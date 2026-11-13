# QFlow

**Your place in line, without having to stand in it.**

QFlow is a small digital queue manager for busy campus service desks. A student can take a token on their phone, keep an eye on the live line, and get a rough idea of the wait. Staff can call the next person, mark a visit complete, or skip and recall a token from one dashboard. A public screen shows the queue without displaying anyone’s personal details.

It is built as a practical hackathon MVP with Flask, SQLite, plain HTML/CSS, and a little vanilla JavaScript. The goal is to make the queue work end to end and keep the setup approachable.

## What you can do

- Create an account and sign in with securely hashed passwords.
- Join an active campus service queue and receive a service-specific token such as `EX-001` or `LIB-001`.
- See your status, people ahead, counter assignment, and an estimated wait that updates every three seconds.
- Cancel a waiting or called token. You can have only one active token per service at a time.
- Use the admin dashboard to call, complete, skip, recall, or cancel tokens and to activate or deactivate counters.
- Put the public queue display on a shared screen; it shows token numbers and service/counter information, never student names.
- Review basic counts by service and completed-versus-skipped totals in the analytics view.
- Add sample departments and counters with one setup command.

## Get it running on Windows

You’ll need Python 3.10 or newer. From this folder, open PowerShell and run:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
$env:FLASK_APP = "app.py"
flask seed
flask run
```

Then visit <http://127.0.0.1:5000>. The first run creates `instance/qflow.db` automatically. The `flask seed` command adds the demo departments, one counter per department, and an administrator account.

Demo admin sign-in:

- Email: `admin@qflow.local`
- Password: `ChangeMe123!`

Change that password before showing the app on a shared network. For a real deployment, set a private random `SECRET_KEY` and `DEMO_ADMIN_PASSWORD` in your environment before seeding. The seeded password is for a local demo only.

To run locally with a chosen demo password before seeding:

```powershell
$env:DEMO_ADMIN_PASSWORD = "choose-a-private-password"
flask seed
```

## A quick judge demo

1. Sign in as the demo admin and leave the admin dashboard open in one window.
2. In a private browser window, create a student account and join the Examination Section queue.
3. Show the token and live position on the student dashboard; the public display is available at `/display`.
4. Return to the admin window and call the token. The student view changes on its next refresh.
5. Mark it complete, then open `/analytics` to see the updated real counts.

The seeded administrator credentials above are intentionally visible for a quick local demo. This is not intended as a production account setup flow.

## Project map

```text
app.py                 Flask app, models, authentication, queue and admin routes
requirements.txt       Python dependencies
.env.example           Environment variable template
instance/qflow.db      Created automatically on first run
static/css/style.css   Responsive styles
static/js/             Three-second student and public-display polling
templates/             Server-rendered pages
```

## Notes and current limits

- Queue positions are calculated from saved tokens on the server. Wait estimates use the service’s average minutes and active counter count; they are useful guidance, not a promise. This first MVP does not yet model each counter’s in-progress workload independently.
- SQLite serializes writes, and token sequences are unique per service. For a public, high-concurrency deployment, use a production database and add retry/locking around token creation.
- Notifications are stored in the database, and approaching/called/skipped messages are created. The UI currently shows the live token state; a dedicated notification inbox and browser notifications are not part of this MVP.
- The seed command creates an initial set of services and counters. Service creation/editing and adjustable service times are not exposed in the admin UI yet.
- The analytics page uses actual database counts. Historical peak-hour and counter-utilization charts are not implemented.
- CSRF protection is enabled for form posts. Use HTTPS and a strong environment-based secret key before deployment.

## Stack

Python · Flask · Flask-SQLAlchemy · SQLite · Flask-WTF CSRF protection · Werkzeug password hashing · HTML · CSS · Vanilla JavaScript · Chart.js
