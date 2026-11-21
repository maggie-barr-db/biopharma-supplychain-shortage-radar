import { useEffect, useState } from "react";
import { api, Row } from "./api";

type Tab = "radar" | "impact" | "approvals" | "ask";
const money = (v: Row[string]) =>
  v === null || v === undefined ? <span className="masked">restricted</span> : `$${(Number(v) / 1e6).toFixed(1)}M`;
const ACTIONS = ["REALLOCATE_INVENTORY", "EXPEDITE_ALTERNATE_SOURCE", "QUALIFY_ALTERNATE_SOURCE", "ALLOCATE_DEMAND", "FDA_506C_NOTIFICATION"];

export default function App() {
  const [tab, setTab] = useState<Tab>("radar");
  const [me, setMe] = useState<Row | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { api.me().then(setMe).catch((e) => setErr(String(e))); }, []);
  const open = (id: string) => { setSelected(id); setTab("impact"); };
  return (
    <>
      <header>
        <h1>BioChain <span>API Shortage Radar</span></h1>
        <nav>
          {(["radar", "impact", "approvals", "ask"] as Tab[]).map((t) => (
            <button key={t} className={tab === t ? "on" : ""} onClick={() => setTab(t)}>
              {{ radar: "Radar", impact: "Impact", approvals: "Approvals", ask: "Ask" }[t]}
            </button>
          ))}
        </nav>
        {me && <div className="who"><b>{String(me.email)}</b> · {String(me.persona)} · region {String(me.region ?? "none")}</div>}
      </header>
      <main>
        {err && <div className="err">{err}</div>}
        {tab === "radar" && <Radar onOpen={open} />}
        {tab === "impact" && <Impact id={selected} onOpen={open} />}
        {tab === "approvals" && <Approvals me={me} />}
        {tab === "ask" && <Ask />}
      </main>
    </>
  );
}

function Radar({ onOpen }: { onOpen: (id: string) => void }) {
  const [kpis, setKpis] = useState<Row[]>([]);
  const [dis, setDis] = useState<Row[]>([]);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    api.kpis().then(setKpis).catch((e) => setErr(String(e)));
    api.disruptions().then(setDis).catch((e) => setErr(String(e)));
  }, []);
  return (
    <>
      {err && <div className="err">{err}</div>}
      <div className="cards">
        {kpis.map((k) => (
          <div className="card" key={String(k.region)}>
            <div className="k">{String(k.region)} · days of cover</div>
            <div className="v">{String(k.avg_days_of_cover)}</div>
            <div className="s">{String(k.skus)} SKUs · {String(k.skus_under_60_days)} under 60 days ·{" "}
              {k.single_source_share === null ? "revenue share restricted" : `${(Number(k.single_source_share) * 100).toFixed(0)}% single-source revenue`}</div>
          </div>
        ))}
      </div>
      <h2>Active supplier disruptions</h2>
      <table>
        <thead><tr><th>Supplier</th><th>Event</th><th>Date</th><th>SKUs exposed</th><th>Single-source</th><th>First stockout</th><th>Revenue at risk</th></tr></thead>
        <tbody>
          {dis.map((d) => (
            <tr key={String(d.disruption_id)} className="click" onClick={() => onOpen(String(d.disruption_id))}>
              <td>{String(d.vendor_name ?? d.vendor_id)}</td>
              <td><span className="pill crit">{String(d.event_type)}</span></td>
              <td>{String(d.event_date)}</td><td>{String(d.skus)}</td><td>{String(d.single_source_skus)}</td>
              <td>{String(d.first_stockout)}</td><td>{money(d.revenue_at_risk)}</td>
            </tr>
          ))}
          {dis.length === 0 && <tr><td colSpan={7}>No active disruptions in your regions.</td></tr>}
        </tbody>
      </table>
    </>
  );
}

