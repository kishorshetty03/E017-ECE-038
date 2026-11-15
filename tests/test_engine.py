import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import engine, sample

st = engine.Store(); sample.load(st)
inv = lambda c, m: engine.invoice(st, c, m)
line = lambda c, m, d: next(l for l in inv(c, m)["lines"] if l["device_id"] == d)
tk = lambda m: {t["ticket_id"]: t for t in engine.ticket_rows(st, m)}
ton = lambda m: {(t["device_id"], t["cartridge"]): t for t in engine.toner(st, m)}

def test_ec1_pooled_exact_equal():
    i = inv("CUST-001", "2026-09")
    assert i["pool_mono"] == i["use_mono"] == 5000 and i["over_mono"] == 0

def test_ec2_48h_and_72h():
    t = tk("2026-09")
    assert t["TKT-007"]["credit"] == 0 and t["TKT-008"]["credit"] == 200

def test_ec3_installed_last_day():
    l = line("CUST-006", "2026-10", "DEV-023")
    assert l["days"] == 1 and l["inc_mono"] == 65 and l["rental"] == 261.29

def test_ec4_toner_15_and_5():
    t = ton("2026-10")
    assert t[("DEV-027", "BLACK")]["urgency"] == "NORMAL" and t[("DEV-027", "CYAN")]["urgency"] == "URGENT"

def test_ec5_zero_pages_valid():
    assert line("CUST-003", "2026-10", "DEV-009")["status"] == "ZERO_PAGES"

def test_trap1_toner_16_and_6():
    t = ton("2026-10")
    assert not any(k[0] == "DEV-028" and v["level"] == 16 for k, v in t.items())
    assert any(k[0] == "DEV-028" and v["level"] == 6 and v["urgency"] == "NORMAL" for k, v in t.items())

def test_trap2_trap3_meter_errors():
    assert line("CUST-010", "2026-09", "DEV-042")["status"] == "METER_ERROR"
    l = line("CUST-010", "2026-10", "DEV-045")
    assert l["status"] == "METER_ERROR" and l["mono"] == l["inc_mono"]

def test_trap4_credit_cap():
    t = tk("2026-10")["TKT-009"]
    assert t["credit_before_cap"] == 3600 and t["credit"] == 3000

def test_trap5_invalid_ticket_rejected():
    assert any("TKT-004" in e for e in st.errors) and "TKT-004" not in {t["ticket_id"] for t in st.tickets}

def test_trap6_boundary_ticket_goes_to_closing_month():
    assert "TKT-005" in tk("2026-09") and "TKT-005" not in tk("2026-08")

def test_trap7_duplicate_reading_used_once():
    assert len(st.readings) == 132

def test_trap8_mid_month_installs():
    assert line("CUST-009", "2026-08", "DEV-040")["days"] == 16 and line("CUST-008", "2026-09", "DEV-037")["days"] == 21

if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_"): f(); print("PASS", n)
