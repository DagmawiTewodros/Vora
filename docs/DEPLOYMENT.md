# Deployment

The production stack is in `docker-compose.yml`: PostgreSQL 16, Redis, the Django API under gunicorn, nginx serving the PWA and proxying `/api` and `/admin`, and a nightly backup job.

## First install

```bash
cp .env.example .env          # set POSTGRES_PASSWORD, DJANGO_SECRET_KEY, hosts
docker compose up -d --build
docker compose exec backend python manage.py createsuperuser
# Optional: demo data to train staff on a test server (not production)
docker compose exec backend python manage.py seed_demo
```

Generate a secret key with `python -c "import secrets; print(secrets.token_urlsafe(50))"`.

Put a TLS terminator in front (Caddy, Traefik, or a cloud load balancer) and point `hms.<hotel-domain>` at it. The app sets secure cookies when `DJANGO_DEBUG=0`; set `SECURE_COOKIES=0` only for plain HTTP on a closed hotel LAN.

## Where to host

The plan suggests AWS Cape Town (af-south-1) or a local data centre. One small VM (2 vCPU, 4 GB) runs the whole stack for a hotel of this size; a managed PostgreSQL can replace the `db` service by pointing `DATABASE_URL` at it.

## Go-live checklist (from the plan)

1. In the admin or Settings screen: hotel TIN, VAT registration number, VAT and service charge rates, whether prices include tax, invoice prefix, business date.
2. Load room types, rooms and rate plans; menus per outlet; laundry prices; staff with roles and PINs.
3. Enter today's USD rate (Settings → Exchange rate). USD postings are refused without one.
4. Import future bookings from the current system (Reservations → New, or a script against `/api/reservations/`).
5. Train each department on its own screens; run in parallel with the old process for a week.
6. On switch-over day, tick **Stop sell** on each OTA channel, then untick after the first availability push.
7. Run the night audit every night (Dashboard → Run night audit).

## Backups

The `backup` service writes `vora-YYYYMMDD-HHMM.sql.gz` to the `backups` volume every night at 03:00 Addis time and keeps 14 days (`BACKUP_KEEP_DAYS`). For the off-site copy, sync that volume to S3 or another site, for example with a host cron job:

```bash
docker run --rm -v vora_backups:/backups -e AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY amazon/aws-cli s3 sync /backups s3://<bucket>/vora/
```

Restore: `gunzip -c vora-....sql.gz | docker compose exec -T db psql -U vora vora`.

## Offline operation

Tablets and front desk PCs install the app from the browser ("Add to home screen" / "Install"). When the internet drops:

- The app, menus, rooms and the front desk board stay readable from the cache.
- POS orders are saved on the device and sent automatically when the connection returns; each order carries a unique id so resending never charges twice. Room numbers are checked on sync, and failed orders stay in the queue with the error shown.
- Check-in, check-out and payments need the server. For full front-desk operation during outages, run the stack on a small server in the hotel (same compose file) and keep a UPS on it, as the plan's risk table recommends.

## Fiscal printer

`backend/apps/billing/fiscal.py` defines the hook called when an invoice is issued. Write a driver class with `register_invoice(invoice) -> fiscal_receipt_number` for the hotel's approved device and set `FISCAL_DRIVER=apps.billing.drivers.YourDriver`.

## OTA / channel manager

Each channel (Settings → Channels) has a webhook URL `/api/channels/webhook/<code>/` authenticated with the `X-Vora-Secret` header (the secret is in the admin). Payload:

```json
{
  "reference": "EXP-123456", "status": "confirmed",
  "room_type": "DLX", "check_in": "2026-11-02", "check_out": "2026-11-05",
  "adults": 2, "children": 0, "currency": "USD", "nightly_rate": "95.00",
  "guest": {"first_name": "Jane", "last_name": "Doe", "email": "...", "phone": "...", "nationality": "GB"},
  "special_requests": ""
}
```

Send the same reference with `"status": "cancelled"` to cancel. Outbound availability is built by `distribution.services.availability_payload`; add the provider's HTTP call in `distribution.services.send`.
