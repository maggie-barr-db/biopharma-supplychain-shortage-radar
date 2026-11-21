"""P01 synthetic data generator for BioChain Industries (all data fictional).

Writes raw landing files to /Volumes/<catalog>/raw/landing and a run summary to
/Volumes/<catalog>/raw/run_log/generate_<scenario>.json. Seeded and idempotent: the
same seed and as-of date rewrite the same files.

Scenarios:
  base            two years of ERP, supplier quality, forecast and SKU data
  warning_letter  one new FDA Warning Letter for the single-source API vendor with the
                  most revenue exposure (the demo disruption signal)

Planted issues (the pipeline must handle these):
  supplier quality uses its own supplier codes and name spellings; DUNS sometimes missing
  ~2% of PO lines re-sent in a second file (duplicates)
  ~3% of PO lines in grams instead of kilograms
  ~4% of PO lines from older vendors have no lead time
  one forecast file delivered twice, one delivered late (older published_at)
  ~0.5% negative forecast quantities
  discontinued SKUs still in the SKU master
"""
import argparse, csv, json, os, random, shutil
from datetime import date, timedelta

REGIONS = {"US": ["US-NJ1", "US-NC1"], "EU": ["EU-IE1", "EU-DE1"], "APAC": ["AP-SG1", "AP-IN1"]}
DRUGS = ["cefazolin", "ceftriaxone", "vancomycin", "meropenem", "piperacillin", "heparin",
         "enoxaparin", "ondansetron", "dexamethasone", "methylprednisolone", "furosemide",
         "midazolam", "propofol", "ketamine", "fentanyl", "morphine", "lidocaine", "bupivacaine",
         "norepinephrine", "epinephrine", "vasopressin", "amiodarone", "esmolol", "labetalol",
         "pantoprazole", "famotidine", "metoclopramide", "acyclovir", "fluconazole",
         "azithromycin", "doxycycline", "gentamicin", "tobramycin", "insulin glargine",
         "octreotide", "oxytocin", "magnesium sulfate", "potassium chloride",
         "sodium bicarbonate", "tranexamic acid"]
EXCIPIENTS = ["mannitol", "sucrose", "polysorbate 80", "sodium citrate", "benzyl alcohol",
              "sodium chloride", "trehalose", "histidine", "glycine", "edetate disodium"]
WORDS = ["Arden", "Bexley", "Calder", "Dunmore", "Elmwood", "Fairhaven", "Glenrock", "Harlow",
         "Ivybridge", "Juniper", "Kestrel", "Larchmont", "Moreton", "Northgate", "Oakridge"]
SUFFIX = ["Fine Chemicals", "Pharma Ingredients", "Biochem", "Synthesis", "API Works"]
COUNTRIES = ["IN", "CN", "IT", "DE", "US", "IE", "KR", "ES"]
EVENTS = {"AUDIT": 0.45, "FDA_483": 0.25, "CAPA_CLOSED": 0.2, "WARNING_LETTER": 0.06, "IMPORT_ALERT": 0.04}


