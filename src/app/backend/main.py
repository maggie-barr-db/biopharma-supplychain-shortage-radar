"""Shortage radar app backend (FastAPI). Serves the React UI and the API it calls.

Identity: every request runs as the signed-in user (Databricks Apps on-behalf-of-user token).
- UC reads (gold tables, metric view) use the user's token, so UC row filters and masks apply.
- Lakebase reads/writes use the app service principal with app.user = the user's email, so the same
  entitlements apply through Postgres RLS and the approval trigger (UC policies do not reach Lakebase).
- Ask goes to the routing agent with the user's token; if that call fails, it falls back to the
  Supply Exposure Genie Agent called directly as the user.
"""
import os, time, uuid
from pathlib import Path

import httpx
import psycopg
from databricks.sdk import WorkspaceClient
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

CATALOG = os.getenv("CATALOG", "supply_chain")
WAREHOUSE_ID = os.getenv("WAREHOUSE_ID", "")
LAKEBASE_ENDPOINT = os.getenv("LAKEBASE_ENDPOINT", "projects/shortage-radar/branches/production/endpoints/primary")
AGENT_URL = os.getenv("AGENT_URL", "").rstrip("/")
GENIE_SPACE_ID = os.getenv("GENIE_SUPPLY_EXPOSURE_ID", "")
HOST = os.getenv("DATABRICKS_HOST", "").rstrip("/")
if HOST and not HOST.startswith("http"):
    HOST = f"https://{HOST}"

app = FastAPI(title="Shortage radar")
_sp = WorkspaceClient()  # app service principal (Lakebase connection only)


def user_ctx(req: Request) -> tuple[WorkspaceClient, str, str]:
    token = req.headers.get("x-forwarded-access-token")
    email = req.headers.get("x-forwarded-email")
    if not token or not email:
        raise HTTPException(401, "Sign in through Databricks Apps")
    return WorkspaceClient(host=HOST, token=token, auth_type="pat"), email, token


def sql(w: WorkspaceClient, statement: str, params: dict | None = None) -> list[dict]:
    from databricks.sdk.service.sql import StatementParameterListItem
    p = [StatementParameterListItem(name=k, value=str(v)) for k, v in (params or {}).items()]
    r = w.statement_execution.execute_statement(warehouse_id=WAREHOUSE_ID, statement=statement,
                                                parameters=p, wait_timeout="50s")
    if r.status.state.value != "SUCCEEDED":
        raise HTTPException(502, f"query failed: {r.status.error.message if r.status.error else r.status.state}")
    cols = [c.name for c in r.manifest.schema.columns]
    return [dict(zip(cols, row)) for row in (r.result.data_array or [])]


def pg(email: str) -> psycopg.Connection:
    cred = _sp.postgres.generate_database_credential(endpoint=LAKEBASE_ENDPOINT)
    host = _sp.postgres.get_endpoint(name=LAKEBASE_ENDPOINT).status.hosts.host
    conn = psycopg.connect(host=host, dbname="databricks_postgres", user=_sp.config.client_id,
                           password=cred.token, sslmode="require", autocommit=True)
    conn.execute("SELECT set_config('app.user', %s, false)", (email,))
    return conn


@app.get("/api/me")
def me(req: Request):
    w, email, _ = user_ctx(req)
    rows = sql(w, f"SELECT persona, region, can_see_commercial, can_approve FROM {CATALOG}.governance.user_entitlement "
                  "WHERE principal = current_user()")
    return {"email": email, **(rows[0] if rows else {"persona": "none", "region": None,
                                                     "can_see_commercial": "false", "can_approve": "false"})}


@app.get("/api/kpis")
def kpis(req: Request):
    w, _, _ = user_ctx(req)
    return sql(w, f"""SELECT region, MEASURE(sku_count) AS skus, ROUND(MEASURE(avg_days_of_cover), 1) AS avg_days_of_cover,
        MEASURE(skus_under_60_days_cover) AS skus_under_60_days, ROUND(MEASURE(single_source_revenue_share), 3) AS single_source_share
        FROM {CATALOG}.gold.mv_supply_kpis GROUP BY region ORDER BY region""")


@app.get("/api/disruptions")
def disruptions(req: Request):
    w, _, _ = user_ctx(req)
    return sql(w, f"""SELECT d.disruption_id, d.vendor_id, s.vendor_name, d.event_type, d.event_date,
        COUNT(DISTINCT d.sku_id) AS skus, COUNT_IF(d.single_source) AS single_source_skus,
        MIN(d.projected_stockout_date) AS first_stockout, ROUND(SUM(d.revenue_at_risk), 0) AS revenue_at_risk
        FROM {CATALOG}.gold.disruption_impact d LEFT JOIN {CATALOG}.gold.supplier_risk s USING (vendor_id)
        GROUP BY ALL ORDER BY revenue_at_risk DESC NULLS LAST, first_stockout""")


@app.get("/api/disruptions/{disruption_id}")
def disruption(disruption_id: str, req: Request):
    w, _, _ = user_ctx(req)
    return sql(w, f"""SELECT sku_id, drug, region, site_id, api_id, single_source, ROUND(weekly_units, 0) AS weekly_units,
        cover_days_before, cover_days_without_vendor, requalification_days, projected_stockout_date, supply_gap_days,
        revenue_at_risk FROM {CATALOG}.gold.disruption_impact WHERE disruption_id = :id
        ORDER BY projected_stockout_date, sku_id""", {"id": disruption_id})