function Impact({ id, onOpen }: { id: string | null; onOpen: (id: string) => void }) {
  const [rows, setRows] = useState<Row[]>([]);
  const [msg, setMsg] = useState<string | null>(null);
  const [form, setForm] = useState({ sku_id: "", action_type: ACTIONS[0], description: "" });
  useEffect(() => { if (id) api.disruption(id).then(setRows).catch((e) => setMsg(String(e))); }, [id]);
  if (!id) return <Radar onOpen={onOpen} />;
  const sku = rows.find((r) => r.sku_id === form.sku_id);
  const submit = () =>
    api.propose({ disruption_id: id, sku_id: form.sku_id, region: String(sku?.region ?? ""), action_type: form.action_type,
      description: form.description, est_revenue_protected: sku?.revenue_at_risk ?? null })
      .then((r) => setMsg(`Saved as PROPOSED action ${r.action_id}. An approver signs off in Approvals.`))
      .catch((e) => setMsg(String(e)));
  return (
    <>
      <h2>Impact of disruption {id}</h2>
      <table>
        <thead><tr><th>SKU</th><th>Drug</th><th>Region</th><th>Source</th><th>Cover now (d)</th><th>Cover w/o vendor (d)</th><th>Stockout</th><th>Gap (d)</th><th>Revenue at risk</th></tr></thead>
        <tbody>
          {rows.map((r) => (
            <tr key={String(r.sku_id)}>
              <td>{String(r.sku_id)}</td><td>{String(r.drug)}</td><td>{String(r.region)}</td>
              <td>{r.single_source === "true" ? <span className="pill crit">single</span> : <span className="pill ok">multi</span>}</td>
              <td>{String(r.cover_days_before)}</td><td>{String(r.cover_days_without_vendor)}</td>
              <td>{String(r.projected_stockout_date)}</td>
              <td>{Number(r.supply_gap_days) > 0 ? <span className="pill warn">{String(r.supply_gap_days)}</span> : "0"}</td>
              <td>{money(r.revenue_at_risk)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <h2 style={{ marginTop: 24 }}>Propose a mitigation</h2>
      <div className="row">
        <select value={form.sku_id} onChange={(e) => setForm({ ...form, sku_id: e.target.value })}>
          <option value="">Select SKU</option>
          {rows.map((r) => <option key={String(r.sku_id)} value={String(r.sku_id)}>{String(r.sku_id)} · {String(r.drug)}</option>)}
        </select>
        <select value={form.action_type} onChange={(e) => setForm({ ...form, action_type: e.target.value })}>
          {ACTIONS.map((a) => <option key={a}>{a}</option>)}
        </select>
        <input style={{ flex: 1, minWidth: 280 }} placeholder="What to do and why" value={form.description}
          onChange={(e) => setForm({ ...form, description: e.target.value })} />
        <button className="primary" disabled={!form.sku_id || !form.description} onClick={submit}>Propose</button>
      </div>
      {msg && <div className="card">{msg}</div>}
    </>
  );
}

function Approvals({ me }: { me: Row | null }) {
  const [rows, setRows] = useState<Row[]>([]);
  const [why, setWhy] = useState<Record<number, string>>({});
  const [audit, setAudit] = useState<{ id: number; rows: Row[] } | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const load = () => api.actions().then(setRows).catch((e) => setMsg(String(e)));
  useEffect(() => { load(); }, []);
  const decide = (id: number, status: string) =>
    api.decide(id, status, why[id] ?? "").then(() => { setMsg(`Action ${id} ${status}.`); load(); }).catch((e) => setMsg(String(e)));
  return (
    <>
      <h2>Mitigation actions {me?.can_approve === "true" ? "(you can approve)" : "(view only)"}</h2>
      {msg && <div className="card" style={{ marginBottom: 12 }}>{msg}</div>}
      <table>
        <thead><tr><th>#</th><th>SKU</th><th>Region</th><th>Action</th><th>Proposed by</th><th>Status</th><th>Decision</th></tr></thead>
        <tbody>
          {rows.map((r) => {
            const id = Number(r.action_id);
            return (
              <tr key={id}>
                <td>{id}</td><td>{String(r.sku_id)}</td><td>{String(r.region)}</td>
                <td><b>{String(r.action_type)}</b><div className="s">{String(r.description)}</div></td>
                <td>{String(r.proposed_by)}{r.on_behalf_of ? ` for ${r.on_behalf_of}` : ""}</td>
                <td><span className={`pill ${r.status === "APPROVED" ? "ok" : r.status === "REJECTED" ? "crit" : "warn"}`}>{String(r.status)}</span></td>
                <td>
                  {r.status === "PROPOSED" ? (
                    <div className="row" style={{ margin: 0 }}>
                      <input placeholder="Rationale (required)" value={why[id] ?? ""} onChange={(e) => setWhy({ ...why, [id]: e.target.value })} />
                      <button className="primary" onClick={() => decide(id, "APPROVED")}>Approve</button>
                      <button className="ghost" onClick={() => decide(id, "REJECTED")}>Reject</button>
                    </div>
                  ) : <span>{String(r.decided_by)} · {String(r.decision_rationale)}</span>}
                  <button className="ghost" style={{ marginTop: 6 }} onClick={() => api.audit(id).then((a) => setAudit({ id, rows: a }))}>Audit</button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {audit && (
        <div className="card" style={{ marginTop: 16 }}>
          <b>Audit trail for action {audit.id}</b>
          {audit.rows.map((a) => <div key={String(a.audit_id)} className="route">{String(a.at)} · {String(a.event)} · {String(a.actor)}</div>)}
        </div>
      )}
    </>
  );
}

function Ask() {
  const [q, setQ] = useState("");
  const [log, setLog] = useState<{ u: string; a?: string; route?: string }[]>([]);
  const [session, setSession] = useState<string | undefined>();
  const [busy, setBusy] = useState(false);
  const send = () => {
    const question = q; setQ(""); setBusy(true); setLog((l) => [...l, { u: question }]);
    api.ask(question, session)
      .then((r) => { setSession(r.session_id ?? session);
        setLog((l) => [...l.slice(0, -1), { u: question, a: r.answer, route: `${r.route}${r.fallback_reason ? ` (${r.fallback_reason})` : ""} · ${r.seconds}s` }]); })
      .catch((e) => setLog((l) => [...l.slice(0, -1), { u: question, a: String(e) }]))
      .finally(() => setBusy(false));
  };
  return (
    <>
      <h2>Ask the radar</h2>
      <div className="chat">
        {log.length === 0 && <div className="s">Try: "Which products are exposed to the supplier that just got a warning letter, and when do they stock out?"</div>}
        {log.map((m, i) => (
          <div key={i}>
            <div className="msg u">{m.u}</div>
            {m.a ? <div className="msg">{m.a}<div className="route">{m.route}</div></div> : <div className="msg route">thinking...</div>}
          </div>
        ))}
      </div>
      <div className="row">
        <input style={{ flex: 1 }} value={q} placeholder="Ask about exposure, suppliers or mitigations"
          onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === "Enter" && q && !busy && send()} />
        <button className="primary" disabled={!q || busy} onClick={send}>Ask</button>
      </div>
    </>
  );
}
