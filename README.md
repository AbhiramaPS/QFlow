# QFlow

QFlow helps campus service providers and customers arrange appointments without a long chain of messages. Providers describe what they offer and publish the times they are free. Customers browse those listings and request a time. Providers can confirm or decline, and both sides can check the booking in their own account.

This is a small Flask and SQLite project for a college demo. The main flow is: list a service, add an open time, request it, and confirm the reservation.

## What it can do

- Separate provider and customer registration and sign-in.
- Providers can add or pause listings, set session lengths, and publish times.
- Customers can browse services, request an open slot, leave a note, and cancel a future booking.
- Providers can confirm, decline, complete, or cancel reservations.
- Each time slot can only be claimed once. Overlapping bookings for one provider are blocked.
- Passwords are hashed, role-specific pages are protected, and form posts use CSRF protection.
- SQLite data is stored in `instance/qflow.db`, created automatically on first run.

## Run on Windows

Install Python 3.10 or newer. In PowerShell:

```powershell
cd D:\QFlow
py -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env` and set a long random `SECRET_KEY` and private demo passwords. Then seed sample accounts/listings and start the app:

```powershell
$env:FLASK_APP = "app.py"
flask seed
flask run --debug
```

Open <http://127.0.0.1:5000>. Leave the terminal open while using QFlow; press **Ctrl+C** to stop Flask. Debug mode reloads Python changes. Refresh after editing templates or styles; use **Ctrl+F5** if the browser keeps an old stylesheet.

On a fresh database, the seed command creates a provider, a customer, two sample listings, and appointment times for tomorrow. The example `.env` uses these demo sign-ins; if you changed the demo password values, use your chosen passwords instead:

- Provider: `admin@qflow.local` / `ChangeMe123!`
- Customer: `customer@qflow.local` / `ChangeMe123!`

These passwords are for local demos only. Change them before sharing or deploying the app.

## Quick demo

1. Sign in as the demo provider, add a service, and publish an appointment time.
2. Sign in as the demo customer, browse the service, and request that time.
3. Return to the provider account and confirm the request.
4. Check the customer's dashboard to see the confirmed reservation.

## Project files

```text
app.py                    Flask app, database models, and routes
requirements.txt          Python dependencies
.env.example              Environment variable template
templates/                Public pages and provider/customer dashboards
static/css/style.css      Responsive interface styles
instance/qflow.db         Created automatically on first run
```

## Current limits

- Providers enter times one at a time. Recurring availability and calendar export are not included.
- Appointment times use the computer’s local time for this single-campus MVP.
- A larger deployment should use a production database and add email or push notifications.
- Old queue-era tables are left in existing databases, but the reservation flow uses the new provider, offering, slot, and reservation tables.
- Provider and customer accounts are self-serve; there is no platform-wide approval process or payment handling yet.
