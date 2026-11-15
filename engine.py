"""Billing engine for ECE-038. Business rules BR-01..BR-08 are marked inline."""
import calendar, csv, io
from datetime import datetime, date
from decimal import Decimal as D, ROUND_HALF_UP

MONO_RATE, COL_RATE, GST = D("0.60"), D("4.50"), D("0.18")   # BR-04, BR-08
CTR = ("mono", "colour", "a3_mono", "a3_colour")
TONER = {"toner_k": "Black", "toner_c": "Cyan", "toner_m": "Magenta", "toner_y": "Yellow"}


def q(x, p="1"):
    return D(x).quantize(D(p), ROUND_HALF_UP)


def rows(text):
    return [{k.strip(): (v or "").strip() for k, v in r.items()} for r in csv.DictReader(io.StringIO(text.strip()))]


class Store:
    def __init__(s):
        s.clear()

    def clear(s):
        s.customers, s.devices, s.readings, s.tickets = {}, {}, {}, []

    def add_customer(s, c):
        s.customers[c["customer_id"]] = {"customer_id": c["customer_id"], "name": c.get("name") or c["customer_id"]}
        for d in c.get("devices", []):
            s.add_device({**d, "customer_id": c["customer_id"]})

    def add_device(s, d):
        n = {k: int(d.get(k) or 0) for k in ("inc_mono", "inc_colour", "open_mono", "open_colour", "open_a3_mono", "open_a3_colour")}
        n.update(device_id=d["device_id"], customer_id=d["customer_id"], model=d.get("model", ""),
                 rental=D(str(d["rental"])), install_date=str(d["install_date"])[:10])
        s.devices[n["device_id"]] = n
        s.customers.setdefault(n["customer_id"], {"customer_id": n["customer_id"], "name": n["customer_id"]})

    def add_reading(s, r):
        n = {k: int(r[k]) for k in CTR}
        n.update({k: (int(r[k]) if str(r.get(k, "")).strip() != "" else 100) for k in TONER})
        n.update(device_id=r["device_id"], month=r["month"][:7])
        s.readings[(n["device_id"], n["month"])] = n

    def add_ticket(s, t):
        p = lambda v: datetime.fromisoformat(v.strip().replace(" ", "T")) if v and v.strip() else None
        s.tickets.append({"device_id": t["device_id"], "opened": p(t["opened"]), "closed": p(t.get("closed"))})

    def load_readings_csv(s, text):
        for r in rows(text): s.add_reading(r)

    def load_tickets_csv(s, text):
        for r in rows(text): s.add_ticket(r)

    def load_devices_csv(s, text):
        for r in rows(text): s.add_device(r)

    def months(s):
        return sorted({m for (_, m) in s.readings})


def days_installed(dev, y, m, dim):                     # BR-07
    d = datetime.fromisoformat(dev["install_date"]).date()
    if d > date(y, m, dim): return 0
    return dim if d <= date(y, m, 1) else dim - d.day + 1   # installed on last day -> 1 day


def usage(st, dev, month):                              # BR-01, BR-02
    cur = st.readings.get((dev["device_id"], month))
    if not cur: return None
    prior = [m for (d, m) in st.readings if d == dev["device_id"] and m < month]
    p = st.readings[(dev["device_id"], max(prior))] if prior else {k: dev["open_" + k] for k in CTR}
    diff = {k: cur[k] - p[k] for k in CTR}
    if any(v < 0 for v in diff.values()): return {"error": True}   # equal reading -> 0 pages, valid
    return {"error": False, "mono": diff["mono"] + 2 * diff["a3_mono"], "colour": diff["colour"] + 2 * diff["a3_colour"]}


def invoice(st, cid, month):
    y, mo = map(int, month.split("-"))
    dim = calendar.monthrange(y, mo)[1]
    end = datetime(y + mo // 12, mo % 12 + 1, 1)
    lines = []
    for dev in (d for d in st.devices.values() if d["customer_id"] == cid):
        days = days_installed(dev, y, mo, dim)
        if not days: continue
        inc_m, inc_c = (int(q(D(dev[k]) * days / dim)) for k in ("inc_mono", "inc_colour"))
        rent = q(dev["rental"] * days / dim, "0.01")
        u, flag = usage(st, dev, month), None
        if u is None: m = c = 0; flag = "NO_READING"
        elif u["error"]: m, c, flag = inc_m, inc_c, "METER_ERROR"       # BR-01: bill included pages only
        else: m, c = u["mono"], u["colour"]
        credit, hrs = D(0), 0
        for t in st.tickets:                                              # BR-06
            if t["device_id"] == dev["device_id"] and t["opened"] and t["opened"].strftime("%Y-%m") == month:
                secs = int(((t["closed"] or end) - t["opened"]).total_seconds())
                hrs = max(hrs, secs // 3600)
                if secs > 48 * 3600: credit += 200 * ((secs - 48 * 3600) // 86400)
        credit = min(credit, dev["rental"])
        lines.append(dict(device_id=dev["device_id"], model=dev["model"], days=days, rental=float(rent), inc_mono=inc_m,
                          inc_colour=inc_c, mono=m, colour=c, flag=flag, credit=float(credit), ticket_hours=hrs))
    pm, pc = sum(l["inc_mono"] for l in lines), sum(l["inc_colour"] for l in lines)      # BR-03
    um, uc = sum(l["mono"] for l in lines), sum(l["colour"] for l in lines)
    om, oc = max(0, um - pm), max(0, uc - pc)
    overage = om * MONO_RATE + oc * COL_RATE                                              # BR-04
    solo = sum(max(0, l["mono"] - l["inc_mono"]) for l in lines) * MONO_RATE + sum(max(0, l["colour"] - l["inc_colour"]) for l in lines) * COL_RATE
    rental, credits = sum(D(str(l["rental"])) for l in lines), sum(D(str(l["credit"])) for l in lines)
    taxable = max(D(0), rental + overage - credits)
    gst = q(taxable * GST, "0.01")                                                        # BR-08
    return dict(customer_id=cid, name=st.customers[cid]["name"], month=month, lines=lines, pool_mono=pm, pool_colour=pc,
                use_mono=um, use_colour=uc, over_mono=om, over_colour=oc, overage=float(overage), solo_overage=float(solo),
                rental=float(rental), credits=float(credits), taxable=float(taxable), gst=float(gst), total=int(q(taxable + gst)))


def invoices(st, month):
    return [invoice(st, c, month) for c in sorted(st.customers)]


def toner(st, month):                                   # BR-05
    out = []
    for (did, m), r in st.readings.items():
        if m != month or did not in st.devices: continue
        for k, name in TONER.items():
            if r[k] <= 15:
                out.append(dict(customer_id=st.devices[did]["customer_id"], device_id=did, model=st.devices[did]["model"],
                                cartridge=name, level=r[k], urgent=r[k] <= 5))
    return sorted(out, key=lambda x: (not x["urgent"], x["level"], x["device_id"]))


def utilisation(st, month):
    out = []
    for inv in invoices(st, month):
        for l in inv["lines"]:
            inc = l["inc_mono"] + l["inc_colour"]
            pct = None if l["flag"] or not inc else round((l["mono"] + l["colour"]) * 100 / inc, 1)
            out.append(dict(customer_id=inv["customer_id"], device_id=l["device_id"], model=l["model"], used=l["mono"] + l["colour"],
                            included=inc, pct=pct, rightsize=pct is not None and pct < 30))
    return out