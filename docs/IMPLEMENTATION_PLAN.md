# Vora Addis HMS – Implementation Plan

This is the plan the system is built from (original: [Vora_Addis_HMS_Implementation_Plan.docx](Vora_Addis_HMS_Implementation_Plan.docx)). The [build status](#build-status) at the end maps each part of the plan to the code.

22 October 2026 · Prepared by Dagmawi

## Overview

A single web-based system can run Vora Addis's rooms, restaurant, bar,
café, laundry and billing in about 5 months, delivered in four phases
with the front desk live by month 3.

Vora Addis is a 3-star hotel on Jomo Kenyatta Street in Kirkos, Addis
Ababa, a 15-minute walk from the ECA Conference Center and Meskel
Square. It lists five room types, free breakfast, a restaurant, bar,
café, laundry/dry cleaning, parking and a daily manager's reception,
and it sells through online travel agencies such as Expedia.

Goals of the system:

-   One guest folio: room, restaurant, bar, café and laundry charges all
    land on the guest's bill

-   No double bookings between walk-ins, phone bookings and OTAs

-   Real-time room status shared by front desk and housekeeping

-   ERCA-compliant invoicing in ETB, with USD for foreign guests

-   Daily owner reports: occupancy, ADR, RevPAR, revenue by outlet

Room count, staff numbers and current tools are not public yet; they are
listed as open questions at the end.

## Scope: modules

Ten modules, split into must-have for go-live and later additions.

  ----------------------------------------------------------------------------
  **Module**      **What it does**                 **Users**       **Phase**
  --------------- -------------------------------- --------------- -----------
  Reservations    Calendar, rate plans, deposits,  Front desk,     1
                  group and corporate bookings,    sales           
                  cancellations                                    

  Front desk      Check-in/out, room assignment,   Receptionists   1
                  guest registration, passport                     
                  scan, key handover                               

  Guest folio &   One bill per stay, split bills,  Front desk,     1
  billing         deposits, refunds, ETB/USD       cashier         

  Housekeeping    Room status (dirty, clean,       Housekeepers,   2
                  inspected, out of order), task   supervisor      
                  lists, mobile view                               

  Restaurant, bar Orders, kitchen tickets, post to Waiters,        2
  & café POS      room, breakfast tracking         cashier         

  Laundry & dry   Item intake, pricing, post to    Laundry staff   2
  cleaning        room                                             

  Inventory &     Stock for kitchen, bar, minibar, Store keeper    3
  purchasing      amenities; supplier orders                       

  Reports &       Occupancy, ADR, RevPAR, outlet   Manager, owner  1--3
  dashboard       sales, night audit, cashier                      
                  shift close                                      

  Channel manager Sync availability and rates with Revenue manager 3
  & booking       Expedia/Booking.com; direct                      
  engine          bookings on the hotel website                    

  Staff, roles &  Users, permissions per role, who Admin           1
  audit log       changed what                                     
  ----------------------------------------------------------------------------

Out of scope for v1: payroll and full accounting (export to the hotel's
accounting software instead), door-lock integration, and a guest mobile
app.

## Ethiopia-specific requirements

These are what make a local system worth more than an imported PMS;
confirm each with the hotel's finance team and accountant.

-   **Tax invoicing:** VAT and service charge on every bill, TIN on
    invoices, and a plan for the Ministry of Revenues' fiscal device /
    e-invoicing rules (confirm the current requirement before build)

-   **Currencies:** ETB as base, USD price display and payment for
    foreign guests, daily exchange rate entered by finance

-   **Payments:** cash, card (POS terminal), Telebirr, CBE Birr and bank
    transfer, each tracked per cashier shift

-   **Guest registration:** nationality, passport or Kebele/Fayda ID,
    visa details, and a printable guest register for police checks

-   **Language:** English and Amharic interface for staff; guest
    invoices in English

-   **Connectivity:** an offline mode for the POS and front desk,
    syncing when the internet returns, plus a local backup

-   **Calendar:** Gregorian by default, Ethiopian date shown on invoices
    if the hotel wants it

## Architecture and tech stack

One cloud-hosted backend serves every screen, so a bar tab posted to
room 204 shows on the front desk instantly.

  -----------------------------------------------------------------------
  **Layer**             **Components**
  --------------------- -------------------------------------------------
  Clients               Front desk (web): check-in, billing · POS
                        tablets: restaurant, bar, café · Housekeeping
                        app: phones, room status · Manager dashboard:
                        reports, night audit

  Backend API (NestJS   Reservations · Folio and billing · POS ·
  or Django REST)       Housekeeping · Laundry · Inventory · Reports ·
                        Auth and audit · Offline sync queue · VAT and
                        service charge rules

  Data                  PostgreSQL main database · nightly off-site
                        backup · Redis for sessions and queues

  Integrations          Channel manager (Expedia, Booking.com) ·
                        Telebirr, CBE Birr, card terminals · SMS and
                        email confirmations · fiscal receipt printer
  -----------------------------------------------------------------------

  ------------------------------------------------------------------------
  **Layer**   **Suggested choice**      **Why**
  ----------- ------------------------- ----------------------------------
  Frontend    React (Next.js) + PWA     Works on desktops and cheap
                                        Android tablets; installable,
                                        offline cache

  Backend     NestJS (TypeScript) or    Fast to build, strong typing /
              Django REST               admin tools

  Database    PostgreSQL                Reliable for money and bookings;
                                        transactions prevent double
                                        booking

  Hosting     AWS (Cape Town region) or Low latency; AWS student credits
              a local data centre       help early costs

  Auth        Role-based access, PIN    Fast at the till, safe for
              login for POS staff       managers
  ------------------------------------------------------------------------

## Data model

The Folio is the centre: every outlet posts charges to it, and it
becomes the invoice.

  ---------------------------------------------------------------------------
  **Entity**         **Key fields**                     **Links to**
  ------------------ ---------------------------------- ---------------------
  Guest              name, phone, email, nationality,   Reservations, Folios
                     ID/passport no., visa              

  RoomType           name, capacity, base rate          Rooms, RatePlans

  Room               number, floor, status,             RoomType
                     housekeeping status                

  RatePlan           name, season, price ETB/USD,       RoomType
                     breakfast included                 

  Reservation        dates, source (walk-in, phone,     Guest, RoomType, Room
                     OTA, direct), status, deposit      

  Stay               actual check-in/out, room moves    Reservation, Folio

  Folio              balance, currency, status          Stay, Charges,
                                                        Payments

  Charge             outlet, item, qty, amount, VAT,    Folio, Order,
                     service charge                     LaundryTicket

  Payment            method, amount, currency,          Folio
                     reference, cashier shift           

  Order (POS)        outlet, table/room, items, waiter  Charge, MenuItem

  LaundryTicket      items, price, status               Charge

  HousekeepingTask   room, type, assignee, done at      Room, Staff

  InventoryItem      unit, stock, reorder level         PurchaseOrder,
                                                        MenuItem recipe

  Staff / Role       name, role, permissions            AuditLog

  AuditLog           who, what, when, before/after      all
  ---------------------------------------------------------------------------

## Roadmap

Front desk goes live in week 11, the full system by week 22. Every phase
ends with a demo to the manager and a written sign-off before the next
starts.

  ----------------------------------------------------------------------------
  **Phase**    **Weeks**   **Deliverables**                     **Gate at
                                                                end**
  ------------ ----------- ------------------------------------ --------------
  0\.          1--3        Site visit, interviews,              Scope signed
  Discovery                requirements, screen designs, tax    
                           invoice check                        

  1\. Front    4--11       Reservations, check-in and out,      Front desk
  office                   guest folio and billing, roles and   live
                           audit log                            

  2\. Outlets  12--16      Housekeeping app, restaurant and bar Full hotel
                           POS, laundry, offline sync           go-live

  3\. Growth   17--22      Inventory, channel manager, booking  Handover
                           engine, owner dashboard              
  ----------------------------------------------------------------------------

## Team, budget and rollout

A team of 4--5 can deliver this; the budget below is a placeholder to
replace with your own rates.

  ---------------------------------------------------------------------------
  **Role**              **Count**   **Focus**
  --------------------- ----------- -----------------------------------------
  Project lead / BA     1           Requirements, hotel liaison, testing
                                    sign-off

  Backend developer     1--2        API, database, tax and billing logic

  Frontend developer    1           Front desk, POS and dashboard screens

  UI/QA (part-time)     1           Design, test cases, training material
  ---------------------------------------------------------------------------

**Running costs to quote the hotel:** cloud hosting (one small server +
managed database + backups), domain and SSL, SMS/email credits, and an
annual support contract. Hardware the hotel may need: receipt printers,
a kitchen printer, a passport scanner and tablets for housekeeping.

**Pricing models to offer:** a one-time build fee plus monthly support,
or a monthly subscription (SaaS) that you can later resell to other
Addis hotels.

**Go-live steps:**

1.  Load rooms, rates, menus, staff and future bookings from the current
    system

2.  Train each department on its own screens (half a day each)

3.  Run in parallel with the old process for one week

4.  Switch over on a low-occupancy day, with a developer on site for the
    first 3 nights

5.  Hand over admin guide and a support line with agreed response times

## Risks and open questions

  -----------------------------------------------------------------------
  **Risk**                     **Mitigation**
  ---------------------------- ------------------------------------------
  Internet or power outages    Offline-first POS and front desk; UPS for
  stop sales                   the server room

  Tax rules change or are      Confirm invoice format with the hotel's
  misread                      accountant before Phase 1 ends

  Staff resist a new system    Train by department; keep screens simple;
                               Amharic labels

  OTA double bookings during   Close OTA inventory for go-live day, then
  switch-over                  sync

  Scope keeps growing          Fix Phase 1 scope in writing; new requests
                               go to a later phase
  -----------------------------------------------------------------------

Questions to ask Vora Addis before quoting:

-   How many rooms, and how many of each room type?

-   What do they use today (paper, Excel, another PMS)?

-   Which OTAs do they sell on besides Expedia?

-   Do they have a fiscal printer, and which model?

-   How many staff per department, and how many shifts?

-   Is there an accounting system the folio data must export to?

-   Budget range and target go-live date?

## Sources

[Vora Addis Hotel --
Expedia](https://www.expedia.com/Addis-Ababa-Hotels-Vora-Addis-Hotel.h134512934.Hotel-Information)

## Build status

### Done in code

| Plan item | Implementation |
|---|---|
| One guest folio for room, restaurant, bar, café, laundry | `billing.Folio` / `Charge`; POS (`pos.services.post_to_room`) and laundry (`laundry.services.post_ticket`) post to the in-house guest's primary folio |
| No double bookings between walk-ins, phone and OTAs | `reservations.services.create_reservation` locks the room type row and checks every night's availability; OTA webhook and booking engine use the same function |
| Real-time room status for front desk and housekeeping | Shared room rack (`/api/housekeeping/rooms/`); check-out marks rooms dirty and opens a departure task; clean → inspection task → inspected |
| ERCA-style invoicing in ETB, USD for foreign guests | Per-line VAT and service charge (`core.money.tax_breakdown`), hotel and buyer TIN, gap-free invoice numbers (`billing.DocumentSequence`), USD converted at finance's daily rate |
| Daily owner reports | Occupancy, ADR, RevPAR, revenue by outlet, payments by method (`reports.services`); night audit freezes each day |
| Reservations: rate plans, deposits, groups, cancellations | Seasonal/corporate rate plans with priority, deposits as payments, groups, cancel / no-show |
| Front desk: check-in/out, assignment, registration, key handover | Registration checks (ID, nationality, passport for foreigners), dirty-room block, early arrival/departure, room moves, key card count |
| Folio: split bills, deposits, refunds | Extra folios per reservation and charge transfer; manager-only refunds; void with reason |
| Housekeeping mobile view | Phone-friendly room rack and task list |
| POS: orders, kitchen tickets, post to room, breakfast | Orders per outlet, kitchen screen (food only), pay at outlet with change, complimentary (manager), breakfast log and report |
| Laundry: intake, pricing, post to room | Price list per item/service, express surcharge, status flow, charge on delivery |
| Inventory & purchasing | Stock by location, reorder levels, recipe deduction on POS sales, purchase orders with partial receipt, stock counts |
| Reports: night audit, cashier shift close | Night audit (room nights, no-shows, overdue departures, open shifts); shift close with expected vs counted cash |
| Channel manager & booking engine | Availability/rate payload per channel with markup, buffer and stop-sell; signed OTA webhook (idempotent, handles cancellations); public availability + booking API |
| Staff, roles & audit log | 10 roles, PIN login for tills, per-role API permissions, before/after audit log of key records |
| Payments: cash, card, Telebirr, CBE Birr, bank transfer, per shift | All methods, references required for non-cash, every payment tied to the cashier's open shift; company account (city ledger) |
| Guest registration and police register | Nationality, ID type (passport, Kebele, Fayda), visa number/expiry; printable guest register |
| English and Amharic interface | Staff UI language switch; Amharic menu and laundry names; guest invoices in English |
| Offline mode for POS and front desk | PWA service worker caches the app, menus, rooms and front desk board; POS orders queue on the device and sync idempotently |
| Ethiopian calendar | Ethiopian date on invoices, exchange rates and the header (`core.ethiopian`) |
| Hosting: PostgreSQL, Redis, nightly backup | Docker Compose stack with nightly `pg_dump` (`deploy/backup.sh`) |

### Needs the hotel or a third party

| Item | What is needed | Where to plug it in |
|---|---|---|
| Fiscal device / e-invoicing | Printer model and the Ministry of Revenues' current rule | Add a driver class and set `FISCAL_DRIVER` (`backend/apps/billing/fiscal.py`) |
| OTA connection | Choice of channel-manager provider and API keys | `distribution.services.send` (outbound) and the webhook payload mapping |
| Room count and types, rates, menu | Real figures from the hotel | Admin or `seed_demo` |
| Invoice format sign-off | Hotel accountant | `pages/Invoice.tsx`, `billing.services.invoice_data` |
| Off-site backup target | S3 bucket or second site | Copy the `backups` volume off the server (see DEPLOYMENT.md) |
| SMS / email confirmations | SMS gateway account | Not built yet |
| Payment terminal / Telebirr API integration | Provider APIs | Payments are recorded with references today; automatic confirmation not built |

### Out of scope for v1 (unchanged from the plan)

Payroll and full accounting (export instead), door-lock integration, guest mobile app.
