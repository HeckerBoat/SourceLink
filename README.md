# SourceLink Resource Hosting Platform

A commercial virtual-resource hosting platform. Admins maintain resource blocks
(name, cloud-drive link, block password, third-party purchase link) in the admin
console; registered users browse the marketplace and must enter the block
password to reveal each resource's cloud-drive link.

- Backend: Python Flask (SQLModel over SQLite, JWT auth)
- Frontend: Vue 3 + Vite + Element Plus + Pinia
- Decoupled development, single entry point in production (Flask serves the built UI)

中文文档：[README_zh.md](README_zh.md)

---

## Features

- **Admin**: sign in as `admin`, create / edit / delete resource blocks, publish/unpublish,
  edit site settings, inspect unlock access logs and read all user feedback —
  both access logs and feedback entries can be deleted one by one or wiped in one click.
- **Resource block fields**: name, cloud-drive URL, block password, purchase URL — all editable.
- **Users**: register with either an SMS code or an email code (one is enough),
  then sign in with username / phone / email.
- **Slider captcha**: registration and first login from a new device require a
  drag-to-fill puzzle captcha (randomly generated server-side with Pillow,
  one-shot challenge + 5-minute ticket, ±6 px tolerance).
- **New-device protection**: the first sign-in from an unknown device requires the
  slider captcha and triggers an email risk alert (time / IP / device info);
  later logins from the same device skip the captcha (trusted-device table).
- **Idle session expiry**: tokens live for the `session_idle_minutes` site config
  (default 60, admin-adjustable between 5-10080 in the console, effective
  immediately; the `.env` value is only the first-run seed).
  Active sessions are silently renewed via the `X-Refresh-Token` response header;
  after N idle minutes the next request returns 401 and the UI redirects to login.
- **Profile page**: signed-in users can view account info and bind/change a phone
  number without an SMS code (format + uniqueness checks); accounts without an
  email can bind one after verifying an email code (`bind_email` purpose);
  both bound phone and email can be used to log in.
- **User feedback**: signed-in users can submit feedback and see their own entries;
  the admin sees all feedback (with submitter account) in the console.
- **Password-gated reveal**: the cloud-drive link is returned only after the correct
  block password is entered; one-click copy is provided.
- **Unlock once, view forever**: once a user has unlocked a block, reopening it
  skips the password prompt and shows the drive link directly (based on past
  successful unlock logs).
- **Purchase redirects**: each card links out to the third-party purchase page.
- **Verification controls**: SMS and email channels can be toggled independently;
  codes expire in 5 minutes, are rate-limited to one per 60 seconds, and are single-use.
- **Persisted site config**: site name, registration/channel switches and code
  parameters live in the database and are synced to the frontend at startup.
- **Resource TTL & auto-unpublish**: admins set a unified resource validity period
  (months / days / hours; all zeros = permanent). Creation dates are recorded,
  expiry is computed in real time, and expired resources are automatically
  unpublished, cannot be re-published, and cannot be unlocked.
- **Safe upgrades (migration)**: on startup the server back-fills missing `.env`
  keys from `.env.example` (existing values are never overwritten) and ALTERs
  existing SQLite tables to add missing columns (old data preserved); both
  operations back up the original file into `db/backups/` first.
- **Security**: passwords are double-hashed (SHA-256 with a server pepper, then
  salted PBKDF2-SHA256); JWT sessions; drive links are never exposed before unlock.
- **Mobile friendly**: responsive layout at 768 px breakpoint — single-column cards,
  collapsible admin menu, touch-friendly slider captcha.
- **Error handling**: full stack traces are logged on the backend terminal; the UI
  only shows lightweight toasts (no error pop-up dialogs).

## Tech Stack

| Layer | Tech |
| --- | --- |
| Frontend | Vue 3, Vue Router 4, Pinia, Element Plus, Axios, Vite 6 |
| Backend | Flask 3, SQLModel / SQLAlchemy, PyJWT, Flask-Cors, python-dotenv, Pillow |
| Database | SQLite (`db/sourcelink.db`) |
| Tooling | uv (Python 3.12), npm |

## Layout

```
SourceLink/
├── app.py                 # Single entry point
├── backend/               # Flask backend (api / services / models)
├── Frontend/              # Vue frontend source
│   └── dist/              # Build output (npm run build)
├── db/                    # SQLite database file
├── test/                  # API smoke tests + E2E scripts
├── SQLTable.md            # Database schema design (Chinese)
├── CloudConfig.md         # Cloud reverse-proxy setup guide (Chinese)
└── architecture.md        # File-by-file architecture index (Chinese)
```

---

## Quick Start

### 1. Prerequisites