@app.get("/api/actions")
def actions(req: Request):
    _, email, _ = user_ctx(req)
    with pg(email) as conn:
        cur = conn.execute("""SELECT action_id, disruption_id, sku_id, region, action_type, description, est_revenue_protected,
            proposed_by, proposed_source, on_behalf_of, proposed_at, status, decided_by, decided_at, decision_rationale
            FROM ops.mitigation_action ORDER BY action_id DESC LIMIT 100""")
        cols = [d.name for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]


class Proposal(BaseModel):
    disruption_id: str
    sku_id: str
    region: str
    action_type: str
    description: str
    est_revenue_protected: float | None = None


@app.post("/api/actions")
def propose(p: Proposal, req: Request):
    _, email, _ = user_ctx(req)
    try:
        with pg(email) as conn:
            row = conn.execute("""INSERT INTO ops.mitigation_action (disruption_id, sku_id, region, action_type, description,
                est_revenue_protected, proposed_by, proposed_source) VALUES (%s,%s,%s,%s,%s,%s,%s,'PLANNER') RETURNING action_id""",
                (p.disruption_id, p.sku_id, p.region, p.action_type, p.description, p.est_revenue_protected, email)).fetchone()
    except psycopg.Error as e:
        raise HTTPException(403, str(e).splitlines()[0])
    return {"action_id": row[0], "status": "PROPOSED"}


class Decision(BaseModel):
    status: str
    rationale: str


@app.post("/api/actions/{action_id}/decision")
def decide(action_id: int, d: Decision, req: Request):
    _, email, _ = user_ctx(req)
    if d.status not in ("APPROVED", "REJECTED"):
        raise HTTPException(400, "status must be APPROVED or REJECTED")
    try:
        with pg(email) as conn:
            n = conn.execute("UPDATE ops.mitigation_action SET status = %s, decision_rationale = %s WHERE action_id = %s",
                             (d.status, d.rationale, action_id)).rowcount
    except psycopg.Error as e:  # approval trigger: entitlement, segregation of duties, rationale
        raise HTTPException(403, str(e).splitlines()[0])
    if n == 0:
        raise HTTPException(404, "action not found or not visible to you")
    return {"action_id": action_id, "status": d.status, "decided_by": email}


@app.get("/api/actions/{action_id}/audit")
def audit(action_id: int, req: Request):
    _, email, _ = user_ctx(req)
    with pg(email) as conn:
        visible = conn.execute("SELECT 1 FROM ops.mitigation_action WHERE action_id = %s", (action_id,)).fetchone()
        if not visible:
            raise HTTPException(404, "action not found or not visible to you")
        rows = conn.execute("SELECT audit_id, event, actor, at FROM ops.audit_log WHERE action_id = %s ORDER BY audit_id",
                            (action_id,)).fetchall()
    return [{"audit_id": a, "event": e, "actor": ac, "at": str(t)} for a, e, ac, t in rows]


class Ask(BaseModel):
    question: str
    session_id: str | None = None


def ask_genie(w: WorkspaceClient, question: str) -> dict:
    msg = w.genie.start_conversation_and_wait(space_id=GENIE_SPACE_ID, content=question)
    text, rows = [], None
    for a in msg.attachments or []:
        if a.text:
            text.append(a.text.content)
        if a.query:
            text.append(a.query.description or "")
            res = w.genie.get_message_attachment_query_result(GENIE_SPACE_ID, msg.conversation_id, msg.message_id, a.attachment_id)
            sr = res.statement_response
            if sr and sr.result:
                cols = [c.name for c in sr.manifest.schema.columns]
                rows = [dict(zip(cols, r)) for r in (sr.result.data_array or [])[:20]]
    return {"route": "genie:supply_exposure", "answer": "\n".join(t for t in text if t), "rows": rows}


@app.post("/api/ask")
def ask(q: Ask, req: Request):
    w, _, token = user_ctx(req)
    started = time.time()
    if AGENT_URL:
        try:
            body = {"id": str(uuid.uuid4()), "session_id": q.session_id or str(uuid.uuid4()),
                    "input": [{"role": "user", "content": q.question}]}
            r = httpx.post(f"{AGENT_URL}/api/invocations", json=body, timeout=170,
                           headers={"Authorization": f"Bearer {token}"})
            r.raise_for_status()
            out = r.json().get("output", [])
            answer = "\n".join(m.get("content", "") if isinstance(m.get("content"), str) else
                               " ".join(c.get("text", "") for c in m.get("content", []) if isinstance(c, dict))
                               for m in out if isinstance(m, dict) and m.get("role") == "assistant")
            return {"route": "agent:radar-router", "answer": answer or str(out)[:4000], "rows": None,
                    "session_id": body["session_id"], "seconds": round(time.time() - started, 1)}
        except Exception as e:  # noqa: BLE001 - fall back to Genie, report why
            fallback_reason = f"agent unavailable: {type(e).__name__}"
    else:
        fallback_reason = "agent not configured"
    res = ask_genie(w, q.question)
    return {**res, "fallback_reason": fallback_reason, "seconds": round(time.time() - started, 1)}


dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if dist.exists():
    app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/{path:path}")
    def spa(path: str):
        return FileResponse(dist / "index.html")
