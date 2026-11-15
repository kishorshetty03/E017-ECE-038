import os

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
FILES = (("customers.csv", "load_customers_csv"), ("devices.csv", "load_devices_csv"),
         ("meter_readings.csv", "load_readings_csv"), ("service_tickets.csv", "load_tickets_csv"))


def load(st):
    """Load the official data pack from the data/ folder (used by the website and API)."""
    for fn, method in FILES:
        with open(os.path.join(DATA, fn), encoding="utf-8-sig") as f:
            getattr(st, method)(f.read())
