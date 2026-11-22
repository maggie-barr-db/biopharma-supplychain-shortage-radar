import { useEffect, useMemo, useState } from "react";
import { api, Row } from "./api";

type Tab = "radar" | "impact" | "approvals";
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
  const initial = (window.location.hash.replace("#", "").split("&")[0] || "radar") as Tab;
  const [tab, setTabState] = useState<Tab>(["radar", "impact", "approvals"].includes(initial) ? initial : "radar");
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
          {(["radar", "impact", "approvals"] as Tab[]).map((t) => (
            <button key={t} className={tab === t ? "on" : ""} onClick={() => setTab(t)}>
              {{ radar: "Radar", impact: "Impact", approvals: "Approvals" }[t]}
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
      </main>
      <ChatDock tab={tab} disruption={selected} />
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

function Msg({ text }: { text: string }) {
  const ok = /^(Saved|Action #)/.test(text);
  return <div className={ok ? "note" : "alert"}>{text.replace(/^Error: /, "")}</div>;
}

function Tile({ k, v, tone }: { k: string; v: React.ReactNode; tone: "red" | "navy" | "green" }) {
  return <div className={`tile ${tone}`}><div className="tk">{k}</div><div className="tv">{v}</div></div>;
}

const DAY = 86400000;
const fmt = (d: Date) => d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
const ymd = (s: Row[string]) => { const [y, m, dd] = String(s).slice(0, 10).split("-").map(Number); return new Date(y, m - 1, dd); };

function Impact({ d, onPick }: { d: Row | null; onPick: (d: Row) => void }) {
  const [rows, setRows] = useState<Row[]>([]);
  const [msg, setMsg] = useState<string | null>(null);
  const [sort, setSort] = useState<"urgency" | "revenue">("urgency");
  const [openDrug, setOpenDrug] = useState<Record<string, boolean>>({});
  const [form, setForm] = useState({ sku_id: "", action_type: ACTIONS[2], description: "" });
  useEffect(() => { if (!d) api.disruptions().then((ds) => ds.length && onPick(ds[0])); }, [d]);
  useEffect(() => { if (d) api.disruption(String(d.disruption_id)).then(setRows).catch((e) => setMsg(String(e))); }, [d]);

  const view = useMemo(() => {
    if (!rows.length) return null;
    const r0 = rows[0];
    const asof = new Date(ymd(r0.projected_stockout_date).getTime() - Math.round(Number(r0.cover_days_without_vendor)) * DAY);
    const ready = new Date(asof.getTime() + 180 * DAY);
    const skus = rows.map((r) => {
      const out = ymd(r.projected_stockout_date);
      return { r, out, gap: Number(r.supply_gap_days) || 0, rar: num(r.revenue_at_risk), single: r.single_source === "true" };
    });
    const end = new Date(Math.max(ready.getTime() + 20 * DAY, ...skus.map((x) => x.out.getTime() + 10 * DAY)));
    const pos = (t: Date) => ((t.getTime() - asof.getTime()) / (end.getTime() - asof.getTime())) * 100;
    const months: Date[] = [];
    for (let m = new Date(asof.getFullYear(), asof.getMonth() + 1, 1); m < end; m = new Date(m.getFullYear(), m.getMonth() + 1, 1)) months.push(m);
    const revVisible = skus.some((x) => x.rar !== null);
    const byDrug = new Map<string, typeof skus>();
    skus.forEach((x) => byDrug.set(String(x.r.drug), [...(byDrug.get(String(x.r.drug)) ?? []), x]));
    const groups = [...byDrug.entries()].map(([drug, xs]) => ({
      drug, xs: [...xs].sort((a, b) => sort === "revenue" && revVisible ? (b.rar ?? 0) - (a.rar ?? 0) : a.out.getTime() - b.out.getTime()),
      first: new Date(Math.min(...xs.map((x) => x.out.getTime()))), short: xs.filter((x) => x.gap > 0).length,
      rar: revVisible ? xs.reduce((s, x) => s + (x.rar ?? 0), 0) : null,
      regions: [...new Set(xs.filter((x) => x.gap > 0).map((x) => String(x.r.region)))].sort(),
      doses: new Set(xs.map((x) => String(x.r.strength))).size,
    })).sort((a, b) => sort === "revenue" && revVisible ? (b.rar ?? 0) - (a.rar ?? 0) : a.first.getTime() - b.first.getTime());
    const regions = ["US", "EU", "APAC"].map((rg) => {
      const xs = skus.filter((x) => x.r.region === rg);
      const short = xs.filter((x) => x.gap > 0);
      return { rg, total: xs.length, short: short.length, first: short.length ? new Date(Math.min(...short.map((x) => x.out.getTime()))) : null,
               rar: revVisible ? short.reduce((s, x) => s + (x.rar ?? 0), 0) : null };
    }).filter((x) => x.total > 0);
    return { asof, ready, end, pos, months, groups, regions, revVisible };
  }, [rows, sort]);

  if (!d) return <div className="empty">Loading the top disruption...</div>;
  const sku = rows.find((r) => r.sku_id === form.sku_id);
  const submit = () =>
    api.propose({ disruption_id: d.disruption_id, sku_id: form.sku_id, region: String(sku?.region ?? ""), action_type: form.action_type,
      description: form.description, est_revenue_protected: num(sku?.revenue_at_risk) })
      .then((r) => { setMsg(`Saved as proposed action #${r.action_id}. An approver signs off in Approvals.`); setForm({ ...form, description: "" }); })
      .catch((e) => setMsg(String(e)));
  const isOpen = (drug: string, i: number) => openDrug[drug] ?? i === 0;
  return (
    <>
      <div className="eyebrow">Impact · {String(d.event_type).replace(/_/g, " ")} · {String(d.event_date)}</div>
      <h1>{String(d.vendor_name ?? d.vendor_id)}: {rows.length} SKUs exposed, first stockout in {Math.round(Number(d.first_stockout_days))} days</h1>
      {view && (
        <>
          <div className="markets">
            {view.regions.map((m) => (
              <div className={`market ${m.short ? "hot" : ""}`} key={m.rg}>
                <div className="mname">{m.rg}</div>
                <div className="mbig">{m.short}<span> of {m.total} SKUs run out before a new supplier is ready</span></div>
                <div className="mrow">{m.first ? <>first stockout <b>{fmt(m.first)}</b></> : "covered"}{m.rar !== null && m.short > 0 && <> · {money(m.rar)} at risk</>}</div>
              </div>
            ))}
          </div>
          <div className="toolbar">
            <div className="legend">
              <span><i className="sw red" />runs out before a new supplier could be ready (~{fmt(view.ready)}, 180 days to qualify)</span>
              {view.groups.some((g) => g.xs.some((x) => x.gap <= 0)) && <span><i className="sw navy" />covered (stock or a backup supplier lasts)</span>}
              <span className="hint">Click a SKU to propose a mitigation</span>
            </div>
            <div className="seg">
              <button className={sort === "urgency" ? "on" : ""} onClick={() => setSort("urgency")}>Most urgent</button>
              <button className={sort === "revenue" ? "on" : ""} disabled={!view.revVisible} title={view.revVisible ? "" : "Revenue is not visible for your role"} onClick={() => setSort("revenue")}>Most revenue at risk</button>
            </div>
          </div>
          <div className="timeline-card">
            <div className="axis">
              <div className="axis-label" />
              <div className="axis-track">
                <span className="tick today" style={{ left: "0%" }}>today</span>
                {view.months.filter((m) => view.pos(m) > 6).map((m) => <span key={m.toISOString()} className="tick" style={{ left: `${view.pos(m)}%` }}>{m.toLocaleDateString("en-US", { month: "short" })}</span>)}
                <span className="flag" style={{ left: `${view.pos(view.ready)}%` }}>new supplier ~{fmt(view.ready)}</span>
              </div>
              <div />
            </div>
            {view.groups.map((g, i) => (
              <div className="drug" key={g.drug}>
                <button className="drughead" onClick={() => setOpenDrug({ ...openDrug, [g.drug]: !isOpen(g.drug, i) })}>
                  <span className="caret">{isOpen(g.drug, i) ? "▾" : "▸"}</span>
                  <span className="dn">{g.drug}</span>
                  <span className="dm">{g.xs.length} SKUs · {g.doses} {g.doses === 1 ? "dose" : "doses"}</span>
                  <span className="dm">{g.short ? <>{g.short} short in {g.regions.join(", ")}</> : "all covered"}</span>
                  <span className="dm">first stockout <b className={g.short ? "red" : ""}>{fmt(g.first)}</b></span>
                  {g.rar !== null && <span className="dm">{money(g.rar)} at risk</span>}
                </button>
                {isOpen(g.drug, i) && g.xs.map((x) => (<div key={String(x.r.sku_id)}>
                  <div className={`skurow ${form.sku_id === x.r.sku_id ? "sel" : ""}`} onClick={() => { setMsg(null); setForm({ ...form, sku_id: form.sku_id === x.r.sku_id ? "" : String(x.r.sku_id) }); }}>
                    <div className="sku">
                      <b>{String(x.r.strength)} · {String(x.r.pack)}</b>
                      <span><span className="rg">{String(x.r.region)}</span> {String(x.r.sku_id)} · {x.single ? "single-source" : "backup supplier approved"}</span>
                    </div>
                    <div className="axis-track bars">
                      {view.months.map((m) => <i key={m.toISOString()} className="grid" style={{ left: `${view.pos(m)}%` }} />)}
                      <i className="guide" style={{ left: `${view.pos(view.ready)}%` }} />
                      <i className={`bar ${x.gap > 0 ? "red" : "navy"}`} style={{ width: `${view.pos(x.out)}%` }} />
                    </div>
                    <div className="sval">
                      <b className={x.gap > 0 ? "red" : ""}>runs out {fmt(x.out)}</b>
                      <span>{x.gap > 0 ? `${Math.round(x.gap)} days short` : "covered"}{x.rar !== null && x.gap > 0 ? ` · ${money(x.r.revenue_at_risk) as unknown as string}` : ""}</span>
                    </div>
                  </div>
                  {form.sku_id === x.r.sku_id && (
                    <div className="inline-propose" onClick={(e) => e.stopPropagation()}>
                      <div className="ip-title">Propose a mitigation for {String(x.r.drug).replace(/^./, (c) => c.toUpperCase())} {String(x.r.strength)} · {String(x.r.pack)} · {String(x.r.region)}</div>
                      <div className="form">
                        <select value={form.action_type} onChange={(e) => setForm({ ...form, action_type: e.target.value })}>
                          {ACTIONS.map((a) => <option key={a} value={a}>{label(a)}</option>)}
                        </select>
                        <input autoFocus placeholder="What to do and why" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
                        <button className="primary" disabled={!form.description} onClick={submit}>Propose</button>
                        <button className="ghost" onClick={() => setForm({ ...form, sku_id: "" })}>Cancel</button>
                      </div>
                      {msg && <Msg text={msg} />}
                    </div>
                  )}
                </div>))}
              </div>
            ))}
          </div>
        </>
      )}
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
      {msg && <Msg text={msg} />}
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

type Msg = { u: string; a?: string; route?: string };
const saved = <T,>(k: string, d: T): T => { try { return JSON.parse(sessionStorage.getItem(k) ?? "") as T; } catch { return d; } };

function ChatDock({ tab, disruption }: { tab: Tab; disruption: Row | null }) {
  const [open, setOpen] = useState<boolean>(window.location.hash.includes("chat") || saved("radar-chat-open", false));
  const [log, setLog] = useState<Msg[]>(saved("radar-chat-log", []));
  const [session, setSession] = useState<string | undefined>(saved("radar-chat-session", undefined));
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => { sessionStorage.setItem("radar-chat-log", JSON.stringify(log)); }, [log]);
  useEffect(() => { sessionStorage.setItem("radar-chat-open", JSON.stringify(open)); document.body.classList.toggle("dock-open", open); }, [open]);
  useEffect(() => { if (session) sessionStorage.setItem("radar-chat-session", JSON.stringify(session)); }, [session]);
  const who = disruption ? `${disruption.vendor_name ?? disruption.vendor_id} (${disruption.disruption_id})` : "";
  const context = tab === "impact" && disruption ? `Impact page, looking at disruption ${who}` : `${tab} page`;
  const suggestions: Record<Tab, string[]> = {
    radar: ["Which products are exposed to the supplier that just received a warning letter, and when do they stock out?",
            "Which suppliers have an open warning letter or import alert?"],
    impact: [`Which SKUs in this disruption run out before an alternate source can be qualified?`,
             `Propose a mitigation for the most at-risk SKU in this disruption.`],
    approvals: ["Which open purchase orders from single-source suppliers are predicted to be late?",
                "What did the latest warning letter for this supplier say?"],
  };
  const send = (question: string) => {
    setQ(""); setBusy(true); setOpen(true); setLog((l) => [...l, { u: question }]);
    api.ask(question, session, context)
      .then((r) => { setSession(r.session_id ?? session);
        const route = r.route.replace("agent:radar-router -> ", "").split(", ").filter((t) => !t.endsWith("_query_result")).map(label).join(" → ");
        setLog((l) => [...l.slice(0, -1), { u: question, a: r.answer, route: `${r.fallback_reason ? "Genie (fallback)" : route} · ${r.seconds}s` }]); })
      .catch((e) => setLog((l) => [...l.slice(0, -1), { u: question, a: String(e).replace(/^Error: /, "") }]))
      .finally(() => setBusy(false));
  };
  const reset = () => { setLog([]); setSession(undefined); sessionStorage.removeItem("radar-chat-session"); };
  return (
    <>
      {!open && <button className="fab" onClick={() => setOpen(true)}><span className="fabdot" />Ask the radar</button>}
      <aside className={`dock ${open ? "open" : ""}`}>
        <div className="dockhead">
          <div><b>Ask the radar</b><div className="ctx">Context: {context}</div></div>
          <div className="dockbtns"><button className="link" onClick={reset}>New chat</button><button className="x" onClick={() => setOpen(false)} aria-label="Close">×</button></div>
        </div>
        <div className="dockbody">
          {log.length === 0 && <div className="examples">{suggestions[tab].map((e) => <button key={e} onClick={() => send(e)}>{e}</button>)}</div>}
          {log.map((m, i) => (
            <div key={i}>
              <div className="bubble user">{m.u}</div>
              {m.a ? <div className="bubble bot"><Markdown text={m.a} />{m.route && <div className="route">answered by {m.route}</div>}</div>
                : <div className="bubble bot thinking">Routing your question to the right agent...</div>}
            </div>
          ))}
          {log.length > 0 && !busy && <div className="followups">{suggestions[tab].map((e) => <button key={e} onClick={() => send(e)}>{e}</button>)}</div>}
        </div>
        <div className="askbar">
          <input value={q} placeholder="Ask about exposure, suppliers or mitigations" onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && q && !busy && send(q)} />
          <button className="primary" disabled={!q || busy} onClick={() => send(q)}>Ask</button>
        </div>
      </aside>
    </>
  );
}
