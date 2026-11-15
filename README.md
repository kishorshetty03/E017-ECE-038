# E017-ECE-038 Printer and Copier Managed-Print Billing Engine
Python 3.10+ / Flask. Command-file driven engine (`run.py`) plus a colourful dashboard and REST API.

## Run (command file, what the evaluator uses)
    pip install -r requirements.txt
    python run.py data/commands.txt output
Writes `invoices.csv`, `device_usage.csv`, `toner_shipments.csv`, `downtime_credits.csv` into `output/`. Error lines (e.g. rejected tickets) are printed to the console.
To evaluate another input set, put its CSVs and commands.txt in a folder and run `python run.py <folder>/commands.txt`.

## Dashboard and API
    python app.py     # http://localhost:5000 (reads the CSVs in data/)
GET /api/invoices?month=2026-10, /api/toner?month=..., /api/utilisation?month=...; POST /api/bill (stateless, JSON).

## Tests
    python tests/test_engine.py     # one test per edge case EC1-EC5 and trap TRAP1-TRAP8

## Business rules
BR-01 pages = current minus previous per counter (previous = prior month-end reading, else opening meters); lower reading = METER_ERROR, device billed at its included pages only. BR-02 A3 = 2 pages in its class.
BR-03 included pages pooled per customer, overage on the pooled total. BR-04 overage Rs 0.60 mono / Rs 4.50 colour. BR-05 toner <=15% ship (NORMAL), <=5% URGENT.
BR-06 credit Rs 200 per full 24h beyond 48h, capped at the device monthly rental. BR-07 mid-month install pro-rated by days installed / days in month (install day counts), pages rounded half-up, rental to 2 decimals.
BR-08 GST 18% on rental + overage - credits (GST to 2 decimals), invoice total rounded half-up to the rupee.

## Decisions to record in the decision log
1. A ticket's credit is booked in the month it is closed (TRAP6: TKT-005 opened 30 Aug, closed 2 Sep, so it is credited in September).
2. A meter-error device contributes its included pages as usage (no overage); utilisation shows 100.0. The erroneous reading remains the baseline for the next month.
3. Duplicate reading rows for the same device and month: the first one is used.
4. Invalid tickets (closed before opened) are rejected with an ERROR line and produce no credit row.
5. Credit cap is applied per ticket and again per device per month.
6. Status ZERO_PAGES = valid reading with 0 pages; devices installed after the month end are not billed that month.
