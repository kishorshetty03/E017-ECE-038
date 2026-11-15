# ECE-038 – Printer and Copier Managed-Print Billing Engine — Sample Data Pack

Prepared by 10 SECONDS for Team E017.

## Files

| File | What it holds | Row count |
|---|---|---|
| `customers.csv` | Customers (offices renting MFPs) | 10 |
| `devices.csv` | Rented devices with rental, included pages and opening meters | 45 |
| `meter_readings.csv` | Month-end meter readings and toner levels | 133 |
| `service_tickets.csv` | Service tickets (downtime) | 12 |
| `commands.txt` | Commands to process, in file order (comment lines start with #) | 8 commands |

## Column reference

Conventions: dates `YYYY-MM-DD`; timestamps `YYYY-MM-DD HH:MM:SS` (24h, IST, no timezone suffix); money in Rs as plain decimals (no commas, no symbol); percentages as plain numbers (12.5 = 12.5%); booleans `true`/`false`; IDs uppercase with a fixed prefix.

### customers.csv
| column | type | units / format | allowed values | notes |
|---|---|---|---|---|
| customer_id | string | `CUST-nnn` | unique | |
| name | string | | | |
| city | string | | | |

### devices.csv
| column | type | units / format | allowed values | notes |
|---|---|---|---|---|
| device_id | string | `DEV-nnn` | unique | |
| customer_id | string | | from customers.csv | pooling is per customer |
| model | string | | | |
| monthly_rental | decimal | Rs | | cap for downtime credit |
| included_mono | integer | pages/month | | pro-rated for mid-month installs |
| included_colour | integer | pages/month | | |
| installation_date | date | YYYY-MM-DD | | days installed in a month count the installation day |
| opening_mono, opening_colour, opening_a3_mono, opening_a3_colour | integer | meter counts | | the "previous reading" for the first billed month after installation |

### meter_readings.csv
| column | type | units / format | allowed values | notes |
|---|---|---|---|---|
| device_id | string | | from devices.csv | one row per device per month end (one duplicate planted) |
| reading_date | date | YYYY-MM-DD | 2026-08-31, 2026-09-30, 2026-10-31 | month-end reading |
| mono, colour, a3_mono, a3_colour | integer | cumulative meter counts | | pages = current − previous; A3 counts 2 pages in its colour class; lower than previous → METER_ERROR |
| toner_black_pct, toner_cyan_pct, toner_magenta_pct, toner_yellow_pct | integer | percent | 0–100 | ≤ 15 ship; ≤ 5 URGENT |

### service_tickets.csv
| column | type | units / format | allowed values | notes |
|---|---|---|---|---|
| ticket_id | string | `TKT-nnn` | unique | |
| device_id | string | | from devices.csv | |
| opened_at | timestamp | YYYY-MM-DD HH:MM:SS | | |
| closed_at | timestamp | YYYY-MM-DD HH:MM:SS | | one planted ticket closes before it opens (invalid) |
| issue | string | | | informational |

## Command file format

One command per line, `COMMAND_NAME|arg1|...`; lines starting with `#` are comments. Commands must be processed in file order.

| command | arguments | meaning |
|---|---|---|
| `LOAD_CUSTOMERS` / `LOAD_DEVICES` / `LOAD_READINGS` / `LOAD_TICKETS` | file | load the named file |
| `BILL_MONTH` | YYYY-MM | compute usage, overage, credits and invoices for that month (previous reading = prior month end, or opening meters) |
| `PRINT_UTILISATION` | YYYY-MM | print the device utilisation report for that month |

## Planted scenarios

Every edge case in the brief (EC1…) plus extra traps (TRAP1…). Line numbers count the header as line 1.

- **EC1** – Customer whose pooled mono usage exactly equals pooled included pages — CUST-001 in 2026-09: included 3000 + 2000 = 5000; usage 2800 + 2×50 A3 + 2100 = 5000 → zero mono overage (readings dated 2026-09-30) → `devices.csv` line 2 (DEV-001); `devices.csv` line 3 (DEV-002)
- **EC2** – Ticket open for exactly 48 hours and for 72 hours — 48 h → no credit; 72 h → exactly 1 full 24 h beyond 48 → Rs 200 → `service_tickets.csv` line 8 (TKT-007); `service_tickets.csv` line 9 (TKT-008)
- **EC3** – Device installed on the last day of the month — installed 2026-10-31 → 1/31 of rental and included pages in October (install day counts as installed) → `devices.csv` line 24 (DEV-023)
- **EC4** – Toner at exactly 15% and exactly 5% — 2026-10-31 reading: black 15% (ship, NORMAL) and cyan 5% (URGENT) → `meter_readings.csv` lines 27, 70, 116 (DEV-027)
- **EC5** – Meter reading equal to previous reading (zero pages, valid) — 2026-10-31 reading equals 2026-09-30 reading on every counter → 0 pages, valid → `meter_readings.csv` lines 10, 53, 97 (DEV-009)
- **TRAP1** – toner 16% and 6% → 16 not shipped, 6 shipped but not URGENT → `meter_readings.csv` lines 28, 71, 117 (DEV-028)
- **TRAP2** – METER_ERROR: mono reading 2026-09-30 lower than 2026-08-31 → `meter_readings.csv` lines 41, 85, 131 (DEV-042)
- **TRAP3** – METER_ERROR: colour reading 2026-10-31 lower than 2026-09-30 → `meter_readings.csv` lines 44, 88, 134 (DEV-045)
- **TRAP4** – downtime credit 20 days (18 full days beyond 48 h = 3600) capped at the device rental 3000 → `service_tickets.csv` line 10 (TKT-009)
- **TRAP5** – ticket closed before it was opened — invalid, reject with an error line → `service_tickets.csv` line 5 (TKT-004)
- **TRAP6** – ticket spanning the Aug/Sep month boundary — brief is silent on which month takes the credit; document your choice → `service_tickets.csv` line 6 (TKT-005)
- **TRAP7** – duplicate 2026-10-31 reading row for one device — use it once → `meter_readings.csv` lines 22, 65, 109, 110 (DEV-021)
- **TRAP8** – mid-month installs 2026-08-16 and 2026-09-10 (pro-rata by days installed / days in month) → `devices.csv` line 41 (DEV-040); `devices.csv` line 38 (DEV-037)

## What is NOT in this pack

Expected outputs are not provided for this set. Validate your engine with your own test suite against the rules in your brief (BR-01 … BR-nn). A separate hidden input set with the same schema will be used at final evaluation; outputs are compared field-for-field, so follow the column formats above exactly in your own output.

## Output format expected at evaluation

**`invoices.csv`** — one row per customer per BILL_MONTH:
`month, customer_id, devices_billed, rental_total, included_mono_pooled, included_colour_pooled, mono_pages, colour_pages, mono_overage_pages, colour_overage_pages, mono_overage_amount, colour_overage_amount, downtime_credits, taxable_amount, gst, invoice_total`
- taxable_amount = rental_total + overage − credits; invoice_total rounded to the nearest rupee (0 decimals).

**`device_usage.csv`** — one row per device per month (the utilisation report):
`month, device_id, customer_id, days_installed, prorated_rental, included_mono, included_colour, mono_pages, colour_pages, status, utilisation_pct`
- status = OK / METER_ERROR / ZERO_PAGES; utilisation_pct = (mono_pages + colour_pages) / (included_mono + included_colour) × 100 to 1 decimal.

**`toner_shipments.csv`** — `month, device_id, customer_id, cartridge, level_pct, urgency` (cartridge = BLACK/CYAN/MAGENTA/YELLOW; urgency = NORMAL/URGENT), sorted by device then cartridge.

**`downtime_credits.csv`** — `ticket_id, device_id, month, hours_open, credit_days, credit_before_cap, credit` (one row per valid ticket; rejected tickets go to an error line).
