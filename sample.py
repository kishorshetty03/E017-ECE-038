from engine import Store

DEVS = [("D101", "C1", "Ricoh MP C3003", 3000, 2000, 500, "2025-01-10"), ("D102", "C1", "Ricoh MP 2555", 2000, 3000, 0, "2025-01-10"),
        ("D201", "C2", "Canon iR-ADV C5535", 4500, 2500, 800, "2025-03-01"), ("D202", "C2", "HP LaserJet M880", 3500, 4000, 300, "2025-03-01"),
        ("D203", "C2", "Xerox AltaLink C8130", 5000, 1500, 1000, "2026-10-31"), ("D301", "C3", "Kyocera TASKalfa 4054ci", 2800, 1000, 300, "2025-06-15"),
        ("D302", "C3", "Brother MFC-L9570", 2200, 1000, 200, "2026-10-12")]
NAMES = {"C1": "Sunrise Legal LLP", "C2": "Orbit Logistics", "C3": "Greenleaf Clinic"}
USE = {"D101": {"2026-08": (1200, 150, 10, 5), "2026-09": (1100, 120, 0, 0), "2026-10": (2940, 100, 10, 5)},
       "D102": {"2026-08": (1500, 0, 0, 0), "2026-09": (-50, 0, 0, 0), "2026-10": (2040, 0, 0, 0)},
       "D201": {"2026-08": (1800, 300, 0, 0), "2026-09": (2000, 1000, 20, 10), "2026-10": (2200, 400, 0, 0)},
       "D202": {"2026-08": (3000, 100, 0, 0), "2026-09": (3100, 110, 0, 0), "2026-10": (3200, 90, 0, 0)},
       "D203": {"2026-10": (100, 20, 0, 0)},
       "D301": {"2026-08": (1500, 200, 0, 0), "2026-09": (1300, 220, 0, 0), "2026-10": (700, 400, 10, 5)},
       "D302": {"2026-10": (200, 50, 0, 0)}}
TONER = {("D101", "2026-10"): (15, 40, 60, 70), ("D102", "2026-10"): (5, 30, 50, 90), ("D201", "2026-10"): (14, 4, 50, 40),
         ("D301", "2026-10"): (16, 50, 12, 90)}
TICKETS = [("D101", "2026-10-01 09:00", "2026-10-03 09:00"), ("D201", "2026-10-02 10:00", "2026-10-05 10:00"),
           ("D301", "2026-10-05 08:00", "2026-10-09 20:00"), ("D202", "2026-09-03 09:00", "2026-09-04 09:00"),
           ("D102", "2026-09-10 09:00", "2026-09-26 09:00")]


def load(st: Store):
    for cid, n in NAMES.items(): st.customers[cid] = {"customer_id": cid, "name": n}
    for d, c, model, rent, im, ic, inst in DEVS:
        st.add_device(dict(device_id=d, customer_id=c, model=model, rental=rent, inc_mono=im, inc_colour=ic, install_date=inst))
    for d, months in USE.items():
        cum = [0, 0, 0, 0]
        for m, delta in months.items():
            cum = [a + b for a, b in zip(cum, delta)]
            t = TONER.get((d, m), (60, 55, 70, 80))
            st.add_reading(dict(device_id=d, month=m, mono=cum[0], colour=cum[1], a3_mono=cum[2], a3_colour=cum[3],
                                toner_k=t[0], toner_c=t[1], toner_m=t[2], toner_y=t[3]))
    for d, o, c in TICKETS: st.add_ticket(dict(device_id=d, opened=o, closed=c))