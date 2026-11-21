"""P07/P08 evaluation per EVAL_PROTOCOL.md section 2 -> evidence/05_genie_agent.ipynb.

1. Answer correctness: each benchmark question in the Genie Agent definitions is asked through the Genie
   Conversation API; the result is correct when the expected SQL's values appear in Genie's result
   (single numbers within 1%).
2. Routing accuracy: all 15 questions go to the routing agent; correct when it called the expected tool(s).
3. Access check: 3 questions rerun as the planner_eu service principal.
Usage: python tools/eval_genie.py --profile <p> --planner-profile <p> --agent-url <url>
"""
import argparse, json, subprocess, sys, time, uuid
from pathlib import Path

import httpx
from databricks.sdk import WorkspaceClient

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from capture_evidence import notebook  # noqa: E402

WAREHOUSE = "1d88ef6b173bebc3"
CROSS = [  # questions that need both agents or the action tool (EVAL_PROTOCOL: 3 cross questions)
    ("Which products are exposed to the supplier that just received a warning letter, and when do they stock out?",
     {"supplier_quality", "supply_exposure"}),
    ("Are any SKUs in the current disruption supplied by vendors whose open POs are predicted to be late?",
     {"supplier_quality", "supply_exposure"}),
    ("Propose a mitigation for the single most at-risk SKU in the current disruption.", {"supply_exposure", "propose_mitigation"}),
]


def values(w, sql):
    r = w.statement_execution.execute_statement(warehouse_id=WAREHOUSE, statement=sql, wait_timeout="50s")
    return [row for row in (r.result.data_array or [])] if r.result else []


def genie_rows(w, space, question):
    msg = w.genie.start_conversation_and_wait(space_id=space, content=question)
    for a in msg.attachments or []:
        if a.query:
            res = w.genie.get_message_attachment_query_result(space, msg.conversation_id, msg.message_id, a.attachment_id)
            sr = res.statement_response
            return (sr.result.data_array or []) if sr and sr.result else [], a.query.query
    return [], None


def correct(expected, got):
    exp = [str(v) for row in expected for v in row[:1] if v is not None]
    flat = [str(v) for row in got for v in row if v is not None]
    if len(exp) == 1:
        try:
            e = float(exp[0])
            return any(abs(float(g) - e) <= max(abs(e) * 0.01, 1e-9) for g in flat if g.replace(".", "", 1).replace("-", "", 1).isdigit()) or exp[0] in flat
        except ValueError:
            return exp[0] in flat
    return bool(exp) and all(v in flat for v in exp)


def agent_tools(url, token, question):
    body = {"id": str(uuid.uuid4()), "session_id": str(uuid.uuid4()), "input": [{"role": "user", "content": question}]}
    r = httpx.post(f"{url}/api/invocations", json=body, headers={"Authorization": f"Bearer {token}"}, timeout=240)
    out = r.json().get("output", []) if r.status_code == 200 else []
    out = out.get("output", []) if isinstance(out, dict) else out
    names = {t.get("name", "") for m in out if isinstance(m, dict) for t in (m.get("tool_calls") or [])}
    answer = " ".join(m["content"] for m in out if isinstance(m, dict) and m.get("role") == "assistant"
                      and isinstance(m.get("content"), str))
    return {n.removesuffix("_ask").removesuffix("_poll").removesuffix("_query_result") for n in names if n}, r.status_code, answer[-600:]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--profile", required=True)
    p.add_argument("--planner-profile", default="radar-planner-eu")
    p.add_argument("--agent-url", required=True)
    a = p.parse_args()
    w, wp = WorkspaceClient(profile=a.profile), WorkspaceClient(profile=a.planner_profile)
    spaces = json.loads(subprocess.run(["databricks", "bundle", "summary", "--profile", a.profile, "-o", "json"], cwd=ROOT,
                                       capture_output=True, text=True).stdout)["resources"]["genie_spaces"]
    results, cells, t0 = [], [], time.time()
    for key in ("supply_exposure", "supplier_quality"):
        spec = json.loads((ROOT / "src/genie" / f"{key}.geniespace.json").read_text())
        for b in spec["benchmarks"]["questions"]:
            q, sql = b["question"][0], b["answer"][0]["content"][0]
            got, gsql = genie_rows(w, spaces[key]["id"], q)
            ok = correct(values(w, sql), got)
            results.append({"agent": key, "question": q, "correct": ok, "tools_expected": {key}})
    token = w.config.authenticate()["Authorization"].split(" ", 1)[1]
    for r in results:
        r["tools_called"], r["agent_status"], _ = agent_tools(a.agent_url, token, r["question"])
        r["routed"] = r["tools_expected"] <= r["tools_called"]
    for q, exp in CROSS:
        called, status, answer = agent_tools(a.agent_url, token, q)
        results.append({"agent": "routing", "question": q, "correct": None, "tools_expected": exp, "tools_called": called,
                        "agent_status": status, "routed": exp <= called, "answer": answer})
    access = []
    for b in json.loads((ROOT / "src/genie/supply_exposure.geniespace.json").read_text())["benchmarks"]["questions"][:3]:
        got, _ = genie_rows(wp, spaces["supply_exposure"]["id"], b["question"][0])
        access.append({"question": b["question"][0], "planner_rows": len(got), "sample": got[:3]})
    n_correct = sum(1 for r in results if r["correct"])
    n_bench = sum(1 for r in results if r["correct"] is not None)
    n_routed = sum(1 for r in results if r["routed"])
    table = "\n".join(f"{'OK ' if r['correct'] else ('-- ' if r['correct'] is None else 'NO ')}{'R ' if r['routed'] else 'r '}"
                      f"[{r['agent']}] {r['question'][:70]} | called={sorted(r['tools_called'])}" for r in results)
    cells = [("results (OK/NO = answer correct, R/r = routed correctly)", "-- tools/eval_genie.py", table),
             ("cross-agent answers", "-- routing agent", json.dumps([r.get("answer") for r in results if r["agent"] == "routing"], indent=1)[:2500]),
             ("access check as planner_eu (EU only, revenue NULL)", "-- Genie as service principal", json.dumps(access, default=str)[:1500])]
    head = (f"**Genie answers {n_correct}/{n_bench} benchmark questions correctly; the routing agent routes {n_routed}/{len(results)} "
            f"to the expected tool(s)** (bars: 12/15 and 13/15 in EVAL_PROTOCOL). Run time {int(time.time() - t0)} s.\n")
    notebook("05_genie_agent", head, cells)
    print(head)


if __name__ == "__main__":
    main()
