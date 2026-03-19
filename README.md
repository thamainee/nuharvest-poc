# Agri·cultur – Planting KPI Dashboard

## Quick Start

```bash
# 1. Install dependencies
pip install django openpyxl

# 2. Place your Excel file
mkdir data
cp planting_kpis.xlsx data/

# 3. Run the server
python manage.py runserver

# 4. Open http://127.0.0.1:8000
```

## Project Structure

```
ap/
├── agricult_project/
│   ├── settings.py       ← configure email & thresholds here
│   └── urls.py
├── planting/
│   ├── kpi_reader.py     ← reads Excel, calculates statuses
│   ├── alerts.py         ← sends HTML alert emails
│   ├── views.py
│   ├── urls.py
│   └── templates/planting/dashboard.html
├── data/
│   └── planting_kpis.xlsx   ← your Excel file goes here
├── manage.py
└── requirements.txt
```

## Excel File Format

The dashboard reads from **4 sheets** in `data/planting_kpis.xlsx`:

| Sheet | Columns |
|-------|---------|
| Cost_Per_Seedling | Week, Date, Weekly Labor Cost (R), Qty Seedlings Planted, Cost per Seedling (R), Status |
| Planting_Programme | Week, Planned Date, Actual Date, Weeks Behind, Status |
| Actual_vs_Target | Week, Date, Target Qty, Actual Qty, Achievement (%), Status |
| Dashboard_Summary | Auto-calculated summary |

The **Status column formulas** are pre-built – just update the data columns and they recalculate automatically.

## KPI Thresholds

| KPI | GREEN | ORANGE | RED |
|-----|-------|--------|-----|
| Cost per Seedling | ≤ R2.50 | ≤ R3.50 | > R3.50 |
| Planting Programme | On time | 1 week behind | 2+ weeks behind |
| Achievement % | ≥ 90% | ≥ 75% | < 75% |

Change thresholds in `agricult_project/settings.py` under `THRESHOLDS`.

## Email Alerts

Configure in `settings.py`:
```python
EMAIL_HOST_USER = 'your@gmail.com'
EMAIL_HOST_PASSWORD = 'your-app-password'   # Gmail App Password
ALERT_EMAIL_RECIPIENTS = ['manager@yourfarm.com']
```

Alerts fire automatically when the dashboard loads if any KPI is ORANGE or RED.
Click **📧 Email Alert** on the dashboard to send manually.

## Auto-scheduled Alerts (optional)

Use a cron job or Django management command to send daily digest:
```bash
# crontab: send every Monday at 7am
0 7 * * 1 cd /path/to/ap && python manage.py send_weekly_alerts
```
