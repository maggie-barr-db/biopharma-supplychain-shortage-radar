import { useEffect, useMemo, useState } from "react";
import { api, Row } from "./api";

type Tab = "radar" | "impact" | "approvals" | "ask";
const ACTIONS = ["REALLOCATE_INVENTORY", "EXPEDITE_ALTERNATE_SOURCE", "QUALIFY_ALTERNATE_SOURCE", "ALLOCATE_DEMAND", "FDA_506C_NOTIFICATION"];
const num = (v: Row[string] | undefined) => (v === null || v === undefined || v === "" ? null : Number(v));
const money = (v: Row[string] | undefined) => {
  const n = num(v);
  if (n === null) return <span className="restricted" title="Not visible for your role">restricted</span>;
  if (n === 0) return "$0";
  return n >= 1e6 ? `$${(n / 1e6).toFixed(1)}M` : `$${Math.round(n / 1e3)}K`;
};
const label = (s: Row[string]) => String(s ?? "").replace(/_/g, " ").toLowerCase();

export default function App() {
  const initial = (window.location.hash.replace("#", "") || "radar") as Tab;
  const [tab, setTabState] = useState<Tab>(["radar", "impact", "approvals", "ask"].includes(initial) ? initial : "radar");
  const setTab = (t: Tab) => { setTabState(t); window.location.hash = t; };
  const [me, setMe] = useState<Row | null>(null);
  const [selected, setSelected] = useState<Row | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { api.me().then(setMe).catch((e) => setErr(String(e))); }, []);
  const open = (d: Row) => { setSelected(d); setTab("impact"); };
  return (
    <div className="shell">
      <header>
        <div className="brand"><span className="mark" />BioChain <b>Shortage Radar</b></div>
        <nav>
          {(["radar", "impact", "approvals", "ask"] as Tab[]).map((t) => (
            <button key={t} className={tab === t ? "on" : ""} onClick={() => setTab(t)}>
              {{ radar: "Radar", impact: "Impact", approvals: "Approvals", ask: "Ask" }[t]}
            </button>
          ))}
        </nav>
        {me && (
          <div className="who">
            <span className="avatar">{String(me.email)[0]?.toUpperCase()}</span>
            <div><div className="email">{String(me.email)}</div>
              <div className="role">{label(me.persona)} · {me.region === "*" ? "all regions" : `${me.region} only`}</div></div>
          </div>
        )}
      </header>
      <main>
        {err && <div className="alert">{err}</div>}
        {tab === "radar" && <Radar onOpen={open} />}
        {tab === "impact" && <Impact d={selected} onPick={setSelected} />}
        {tab === "approvals" && <Approvals me={me} />}
        {tab === "ask" && <Ask />}
      </main>
    </div>
  );
}

