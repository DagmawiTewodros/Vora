# API overview

All endpoints are under `/api/` and return JSON. Authenticate with `POST /api/auth/login/` (username + password) or `POST /api/auth/pin/` (username + PIN), then send `Authorization: Bearer <access>`. Refresh with `POST /api/auth/refresh/`.

| Area | Endpoints |
|---|---|
| Auth & staff | `auth/login/`, `auth/pin/`, `auth/refresh/`, `auth/me/`, `staff/`, `staff/roles/` |
| Settings | `settings/` (GET, PATCH `settings/1/`), `exchange-rates/`, `exchange-rates/current/`, `calendar/today/`, `audit-log/` |
| Rooms | `room-types/`, `rooms/`, `rooms/{id}/out-of-order/`, `rooms/{id}/return-to-service/`, `rate-plans/` |
| Guests | `guests/?search=` |
| Reservations | `availability/?check_in=&check_out=&currency=`, `front-desk/`, `reservations/` (+ `confirm`, `cancel`, `no-show`, `check-in`, `prepare-check-out`, `check-out`, `move-room`, `free-rooms`, `moves`), `groups/` |
| Billing | `folios/` (+ `charges`, `payments`, `transfer`, `close`, `invoice`, `split`, `walk-in`), `charges/{id}/void/`, `payments/`, `shifts/` (+ `current`, `summary`, `close`) |
| Housekeeping | `housekeeping/rooms/` (+ `set-status`), `housekeeping/tasks/` (+ `start`, `complete`) |
| POS | `pos/outlets/`, `pos/categories/`, `pos/menu/`, `pos/orders/` (+ `items`, `send`, `settle`, `void`, `items/{id}/void`, `sync`), `pos/kitchen/`, `pos/kitchen/items/{id}/`, `pos/breakfast/` |
| Laundry | `laundry/prices/`, `laundry/tickets/` (+ `advance`, `cancel`) |
| Inventory | `inventory/items/` (+ `move`, `count`, `?low=true`), `inventory/recipes/`, `inventory/movements/`, `inventory/suppliers/`, `inventory/purchase-orders/` (+ `mark-ordered`, `receive`, `cancel`) |
| Reports | `reports/daily/`, `reports/summary/?start=&end=`, `reports/guest-register/`, `reports/breakfast/`, `reports/night-audit/run/`, `reports/night-audits/` |
| Channels | `channels/` (+ `push`, `stop-sell`), `channel-logs/`, `channels/webhook/{code}/` (OTA, secret header) |
| Public booking engine | `public/availability/?check_in=&check_out=&currency=`, `public/book/` (no login, rate limited) |

Money fields are strings with two decimals. All charges are stored in ETB; USD amounts keep the original amount and the exchange rate used.