- Python 3.12 (pinned via `uv python pin 3.12`)
- Node.js 18+ (verified on Node 22)
- [uv](https://docs.astral.sh/uv/)

### 2. Virtualenv & backend dependencies (PowerShell)

```powershell
uv venv
uv pip install -r requirements.txt
```

### 3. Environment file

```powershell
Copy-Item .env.example .env
```

Set `SECRET_KEY`, `PASSWORD_PEPPER`, `SESSION_IDLE_MINUTES` (first-run seed for
the idle-timeout site config; afterwards the admin console value wins), SMTP
credentials and SMS provider options as needed. A `.env` with random keys is
generated automatically on first run.

### 4. Install & build the frontend

```powershell
cd Frontend
npm install
npm run build
cd ..
```

For frontend development, run `npm run dev` (port 5173, `/api` is proxied to 5000).

### 5. Run

```powershell
.\.venv\Scripts\python.exe app.py
```

The first launch creates tables, seeds default config and the admin account. Open:

- Local: <http://127.0.0.1:5000>
- Public: <http://100.93.80.112:5000> (open port 5000 in your firewall)

### Default account

| Username | Password | Notes |
| --- | --- | --- |
| admin | `1q2w3e4r` | Administrator, bound to phone 11111111111 |

## SMS / Email verification

- **SMS** defaults to `console` mode: codes are printed in the backend terminal
  (e.g. `[SMS-console] ... code: 246810`), so registration works without a vendor
  account. Wire Aliyun/Tencent SMS in `backend/services/notifier.py` when ready.
- **Email**: the bundled `.env` is preconfigured for 163.com SMTP
  (`smtp.163.com:465`, POP3/SMTP authorization code) with `SMTP_ENABLED=true`,
  so real HTML code emails are sent; set it to `false` to fall back to terminal
  printing. Run `.\.venv\Scripts\python.exe test\test_email.py` to verify the
  mail pipeline end to end.

## API overview (prefix `/api`)

| Method | Path | Auth | Purpose |
| --- | --- | --- | --- |
| GET | `/config/public` | public | public site config |
| POST | `/captcha/new` | public | fetch a slider-puzzle captcha (challenge + slider image) |
| POST | `/captcha/verify` | public | submit the drag position; returns a one-shot `ticket` |
| POST | `/auth/register` | public | register (channel, target, code, password + `captcha_ticket`, `device_id`) |
| POST | `/auth/login` | public | login; unknown devices must pass `captcha_ticket` first (business code `4011` = need captcha) |
| GET | `/auth/me` | user | current profile |
| POST | `/auth/bind-phone` | user | bind/change phone (no SMS code needed) |
| POST | `/auth/bind-email` | user | bind email after verifying an email code |
| POST | `/verification/send` | mixed | send an SMS/email code (`purpose=register` public; `purpose=bind_email` requires login) |
| GET | `/resources` | user | published blocks (no drive URLs; includes `unlocked` flag) |
| POST | `/resources/<id>/unlock` | user | verify block password, return drive URL; previously-unlocked users may pass an empty password |
| GET/POST/PUT/DELETE | `/admin/resources[...]` | admin | resource CRUD |
| GET/PUT | `/admin/config` | admin | site config |
| GET | `/admin/logs` | admin | unlock audit logs |
| DELETE | `/admin/logs/<id>`, `/admin/logs` | admin | delete one / clear all access logs |
| GET/POST | `/feedback` | user | submit feedback / list entries (users see their own, admin sees all) |
| DELETE | `/feedback/<id>`, `/feedback` | admin | delete one / clear all feedback entries |

Response envelope: `{"code": 0, "msg": "success", "data": ...}` — non-zero `code`
indicates a business error.

## Tests

API smoke test (start the server first; 85 checks, creates and cleans its own data):

```powershell
.\.venv\Scripts\python.exe test\smoke_test.py
```

Migration test (standalone, no server needed; 13 checks for `.env` back-fill and
SQLite column migration with backups):

```powershell
.\.venv\Scripts\python.exe test\migrate_test.py
```

163.com SMTP end-to-end check (sends one test code email to the sender mailbox itself):

```powershell
.\.venv\Scripts\python.exe test\test_email.py
```

Browser E2E (puppeteer-core drives the system-installed Edge, no browser download):

```powershell
cd test/e2e
npm install
node admin-ui.mjs
node dialog-shot.mjs
node slider-captcha.mjs   # slider captcha: wrong drag / exact drag (white-box) / login flow
cd ../..
```

## Security notes

- Change `SECRET_KEY`, `PASSWORD_PEPPER` and the default admin password before going live.
- For production, serve behind waitress/gunicorn with an Nginx HTTPS reverse proxy.
- `.env`, `db/*.db`, `.venv/`, `node_modules/` and `dist/` are git-ignored.
