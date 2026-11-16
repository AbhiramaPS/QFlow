# QFlow

QFlow is a simple appointment board for independent service providers and the people who book them. A provider publishes a service and available times; a customer requests a slot; the provider can confirm, decline, complete, or cancel the booking.

It works for tutoring, clinics, salons, repair services, consultations, and other appointment-based businesses.

## What is included

- Separate provider and customer registration and sign-in.
- Provider service listings, session lengths, pause/resume controls, and availability times.
- Customer browsing, booking requests, notes, and future appointment cancellation.
- Provider confirmation, decline, completion, and cancellation actions.
- Protection against claiming the same slot twice or overlapping a provider’s appointments.
- Hashed passwords, role-protected pages, and CSRF-protected form posts.
- “Add to Google Calendar” links and downloadable QR codes for customer appointments.
- Persistent PostgreSQL storage in production, with SQLite available for local development.
- Responsive browser interface for desktop and mobile screens.

## Live demo

The deployed application is available at [q-flow-five.vercel.app](https://q-flow-five.vercel.app).

The live flow has been checked end to end: provider registration, service creation, appointment-time creation, customer registration, booking, and QR/calendar-link access.

## Run locally on Windows

Install Python 3.10 or newer, then run these commands in PowerShell:

```powershell
cd D:\QFlow
py -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python -m flask --app app run --debug
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000). Keep the terminal open while using QFlow and press **Ctrl+C** to stop the server. Flask debug mode reloads Python changes automatically; refresh the browser after editing templates or CSS.

For a local demo database, set a strong `SECRET_KEY` in `.env` and run:

```powershell
.\.venv\Scripts\python -m flask --app app seed
```

The seed command creates:

- Provider: `admin@qflow.local` / `ChangeMe123!`
- Customer: `customer@qflow.local` / `ChangeMe123!`

These credentials are for local demonstrations only. Change them before sharing the application.

## Production deployment

QFlow is deployed through Vercel from the `main` branch of [AbhiramaPS/QFlow](https://github.com/AbhiramaPS/QFlow). A Neon PostgreSQL database is connected through Vercel Marketplace, and Vercel supplies `DATABASE_URL` to the application.

The application creates its tables automatically on startup. Do not rely on Vercel’s local filesystem for application data; the hosted PostgreSQL database is what keeps accounts, services, times, and reservations across requests and deployments.

## Google Calendar and QR codes

From **My bookings**, a customer can:

1. Select **Add to Google Calendar** to open a pre-filled Google Calendar event.
2. Select **Show QR code** and scan it with a phone to open the same event link.
3. Review the event and tap **Save** in Google Calendar.

The QR flow does not use Google OAuth, so it does not request direct calendar permission from QFlow. The customer completes the final save in Google Calendar.

## Project files

```text
app.py                 Flask routes, models, booking logic, and QR generation
requirements.txt       Python dependencies, including PostgreSQL and QR support
.env.example           Local environment-variable template
templates/             Public pages and provider/customer dashboards
static/css/style.css   Interface styles
instance/              Local SQLite database location when DATABASE_URL is not set
```

## Current limitations

- Providers add appointment times individually; recurring availability is not included.
- Appointment times are stored as local wall-clock times and currently assume one timezone.
- Calendar integration is a pre-filled Google Calendar link, not an OAuth-connected calendar account.
- There is no built-in email, SMS, push notification, payment, or platform-wide provider approval workflow yet.
