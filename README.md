# Vora Addis Hotel Management System

One web system for Vora Addis Hotel (Jomo Kenyatta Street, Kirkos, Addis Ababa) that runs rooms, restaurant, bar, café, laundry and billing, built from the [implementation plan](docs/IMPLEMENTATION_PLAN.md).

- **One guest folio.** Room, restaurant, bar, café, minibar and laundry charges all land on the guest's bill, which becomes a sequentially numbered tax invoice.
- **No double bookings.** Walk-ins, phone bookings, the website booking engine and OTAs all book against one availability table, locked per room type.
- **Shared room status.** Front desk and housekeeping see the same live room rack; check-out marks a room dirty and creates the cleaning task.
- **Ethiopian invoicing.** VAT and service charge on every line, hotel and buyer TIN, ETB base with USD at the daily rate, Ethiopian date, and a fiscal-device hook.
- **Owner reports.** Occupancy, ADR, RevPAR, revenue by outlet, payments by method, night audit, cashier shift close and the police guest register.

| Screen | |
|---|---|
| Front desk | ![Front desk](docs/screenshots/front-desk.png) |
| Guest folio | ![Folio](docs/screenshots/folio.png) |
| Restaurant POS | ![POS](docs/screenshots/pos.png) |
| Housekeeping on a phone | <img src="docs/screenshots/housekeeping-phone.png" width="260" alt="Housekeeping on a phone"> |

## What is in the box

| Module | Status | Where |
|---|---|---|
| Reservations (calendar, rate plans, deposits, groups, cancellations, no-shows) | Done | `backend/apps/reservations`, `rooms` |
| Front desk (check-in/out, room assignment, registration, room moves, key cards) | Done | `backend/apps/reservations` |
| Guest folio & billing (split bills, deposits, refunds, ETB/USD, invoices, shifts) | Done | `backend/apps/billing` |
| Housekeeping (dirty / clean / inspected / out of order, tasks, phone view) | Done | `backend/apps/housekeeping` |
| Restaurant, bar & café POS (orders, kitchen screen, post to room, breakfast) | Done | `backend/apps/pos` |
| Laundry & dry cleaning (intake, pricing, express, post to room) | Done | `backend/apps/laundry` |
| Inventory & purchasing (stock, recipes, purchase orders, counts) | Done | `backend/apps/inventory` |
| Reports & dashboard (KPIs, night audit, shift close, guest register) | Done | `backend/apps/reports` |
| Channel manager & booking engine | Built; needs the hotel's provider API | `backend/apps/distribution` |
| Staff, roles & audit log (PIN login, per-role permissions, before/after log) | Done | `backend/apps/core` |

See [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md#build-status) for what still needs the hotel's input (room count, fiscal printer model, OTA provider, accountant sign-off).

## Stack

- **Backend:** Django 5.1 + Django REST Framework, PostgreSQL (SQLite for quick local runs), Redis cache, JWT auth.
- **Frontend:** React 18 + TypeScript + Vite, installable PWA with an offline POS queue. The plan suggested Next.js; a Vite single-page app was chosen because the system is a logged-in staff tool with no server-rendered pages, and it keeps the offline service worker simple.
- **Deploy:** Docker Compose (Postgres, Redis, gunicorn, nginx, nightly backups). See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

## Run it locally

You need Python 3.12+ and Node 20+.

```bash
# Backend: http://127.0.0.1:8000 (admin at /admin)
cd backend
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo        # demo rooms, rates, menus, staff
python manage.py runserver

# Frontend: http://localhost:5173 (proxies /api to Django)
cd frontend
npm install
npm run dev
```

Demo logins (from `seed_demo`; change them before real use):

| User | Role | PIN | Password |
|---|---|---|---|
| `admin` | Admin (Django admin too) | – | `admin12345` |
| `manager` | Manager | 1111 | `vora12345` |
| `frontdesk` | Front desk | 2222 | `vora12345` |
| `cashier` | Cashier | 3333 | `vora12345` |
| `housekeeper` | Housekeeping | 4444 | `vora12345` |
| `waiter` | Waiter | 5555 | `vora12345` |
| `laundry` | Laundry | 6666 | `vora12345` |
| `store` | Store keeper | 7777 | `vora12345` |
| `revenue` | Revenue manager | 8888 | `vora12345` |

Room types, room numbers, prices and the menu in the seed are placeholders until the hotel confirms the real figures.

**Hotel logo:** put it at `frontend/public/brand/logo.svg` (or `logo.png`, ideally with a transparent background). It then appears in the sidebar, on the sign-in screen and as the faint watermark behind every page. Until a file is there, the hotel name is shown as a typeset wordmark.

## Tests

```bash
cd backend && . .venv/bin/activate
ruff check .
python manage.py test tests                                   # SQLite
DATABASE_URL=postgres://user:pass@localhost/vora python manage.py test tests   # PostgreSQL

cd frontend && npm run build                                  # typecheck + production build
```

The 55 backend tests cover the double-booking guard, check-in/out, VAT and service charge maths, USD conversion, split bills, invoice numbering, POS post-to-room and offline sync, laundry billing, housekeeping flow, night audit KPIs, OTA webhooks and the booking engine. CI runs them on every push (`.github/workflows/ci.yml`).

## A day at the hotel

1. **Front desk** sees today's arrivals, checks a guest in (ID/passport and visa are required; dirty rooms are blocked), and hands over key cards.
2. **Waiters** take orders on a tablet; food goes to the kitchen screen, drinks don't. "Post to room 204" lands each line on the guest's folio with service charge and VAT. If the internet drops, orders queue on the tablet and sync later without double-charging.
3. **Laundry** logs items against the room; delivery posts the charge.
4. **Housekeeping** works from a phone: tasks appear when guests check out, and marking a room clean or inspected updates the front desk instantly.
5. **Night audit** (manager, end of day) posts room nights, flags no-shows, freezes the day's KPIs and moves the business date forward.
6. **Check-out** posts any remaining nights, takes payment (cash, card, Telebirr, CBE Birr, bank transfer or company account) and closes the folio into a numbered tax invoice.

## Project layout

```
backend/
  apps/core           staff, roles, PIN login, hotel settings, exchange rates, audit log, Ethiopian calendar
  apps/rooms          room types, rooms, rate plans
  apps/guests         guest profiles and registration details
  apps/reservations   bookings, availability, check-in/out, room moves
  apps/billing        folios, charges, payments, cashier shifts, invoices, fiscal hook
  apps/housekeeping   room status and cleaning tasks
  apps/pos            outlets, menu, orders, kitchen tickets, breakfast log, offline sync
  apps/laundry        price list and tickets
  apps/inventory      stock, recipes, suppliers, purchase orders
  apps/reports        KPIs, night audit, guest register
  apps/distribution   OTA channels, webhook, booking engine
  tests/              API-level tests
frontend/src
  pages/              one file per screen
  components/         layout, modals, reservation form, cashier shift bar
  lib/                API client, auth, i18n (English/Amharic), offline queue
docs/                 plan, deployment guide, API overview, screenshots
```