def write_csv(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def write_jsonl(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write("\n".join(json.dumps(r) for r in rows) + "\n")


def build_master(rng):
    vendors, used = [], set()
    while len(vendors) < 60:
        name = f"{rng.choice(WORDS)} {rng.choice(SUFFIX)}"
        if name in used:
            continue
        used.add(name)
        i = len(vendors)
        vendors.append({"vendor_id": f"V{100100 + i}", "vendor_name": name, "country": rng.choice(COUNTRIES),
                        "duns": f"{rng.randint(10**8, 10**9 - 1)}", "created_year": rng.randint(2008, 2024),
                        "reliability": round(rng.betavariate(8, 2), 3)})
    materials = [{"material_id": f"M-API-{i:03d}", "material_name": f"{d} API", "material_type": "API",
                  "base_uom": "KG"} for i, d in enumerate(DRUGS)]
    materials += [{"material_id": f"M-EXC-{i:03d}", "material_name": f"{e} grade {g}", "material_type": "EXCIPIENT",
                   "base_uom": "KG"} for i, (e, g) in enumerate((e, g) for e in EXCIPIENTS for g in "ABCDEFGH")]
    source_list = []
    for m in materials:
        n = 1 if rng.random() < 0.35 else rng.choice([2, 2, 3])
        for v in rng.sample(vendors, n):
            source_list.append({"material_id": m["material_id"], "vendor_id": v["vendor_id"],
                                "lead_time_days": rng.choice([30, 45, 60, 75, 90])})
    skus, bom = [], []
    for i, d in enumerate(DRUGS):
        for strength in rng.sample(["1 g", "2 g", "500 mg", "10 mg/mL", "50 mg/mL"], rng.randint(1, 3)):
            for pack in rng.sample(["vial x10", "vial x25", "prefilled syringe x10"], rng.randint(1, 2)):
                for region in rng.sample(list(REGIONS), rng.randint(1, 3)):
                    sku_id = f"SKU-{len(skus) + 1:04d}"
                    skus.append({"sku_id": sku_id, "drug": d, "strength": strength, "pack": pack, "region": region,
                                 "site_id": rng.choice(REGIONS[region]), "net_price": round(rng.uniform(10, 400), 2),
                                 "status": "DISCONTINUED" if rng.random() < 0.04 else "ACTIVE",
                                 "weekly_demand": rng.randint(40, 1200)})
                    bom.append({"sku_id": sku_id, "material_id": f"M-API-{i:03d}", "qty_kg_per_unit": round(rng.uniform(0.0005, 0.004), 5)})
                    for e in rng.sample([m for m in materials if m["material_type"] == "EXCIPIENT"], rng.randint(2, 3)):
                        bom.append({"sku_id": sku_id, "material_id": e["material_id"], "qty_kg_per_unit": round(rng.uniform(0.0001, 0.002), 5)})
    return vendors, materials, source_list, skus, bom


def quality_events(rng, vendors, as_of):
    events = []
    for v in vendors:
        for _ in range(rng.randint(3, 10)):
            et = rng.choices(list(EVENTS), weights=list(EVENTS.values()))[0]
            events.append(quality_row(rng, v, et, as_of - timedelta(days=rng.randint(1, 730))))
    return events


def quality_row(rng, v, event_type, d):
    name = v["vendor_name"].upper() if rng.random() < 0.3 else v["vendor_name"].replace("Pharma Ingredients", "Pharma Ingr.")
    findings = {"FDA_483": "Inadequate investigation of out-of-specification results; cleaning validation gaps.",
                "WARNING_LETTER": "Significant CGMP violations: data integrity failures and contamination controls not followed.",
                "IMPORT_ALERT": "Firm placed on import alert; products subject to detention without physical examination.",
                "AUDIT": "Routine supplier audit; minor documentation observations.",
                "CAPA_CLOSED": "Corrective actions verified and closed."}[event_type]
    return {"supplierCode": f"SQ-{int(v['vendor_id'][1:]) - 100000:04d}", "supplierName": name,
            "dunsNumber": None if rng.random() < 0.1 else v["duns"], "eventType": event_type,
            "eventDate": d.isoformat(), "siteCountry": v["country"],
            "severity": {"WARNING_LETTER": "CRITICAL", "IMPORT_ALERT": "CRITICAL", "FDA_483": "MAJOR"}.get(event_type, "MINOR"),
            "findingText": findings, "status": "CLOSED" if event_type in ("AUDIT", "CAPA_CLOSED") else rng.choice(["OPEN", "CLOSED"])}


def purchase_orders(rng, vendors, source_list, skus, events, as_of):
    vend = {v["vendor_id"]: v for v in vendors}
    bad = {}
    for e in events:
        if e["eventType"] in ("FDA_483", "WARNING_LETTER", "IMPORT_ALERT"):
            bad.setdefault(f"V{100000 + int(e['supplierCode'][3:])}", []).append(date.fromisoformat(e["eventDate"]))
    sites_using = {}
    for s in skus:
        sites_using.setdefault(s["site_id"], set())
    lines, n = [], 0
    start = as_of - timedelta(days=730)
    for day in range(730):
        d = start + timedelta(days=day)
        for _ in range(rng.randint(50, 80)):
            sl = rng.choice(source_list)
            v = vend[sl["vendor_id"]]
            lead = sl["lead_time_days"] + rng.randint(-5, 5)
            promised = d + timedelta(days=lead)
            recent_bad = sum(1 for b in bad.get(v["vendor_id"], []) if 0 <= (d - b).days <= 180)
            p_late = (1 - v["reliability"]) + 0.18 * recent_bad + (0.12 if lead < 40 else 0) + (0.08 if v["country"] in ("IN", "CN") else 0)
            delay = rng.randint(8, 45) if rng.random() < min(p_late, 0.9) else rng.randint(-5, 6)
            received = promised + timedelta(days=delay)
            qty = round(rng.uniform(5, 400), 1)
            grams = rng.random() < 0.03
            n += 1
            lines.append({"po_number": f"45{n // 3:08d}", "po_line": n % 3 + 1, "material_id": sl["material_id"],
                          "vendor_id": v["vendor_id"], "site_id": rng.choice(sorted(sites_using)),
                          "order_qty": qty * 1000 if grams else qty, "uom": "G" if grams else "KG",
                          "order_date": d.isoformat(), "promised_date": promised.isoformat(),
                          "lead_time_days": "" if (v["created_year"] < 2012 and rng.random() < 0.3) else lead,
                          "receipt_date": received.isoformat() if received <= as_of else ""})
    return lines


def inventory(rng, skus, bom, as_of):
    rows = []
    api_sites = {(b["material_id"], s["site_id"]) for s in skus for b in bom if b["sku_id"] == s["sku_id"] and b["material_id"].startswith("M-API")}
    for day in range(90):
        d = (as_of - timedelta(days=89 - day)).isoformat()
        for s in skus:
            rows.append({"snapshot_date": d, "site_id": s["site_id"], "item_id": s["sku_id"], "item_type": "SKU",
                         "on_hand": int(s["weekly_demand"] / 7 * rng.uniform(15, 110)), "uom": "EA"})
        for m, site in sorted(api_sites):
            rows.append({"snapshot_date": d, "site_id": site, "item_id": m, "item_type": "API",
                         "on_hand": round(rng.uniform(20, 900), 1), "uom": "KG"})
    return rows


def forecasts(rng, skus, as_of):
    files = {}
    for k in range(8):
        pub = as_of - timedelta(days=7 * (7 - k))
        rows = []
        for s in skus:
            for w in range(26):
                q = int(s["weekly_demand"] * rng.uniform(0.8, 1.2))
                rows.append({"published_at": pub.isoformat(), "sku_id": s["sku_id"], "region": s["region"],
                             "week_start": (pub + timedelta(days=7 * w)).isoformat(),
                             "forecast_units": -q if rng.random() < 0.005 else q})
        files[f"forecast_{pub.isoformat()}.csv"] = rows
    names = sorted(files)
    files[names[-1].replace(".csv", "_resend.csv")] = files[names[-1]]  # duplicate delivery
    files[f"forecast_{names[-3][9:19]}_late.csv"] = files.pop(names[-3])  # late delivery, older published_at
    return files


def warning_letter(root, rng, vendors, source_list, skus, bom, as_of):
    sole = {}
    for sl in source_list:
        sole.setdefault(sl["material_id"], []).append(sl["vendor_id"])
    rev = {}
    for b in bom:
        vs = sole.get(b["material_id"], [])
        if b["material_id"].startswith("M-API") and len(vs) == 1:
            s = next(x for x in skus if x["sku_id"] == b["sku_id"])
            rev[vs[0]] = rev.get(vs[0], 0) + s["weekly_demand"] * s["net_price"] * 52
    vid = max(rev, key=rev.get)
    v = next(x for x in vendors if x["vendor_id"] == vid)
    row = quality_row(rng, v, "WARNING_LETTER", as_of)
    row["status"] = "OPEN"
    write_jsonl(f"{root}/supplier_quality/events_{as_of.isoformat()}_alert.json", [row])
    with open(f"{root}/docs/warning_letter_{row['supplierCode']}_{as_of.isoformat()}.txt", "w") as f:
        f.write(f"WARNING LETTER (synthetic)\nTo: {v['vendor_name']}\nDate: {as_of}\n\n{row['findingText']}\n"
                "Until violations are corrected, FDA may withhold approval of applications listing this firm.\n")
    return {"vendor_id": vid, "supplier_code": row["supplierCode"], "annual_revenue_exposed": round(rev[vid])}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--catalog", default="supply_chain")
    p.add_argument("--as-of", default="2026-11-20")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--scenario", default="base", choices=["base", "warning_letter"])
    a, _ = p.parse_known_args()
    as_of, rng = date.fromisoformat(a.as_of), random.Random(a.seed)
    root = f"/Volumes/{a.catalog}/raw/landing"
    vendors, materials, source_list, skus, bom = build_master(rng)
    events = quality_events(rng, vendors, as_of)
    summary = {"task": "generate", "scenario": a.scenario, "as_of": a.as_of, "seed": a.seed}
    if a.scenario == "warning_letter":
        summary["disruption"] = warning_letter(root, random.Random(a.seed + 1), vendors, source_list, skus, bom, as_of)
    else:
        for sub in ("erp", "supplier_quality", "forecast", "sku", "docs"):
            shutil.rmtree(f"{root}/{sub}", ignore_errors=True)
        write_csv(f"{root}/erp/vendors/vendors.csv", [{k: v[k] for k in v if k != "reliability"} for v in vendors])
        write_csv(f"{root}/erp/materials/materials.csv", materials)
        write_csv(f"{root}/erp/source_list/source_list.csv", source_list)
        write_csv(f"{root}/erp/bom/bom.csv", bom)
        write_csv(f"{root}/sku/sku_master.csv", [{k: s[k] for k in s if k != "weekly_demand"} for s in skus])
        lines = purchase_orders(rng, vendors, source_list, skus, events, as_of)
        by_month = {}
        for l in lines:
            by_month.setdefault(l["order_date"][:7], []).append(l)
        for m, rows in by_month.items():
            write_csv(f"{root}/erp/po_lines/po_lines_{m}.csv", rows)
        dupes = rng.sample(lines, len(lines) // 50)
        write_csv(f"{root}/erp/po_lines/po_lines_resend_{a.as_of}.csv", dupes)
        inv = inventory(rng, skus, bom, as_of)
        for d in sorted({r["snapshot_date"] for r in inv}):
            write_csv(f"{root}/erp/inventory/inventory_{d}.csv", [r for r in inv if r["snapshot_date"] == d])
        by_q = {}
        for e in events:
            by_q.setdefault(e["eventDate"][:7], []).append(e)
        for m, rows in by_q.items():
            write_jsonl(f"{root}/supplier_quality/events_{m}.json", rows)
        os.makedirs(f"{root}/docs", exist_ok=True)
        for e in events:
            if e["eventType"] in ("FDA_483", "WARNING_LETTER"):
                with open(f"{root}/docs/{e['eventType'].lower()}_{e['supplierCode']}_{e['eventDate']}.txt", "w") as f:
                    f.write(f"{e['eventType']} (synthetic)\nSupplier: {e['supplierName']}\nDate: {e['eventDate']}\n\n{e['findingText']}\n")
        fc = forecasts(rng, [s for s in skus if s["status"] == "ACTIVE"], as_of)
        for name, rows in fc.items():
            write_csv(f"{root}/forecast/{name}", rows)
        summary.update({"vendors": len(vendors), "materials": len(materials), "source_list": len(source_list),
                        "single_source_api_pct": round(100 * sum(1 for m in materials if m["material_type"] == "API" and sum(1 for s in source_list if s["material_id"] == m["material_id"]) == 1) / len(DRUGS), 1),
                        "skus": len(skus), "bom_lines": len(bom), "po_lines": len(lines), "po_duplicates_planted": len(dupes),
                        "po_lines_in_grams": sum(1 for l in lines if l["uom"] == "G"),
                        "po_lines_no_lead_time": sum(1 for l in lines if l["lead_time_days"] == ""),
                        "inventory_rows": len(inv), "quality_events": len(events), "forecast_files": len(fc),
                        "negative_forecasts": sum(1 for rows in fc.values() for r in rows if r["forecast_units"] < 0)})
    os.makedirs(f"/Volumes/{a.catalog}/raw/run_log", exist_ok=True)
    with open(f"/Volumes/{a.catalog}/raw/run_log/generate_{a.scenario}.json", "w") as f:
        json.dump(summary, f, indent=2)
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