function Radar({ onOpen }: { onOpen: (d: Row) => void }) {
  const [kpis, setKpis] = useState<Row[]>([]);
  const [dis, setDis] = useState<Row[] | null>(null);
  useEffect(() => { api.kpis().then(setKpis); api.disruptions().then(setDis).catch(() => setDis([])); }, []);
  const total = useMemo(() => {
    const d = dis ?? [];
    const rar = d.map((x) => num(x.revenue_at_risk)).filter((x): x is number => x !== null);
    return {
      count: d.length, skus: d.reduce((a, x) => a + Number(x.skus), 0),
      rar: rar.length ? rar.reduce((a, b) => a + b, 0) : null,
      first: d.length ? Math.min(...d.map((x) => Number(x.first_stockout_days))) : null,
    };
  }, [dis]);
  return (
    <>
      <div className="eyebrow">Supply risk today</div>
      <h1>Active supplier disruptions and what they put at risk</h1>
      <div className="tiles">
        <Tile k="Active disruptions" v={String(total.count)} tone="navy" />
        <Tile k="SKUs exposed" v={String(total.skus)} tone="navy" />
        <Tile k="Revenue at risk" v={total.rar === null ? "restricted" : money(total.rar)} tone="red" />
        <Tile k="First stockout" v={total.first === null ? "-" : `${total.first} days`} tone="red" />
      </div>
      <div className="section-title">Disruptions <span>click one to see the impact</span></div>
      <div className="cards">
        {(dis ?? []).map((d) => {
          const crit = Number(d.skus_with_gap) > 0;
          return (
            <button key={String(d.disruption_id)} className={`dcard ${crit ? "crit" : ""}`} onClick={() => onOpen(d)}>
              <div className="dtop"><span className={`pill ${crit ? "red" : "amber"}`}>{label(d.event_type)}</span><span className="muted">{String(d.event_date)}</span></div>
              <div className="dname">{String(d.vendor_name ?? d.vendor_id)}</div>
              <div className="dstats">
                <div><b>{String(d.skus)}</b><span>SKUs exposed</span></div>
                <div><b>{String(d.single_source_skus)}</b><span>single-source</span></div>
                <div><b className={crit ? "red" : ""}>{String(d.skus_with_gap)}</b><span>run out before re-sourcing</span></div>
                <div><b>{money(d.revenue_at_risk)}</b><span>revenue at risk</span></div>
              </div>
              <div className="dfoot">First stockout <b>{String(d.first_stockout)}</b> · in {Math.round(Number(d.first_stockout_days))} days</div>
            </button>
          );
        })}
        {dis !== null && dis.length === 0 && <div className="empty">No active disruptions in your regions.</div>}
        {dis === null && <div className="empty">Loading disruptions...</div>}
      </div>
      <div className="section-title">Days of cover by region <span>from the governed metric view</span></div>
      <div className="regions">
        {kpis.map((k) => (
          <div className="region" key={String(k.region)}>
            <div className="rname">{String(k.region)}</div>
            <div className="rbig">{String(k.avg_days_of_cover)}<span> days avg cover</span></div>
            <div className="rrow"><span>{String(k.skus)} SKUs</span><span className={Number(k.skus_under_60_days) > 0 ? "red" : ""}>{String(k.skus_under_60_days)} under 60 days</span></div>
            <div className="bar"><i style={{ width: `${Math.min(100, (num(k.single_source_share) ?? 0) * 100)}%` }} /></div>
            <div className="muted small">{k.single_source_share === null ? "single-source revenue share restricted" : `${Math.round(Number(k.single_source_share) * 100)}% of revenue on single-source APIs`}</div>
          </div>
        ))}
      </div>
    </>
  );
}

function Tile({ k, v, tone }: { k: string; v: React.ReactNode; tone: "red" | "navy" | "green" }) {
  return <div className={`tile ${tone}`}><div className="tk">{k}</div><div className="tv">{v}</div></div>;
}

function Impact({ d, onPick }: { d: Row | null; onPick: (d: Row) => void }) {
  const [rows, setRows] = useState<Row[]>([]);
  const [msg, setMsg] = useState<string | null>(null);
  const [form, setForm] = useState({ sku_id: "", action_type: ACTIONS[2], description: "" });
  useEffect(() => { if (!d) api.disruptions().then((ds) => ds.length && onPick(ds[0])); }, [d]);
  useEffect(() => { if (d) api.disruption(String(d.disruption_id)).then(setRows).catch((e) => setMsg(String(e))); }, [d]);
  if (!d) return <div className="empty">Loading the top disruption...</div>;
  const maxDays = Math.max(180, ...rows.map((r) => Number(r.cover_days_before) || 0));
  const sku = rows.find((r) => r.sku_id === form.sku_id);
  const submit = () =>
    api.propose({ disruption_id: d.disruption_id, sku_id: form.sku_id, region: String(sku?.region ?? ""), action_type: form.action_type,
      description: form.description, est_revenue_protected: num(sku?.revenue_at_risk) })
      .then((r) => { setMsg(`Saved as proposed action #${r.action_id}. An approver signs off in Approvals.`); setForm({ ...form, description: "" }); })
      .catch((e) => setMsg(String(e)));
  return (
    <>
      <div className="eyebrow">Impact · {String(d.event_type).replace(/_/g, " ")} · {String(d.event_date)}</div>
      <h1>{String(d.vendor_name ?? d.vendor_id)}: {rows.length} SKUs exposed, first stockout in {Math.round(Number(d.first_stockout_days))} days</h1>
      <div className="legend"><span><i className="sw cover" />cover without this supplier</span><span><i className="sw gap" />supply gap before an alternate source is qualified</span><span><i className="sw line" />qualification time</span></div>
      <div className="impact">
        {rows.map((r) => {
          const cover = Number(r.cover_days_without_vendor) || 0, req = Number(r.requalification_days) || 0, gap = Math.max(0, req - cover);
          return (
            <div className="irow" key={String(r.sku_id)} onClick={() => setForm({ ...form, sku_id: String(r.sku_id) })}>
              <div className="iname"><b>{String(r.drug)}</b><span>{String(r.sku_id)} · {String(r.region)} · {r.single_source === "true" ? "single-source" : "multi-source"}</span></div>
              <div className="track">
                <i className="cover" style={{ width: `${(Math.min(cover, maxDays) / maxDays) * 100}%` }} />
                {gap > 0 && <i className="gap" style={{ left: `${(cover / maxDays) * 100}%`, width: `${(gap / maxDays) * 100}%` }} />}
                <i className="line" style={{ left: `${(req / maxDays) * 100}%` }} />
              </div>
              <div className="ival"><b className={gap > 0 ? "red" : ""}>{String(r.projected_stockout_date)}</b><span>{gap > 0 ? `${Math.round(gap)} day gap` : "covered"} · {money(r.revenue_at_risk)}</span></div>
            </div>
          );
        })}
      </div>
      <div className="panel">
        <div className="section-title">Propose a mitigation <span>click a SKU above to select it</span></div>
        <div className="form">
          <select value={form.sku_id} onChange={(e) => setForm({ ...form, sku_id: e.target.value })}>
            <option value="">Select SKU</option>
            {rows.map((r) => <option key={String(r.sku_id)} value={String(r.sku_id)}>{String(r.drug)} · {String(r.sku_id)} · {String(r.region)}</option>)}
          </select>
          <select value={form.action_type} onChange={(e) => setForm({ ...form, action_type: e.target.value })}>
            {ACTIONS.map((a) => <option key={a} value={a}>{label(a)}</option>)}
          </select>
          <input placeholder="What to do and why" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
          <button className="primary" disabled={!form.sku_id || !form.description} onClick={submit}>Propose</button>
        </div>
        {msg && <div className="note">{msg}</div>}
      </div>
    </>
  );
}

