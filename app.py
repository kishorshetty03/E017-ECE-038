import os
from flask import Flask, jsonify, request, send_from_directory
import engine, sample

HERE = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, static_folder=os.path.join(HERE, "static"), static_url_path="/static")
st = engine.Store()


def body_text():
    return request.files["file"].read().decode("utf-8-sig") if "file" in request.files else request.get_data(as_text=True)


def counts():
    return dict(customers=len(st.customers), devices=len(st.devices), readings=len(st.readings), tickets=len(st.tickets), months=st.months())


def month_arg():
    if not st.readings: sample.load(st)   # serverless instances start empty, so fall back to demo data
    return request.args.get("month") or st.months()[-1]


@app.get("/")
def home(): return send_from_directory(os.path.join(HERE, "static"), "index.html")

@app.post("/api/sample")
def load_sample(): st.clear(); sample.load(st); return jsonify(counts())

@app.post("/api/customers")
def add_customer():
    for c in (request.get_json() if isinstance(request.get_json(), list) else [request.get_json()]): st.add_customer(c)
    return jsonify(counts()), 201

@app.post("/api/devices")
def add_devices(): st.load_devices_csv(body_text()); return jsonify(counts()), 201

@app.post("/api/readings")
def add_readings(): st.load_readings_csv(body_text()); return jsonify(counts()), 201

@app.post("/api/tickets")
def add_tickets(): st.load_tickets_csv(body_text()); return jsonify(counts()), 201

@app.get("/api/state")
def state():
    if not st.readings: sample.load(st)
    return jsonify(counts())

@app.post("/api/bill")
def bill():
    """Stateless one-shot billing (use this on Vercel). JSON: {month, customers:[...], readings_csv, tickets_csv}"""
    j = request.get_json()
    s = engine.Store()
    for c in j["customers"]: s.add_customer(c)
    s.load_readings_csv(j["readings_csv"])
    if j.get("tickets_csv"): s.load_tickets_csv(j["tickets_csv"])
    m = j.get("month") or s.months()[-1]
    return jsonify(month=m, invoices=engine.invoices(s, m), shipments=engine.toner(s, m), utilisation=engine.utilisation(s, m))

@app.get("/api/invoices")
def invoices(): m = month_arg(); return jsonify(month=m, invoices=engine.invoices(st, m))

@app.get("/api/toner")
def toner(): m = month_arg(); return jsonify(month=m, shipments=engine.toner(st, m))

@app.get("/api/utilisation")
def util(): m = month_arg(); return jsonify(month=m, devices=engine.utilisation(st, m))

@app.errorhandler(Exception)
def fail(e): return jsonify(error=f"{type(e).__name__}: {e}"), 400


if __name__ == "__main__":
    app.run(debug=True, port=5000)
