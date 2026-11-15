"""ECE-038 billing engine. Business rules BR-01..BR-08 are marked inline."""
import calendar, csv, io, os, re
from datetime import datetime, date
from decimal import Decimal as D, ROUND_HALF_UP

MONO_RATE, COL_RATE, GST = D("0.60"), D("4.50"), D("0.18")     # BR-04, BR-08
CTR = ("mono", "colour", "a3_mono", "a3_colour")
CART = ("black", "cyan", "magenta", "yellow")
OLD = {"black": "toner_k", "cyan": "toner_c", "magenta": "toner_m", "yellow": "toner_y"}


def q(x, p="1"):
    return D(x).quantize(D(p), ROUND_HALF_UP)


def f2(x):
    return f"{q(D(str(x)), '0.01'):.2f}"


def pick(d, *keys, default=None):
    for k in keys:
        if d.get(k) not in (None, ""): return d[k]
    return default


def rows(text):
    return [{(k or "").strip(): (v or "").strip() for k, v in r.items()} for r in csv.DictReader(io.StringIO(text.strip()))]


def ts(v):
    return datetime.fromisoformat(v.strip().replace(" ", "T"))


class Store:
    def __init__(s):
        s.clear()

    def clear(s):
        s.customers, s.devices, s.readings, s.tickets, s.errors = {}, {}, {}, [], []

    def add_customer(s, c):
        s.customers[c["customer_id"]] = {"customer_id": c["customer_id"], "name": c.get("name") or c["customer_id"], "city": c.get("city", "")}
        for d in c.get("devices", []):
            s.add_device({**d, "customer_id": c["customer_id"]})

    def add_device(s, d):
        n = dict(device_id=d["device_id"], customer_id=d["customer_id"], model=d.get("model", ""),
                 rental=D(str(pick(d, "monthly_rental", "rental"))),
                 inc_mono=int(pick(d, "included_mono", "inc_mono", default=0)), inc_colour=int(pick(d, "included_colour", "inc_colour", default=0)),
                 install_date=str(pick(d, "installation_date", "install_date"))[:10])
        for k in CTR: n["open_" + k] = int(pick(d, "opening_" + k, "open_" + k, default=0))
        s.devices[n["device_id"]] = n
        s.customers.setdefault(n["customer_id"], {"customer_id": n["customer_id"], "name": n["customer_id"], "city": ""})

    def add_reading(s, r):
        n = {k: int(r[k]) for k in CTR}
        for c in CART:
            v = pick(r, f"toner_{c}_pct", OLD[c]); n["toner_" + c] = int(v) if v is not None else 100
        n.update(device_id=r["device_id"], month=str(pick(r, "reading_date", "month"))[:7])
        s.readings.setdefault((n["device_id"], n["month"]), n)          # duplicate row for same device+month: first one wins

    def add_ticket(s, t):
        tid = t.get("ticket_id") or f"TKT-{len(s.tickets) + 1:03d}"
        op, cl = ts(pick(t, "opened_at", "opened")), pick(t, "closed_at", "closed")
        if cl is None: s.errors.append(f"ERROR {tid}: no closed_at, ticket rejected"); return
        cl = ts(cl)
        if cl < op: s.errors.append(f"ERROR {tid}: closed_at is before opened_at, ticket rejected"); return
        secs = int((cl - op).total_seconds())
        s.tickets.append(dict(ticket_id=tid, device_id=t["device_id"], month=cl.strftime("%Y-%m"), hours=secs / 3600,
                              credit_days=max(0, (secs - 48 * 3600) // 86400)))        # BR-06: full 24h beyond 48h (exactly 48h -> 0)

    def _load(s, fn, text):
        r = rows(text)
        for x in r: fn(x)
        return len(r)

    def load_customers_csv(s, t): return s._load(s.add_customer, t)
    def load_devices_csv(s, t): return s._load(s.add_device, t)
    def load_readings_csv(s, t): return s._load(s.add_reading, t)
    def load_tickets_csv(s, t): return s._load(s.add_ticket, t)

    def months(s):
        return sorted({m for (_, m) in s.readings})


def days_installed(dev, y, m, dim):                     # BR-07: install day counts
    d = datetime.fromisoformat(dev["install_date"]).date()
    if d > date(y, m, dim): return 0
    return dim if d <= date(y, m, 1) else dim - d.day + 1


def usage(st, dev, month):                              # BR-01, BR-02
    cur = st.readings.get((dev["device_id"], month))
    if not cur: return None
    y, m = map(int, month.split("-"))
    prev_month = f"{y - 1}-12" if m == 1 else f"{y}-{m - 1:02d}"
    p = st.readings.get((dev["device_id"], prev_month)) or {k: dev["open_" + k] for k in CTR}
    diff = {k: cur[k] - p[k] for k in CTR}
    if any(v < 0 for v in diff.values()): return {"error": True}     # equal reading = 0 pages, valid
    return {"error": False, "mono": diff["mono"] + 2 * diff["a3_mono"], "colour": diff["colour"] + 2 * diff["a3_colour"]}


def ticket_rows(st, month):                             # a ticket's credit belongs to the month it was closed
    out = []
    for t in st.tickets:
        if t["month"] != month: continue
        dev = st.devices.get(t["device_id"])
        before = D(200 * t["credit_days"])
        credit = min(before, dev["rental"]) if dev else before
        out.append(dict(ticket_id=t["ticket_id"], device_id=t["device_id"], month=month, hours_open=round(t["hours"], 2),
                        credit_days=t["credit_days"], credit_before_cap=float(before), credit=float(credit)))
    return out


def invoice(st, cid, month):
    y, mo = map(int, month.split("-"))
    dim = calendar.monthrange(y, mo)[1]
    tk, lines = ticket_rows(st, month), []
    for dev in sorted((d for d in st.devices.values() if d["customer_id"] == cid), key=lambda d: d["device_id"]):
        days = days_installed(dev, y, mo, dim)
        if not days: continue
        inc_m, inc_c = (int(q(D(dev[k]) * days / dim)) for k in ("inc_mono", "inc_colour"))
        rent = q(dev["rental"] * days / dim, "0.01")
        u = usage(st, dev, month)
        if u is None: m = c = 0; status = "NO_READING"
        elif u["error"]: m, c, status = inc_m, inc_c, "METER_ERROR"        # BR-01: billed at included pages only
        else: m, c = u["mono"], u["colour"]; status = "ZERO_PAGES" if m + c == 0 else "OK"
        mine = [t for t in tk if t["device_id"] == dev["device_id"]]
        credit = min(sum((D(str(t["credit"])) for t in mine), D(0)), dev["rental"])      # BR-06 cap
        lines.append(dict(device_id=dev["device_id"], model=dev["model"], days=days, rental=float(rent), inc_mono=inc_m, inc_colour=inc_c,
                          mono=m, colour=c, status=status, flag=status if status in ("METER_ERROR", "NO_READING") else None,
                          credit=float(credit), ticket_hours=int(max([t["hours_open"] for t in mine], default=0)),
                          util=float(q(D(m + c) * 100 / (inc_m + inc_c), "0.1")) if inc_m + inc_c else 0.0))
    pm, pc = sum(l["inc_mono"] for l in lines), sum(l["inc_colour"] for l in lines)      # BR-03 pooling
    um, uc = sum(l["mono"] for l in lines), sum(l["colour"] for l in lines)
    om, oc = max(0, um - pm), max(0, uc - pc)
    oma, oca = om * MONO_RATE, oc * COL_RATE                                              # BR-04
    solo = sum(max(0, l["mono"] - l["inc_mono"]) for l in lines) * MONO_RATE + sum(max(0, l["colour"] - l["inc_colour"]) for l in lines) * COL_RATE
    rental, credits = sum((D(str(l["rental"])) for l in lines), D(0)), sum((D(str(l["credit"])) for l in lines), D(0))
    taxable = max(D(0), rental + oma + oca - credits)
    gst = q(taxable * GST, "0.01")                                                        # BR-08
    return dict(customer_id=cid, name=st.customers[cid]["name"], month=month, lines=lines, pool_mono=pm, pool_colour=pc,
                use_mono=um, use_colour=uc, over_mono=om, over_colour=oc, over_mono_amt=float(oma), over_colour_amt=float(oca),
                overage=float(oma + oca), solo_overage=float(solo), rental=float(rental), credits=float(credits),
                taxable=float(taxable), gst=float(gst), total=int(q(taxable + gst)))


def invoices(st, month):
    return [invoice(st, c, month) for c in sorted(st.customers)]


def toner(st, month):                                   # BR-05, sorted by device then cartridge
    out = []
    for (did, m), r in sorted(st.readings.items()):
        if m != month or did not in st.devices: continue
        for c in CART:
            lv = r["toner_" + c]
            if lv <= 15:
                out.append(dict(month=month, customer_id=st.devices[did]["customer_id"], device_id=did, model=st.devices[did]["model"],
                                cartridge=c.upper(), level=lv, urgent=lv <= 5, urgency="URGENT" if lv <= 5 else "NORMAL"))
    return out


def utilisation(st, month, invs=None):
    out = []
    for inv in invs or invoices(st, month):
        for l in inv["lines"]:
            inc = l["inc_mono"] + l["inc_colour"]
            out.append(dict(month=month, device_id=l["device_id"], customer_id=inv["customer_id"], model=l["model"], days_installed=l["days"],
                            prorated_rental=l["rental"], included_mono=l["inc_mono"], included_colour=l["inc_colour"], mono_pages=l["mono"],
                            colour_pages=l["colour"], status=l["status"], utilisation_pct=l["util"],
                            used=l["mono"] + l["colour"], included=inc, pct=l["util"], rightsize=l["status"] == "OK" and l["util"] < 30))
    return sorted(out, key=lambda x: x["device_id"])


COLS = {
    "invoices.csv": "month,customer_id,devices_billed,rental_total,included_mono_pooled,included_colour_pooled,mono_pages,colour_pages,mono_overage_pages,colour_overage_pages,mono_overage_amount,colour_overage_amount,downtime_credits,taxable_amount,gst,invoice_total",
    "device_usage.csv": "month,device_id,customer_id,days_installed,prorated_rental,included_mono,included_colour,mono_pages,colour_pages,status,utilisation_pct",
    "toner_shipments.csv": "month,device_id,customer_id,cartridge,level_pct,urgency",
    "downtime_credits.csv": "ticket_id,device_id,month,hours_open,credit_days,credit_before_cap,credit"}


def inv_row(i):
    return [i["month"], i["customer_id"], len(i["lines"]), f2(i["rental"]), i["pool_mono"], i["pool_colour"], i["use_mono"], i["use_colour"],
            i["over_mono"], i["over_colour"], f2(i["over_mono_amt"]), f2(i["over_colour_amt"]), f2(i["credits"]), f2(i["taxable"]), f2(i["gst"]), i["total"]]


def use_row(u):
    return [u["month"], u["device_id"], u["customer_id"], u["days_installed"], f2(u["prorated_rental"]), u["included_mono"], u["included_colour"],
            u["mono_pages"], u["colour_pages"], u["status"], f"{u['utilisation_pct']:.1f}"]


def run_commands(cmd_path, outdir="output", log=print):
    base, st = os.path.dirname(os.path.abspath(cmd_path)), Store()
    loaders = {"LOAD_CUSTOMERS": "load_customers_csv", "LOAD_DEVICES": "load_devices_csv", "LOAD_READINGS": "load_readings_csv", "LOAD_TICKETS": "load_tickets_csv"}
    res = {k: {} for k in COLS}                        # file -> {month: rows}, keeps command order
    for no, line in enumerate(open(cmd_path, encoding="utf-8-sig"), 1):
        line = line.strip()
        if not line or line.startswith("#"): continue
        cmd, *a = [x.strip() for x in line.split("|")]
        try:
            if cmd in loaders:
                n = len(st.errors)
                with open(os.path.join(base, a[0]), encoding="utf-8-sig") as f: cnt = getattr(st, loaders[cmd])(f.read())
                log(f"OK {cmd} {a[0]}: {cnt} rows")
                for e in st.errors[n:]: log(e)
            elif cmd in ("BILL_MONTH", "PRINT_UTILISATION"):
                m = a[0]
                if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", m): raise ValueError(f"bad month '{m}', expected YYYY-MM")
                if cmd == "BILL_MONTH":
                    invs = invoices(st, m)
                    res["invoices.csv"][m] = [inv_row(i) for i in invs]
                    res["device_usage.csv"][m] = [use_row(u) for u in utilisation(st, m, invs)]
                    res["toner_shipments.csv"][m] = [[t["month"], t["device_id"], t["customer_id"], t["cartridge"], t["level"], t["urgency"]] for t in toner(st, m)]
                    res["downtime_credits.csv"][m] = [[t["ticket_id"], t["device_id"], t["month"], f"{t['hours_open']:.2f}", t["credit_days"], f2(t["credit_before_cap"]), f2(t["credit"])] for t in ticket_rows(st, m)]
                    log(f"BILL_MONTH {m}: {len(invs)} invoices, total Rs {sum(i['total'] for i in invs):,}")
                    for i in invs: log(f"  {i['customer_id']}  {i['name']:<30} Rs {i['total']:>8,}")
                else:
                    log(f"UTILISATION REPORT {m}")
                    log(f"{'device':8} {'customer':9} {'days':>4} {'rental':>9} {'inc_m':>6} {'inc_c':>6} {'mono':>6} {'colour':>6}  {'status':<12} {'util%':>6}")
                    for u in utilisation(st, m):
                        log(f"{u['device_id']:8} {u['customer_id']:9} {u['days_installed']:>4} {u['prorated_rental']:>9.2f} {u['included_mono']:>6} {u['included_colour']:>6} {u['mono_pages']:>6} {u['colour_pages']:>6}  {u['status']:<12} {u['utilisation_pct']:>6.1f}")
            else:
                log(f"ERROR line {no}: unknown command '{cmd}'")
        except Exception as e:
            log(f"ERROR line {no} ({line}): {type(e).__name__}: {e}")
    os.makedirs(outdir, exist_ok=True)
    for fn, cols in COLS.items():
        with open(os.path.join(outdir, fn), "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, lineterminator="\n"); w.writerow(cols.split(","))
            for rs in res[fn].values(): w.writerows(rs)
    log(f"Wrote {', '.join(COLS)} to {os.path.abspath(outdir)}")