function Approvals({ me }: { me: Row | null }) {
  const [rows, setRows] = useState<Row[]>([]);
  const [why, setWhy] = useState<Record<number, string>>({});
  const [audit, setAudit] = useState<Record<number, Row[]>>({});
  const [msg, setMsg] = useState<string | null>(null);
  const load = () => api.actions().then(setRows).catch((e) => setMsg(String(e)));
  useEffect(() => { load(); }, []);
  const decide = (id: number, status: string) =>
    api.decide(id, status, why[id] ?? "").then(() => { setMsg(`Action #${id} ${status.toLowerCase()}.`); load(); }).catch((e) => setMsg(String(e)));
  const toggleAudit = (id: number) => audit[id] ? setAudit({ ...audit, [id]: undefined as unknown as Row[] }) : api.audit(id).then((a) => setAudit({ ...audit, [id]: a }));
  return (
    <>
      <div className="eyebrow">Mitigation workflow</div>
      <h1>Proposed and decided mitigations</h1>
      <p className="lede">{me?.can_approve === "true" ? "You can approve. Every decision needs a rationale, and nobody approves their own proposal." : "You can propose; an entitled approver decides."}</p>
      {msg && <div className="note">{msg}</div>}
      <div className="approvals">
        {rows.map((r) => {
          const id = Number(r.action_id);
          return (
            <div className={`acard ${String(r.status).toLowerCase()}`} key={id}>
              <div className="atop">
                <span className={`pill ${r.status === "APPROVED" ? "green" : r.status === "REJECTED" ? "red" : "amber"}`}>{label(r.status)}</span>
                <span className="muted">#{id} · {String(r.sku_id)} · {String(r.region)}</span>
              </div>
              <div className="atitle">{label(r.action_type)}</div>
              <div className="adesc">{String(r.description)}</div>
              <div className="meta">Proposed by {r.proposed_by_persona ? `${label(r.proposed_by_persona).replace("planner ", "planner, ")} (${String(r.proposed_by).includes("@") ? r.proposed_by : "service principal"})` : String(r.proposed_by)}{r.on_behalf_of ? ` for ${r.on_behalf_of}` : ""}{r.proposed_source === "AGENT" ? " · AI assistant" : ""}</div>
              {r.status === "PROPOSED" && me?.can_approve === "true" ? (
                <div className="form">
                  <input placeholder="Rationale (required)" value={why[id] ?? ""} onChange={(e) => setWhy({ ...why, [id]: e.target.value })} />
                  <button className="primary" onClick={() => decide(id, "APPROVED")}>Approve</button>
                  <button className="ghost" onClick={() => decide(id, "REJECTED")}>Reject</button>
                </div>
              ) : r.decided_by ? <div className="meta">Decided by {String(r.decided_by)}: {String(r.decision_rationale)}</div> : null}
              <button className="link" onClick={() => toggleAudit(id)}>{audit[id] ? "Hide audit trail" : "Show audit trail"}</button>
              {audit[id] && <ol className="timeline">{audit[id].map((a) => <li key={String(a.audit_id)}><b>{label(a.event)}</b> · {String(a.actor)} · {String(a.at).slice(0, 19)}</li>)}</ol>}
            </div>
          );
        })}
        {rows.length === 0 && <div className="empty">No mitigations yet. Propose one from the Impact view or ask the assistant.</div>}
      </div>
    </>
  );
}

function Markdown({ text }: { text: string }) {
  const inline = (s: string) => s.split(/(\*\*[^*]+\*\*)/g).map((p, i) => p.startsWith("**") ? <b key={i}>{p.slice(2, -2)}</b> : p);
  const out: React.ReactNode[] = [];
  const lines = text.split("\n");
  for (let i = 0; i < lines.length; i++) {
    const l = lines[i];
    if (l.trim().startsWith("|") && lines[i + 1]?.includes("---")) {
      const head = l.split("|").slice(1, -1).map((c) => c.trim());
      const body: string[][] = [];
      i += 2;
      while (i < lines.length && lines[i].trim().startsWith("|")) { body.push(lines[i].split("|").slice(1, -1).map((c) => c.trim())); i++; }
      i--;
      out.push(<table key={i}><thead><tr>{head.map((h, j) => <th key={j}>{inline(h)}</th>)}</tr></thead><tbody>{body.map((r, k) => <tr key={k}>{r.map((c, j) => <td key={j}>{inline(c)}</td>)}</tr>)}</tbody></table>);
    } else if (/^\s*[-*] /.test(l)) out.push(<li key={i}>{inline(l.replace(/^\s*[-*] /, ""))}</li>);
    else if (l.trim()) out.push(<p key={i}>{inline(l)}</p>);
  }
  return <div className="md">{out}</div>;
}

function Ask() {
  const [q, setQ] = useState("");
  const [log, setLog] = useState<{ u: string; a?: string; route?: string }[]>([]);
  const [session, setSession] = useState<string | undefined>();
  const [busy, setBusy] = useState(false);
  const examples = ["Which products are exposed to the supplier that just received a warning letter, and when do they stock out?",
    "Which suppliers have an open warning letter or import alert?", "Propose a mitigation for the most at-risk SKU in the current disruption."];
  const send = (question: string) => {
    setQ(""); setBusy(true); setLog((l) => [...l, { u: question }]);
    api.ask(question, session)
      .then((r) => { setSession(r.session_id ?? session);
        const route = r.route.replace("agent:radar-router -> ", "").split(", ").filter((t) => !t.endsWith("_query_result")).map(label).join(" → ");
        setLog((l) => [...l.slice(0, -1), { u: question, a: r.answer, route: `${r.fallback_reason ? "Genie (fallback)" : route} · ${r.seconds}s` }]); })
      .catch((e) => setLog((l) => [...l.slice(0, -1), { u: question, a: String(e) }]))
      .finally(() => setBusy(false));
  };
  return (
    <>
      <div className="eyebrow">Ask the radar</div>
      <h1>Questions in plain English, routed to the right agent</h1>
      <div className="chat">
        {log.length === 0 && <div className="examples">{examples.map((e) => <button key={e} onClick={() => send(e)}>{e}</button>)}</div>}
        {log.map((m, i) => (
          <div key={i}>
            <div className="bubble user">{m.u}</div>
            {m.a ? <div className="bubble bot"><Markdown text={m.a} /><div className="route">answered by {m.route}</div></div>
              : <div className="bubble bot thinking">Routing your question to the right agent...</div>}
          </div>
        ))}
      </div>
      <div className="askbar">
        <input value={q} placeholder="Ask about exposure, suppliers or mitigations" onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && q && !busy && send(q)} />
        <button className="primary" disabled={!q || busy} onClick={() => send(q)}>Ask</button>
      </div>
    </>
  );
}
