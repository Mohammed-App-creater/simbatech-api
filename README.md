# Simbatech API

The backend for the Simbatech store (buy or rent by the day, Ethiopian market): Django 5.2, Django REST Framework and PostgreSQL 16. The Next.js site lives in the separate `simbatech-web` repo and talks to this API.

## Run it with Docker (recommended)

You need Docker Desktop.

```bash
cp .env.example .env     # then set SECRET_KEY
docker compose up -d     # Postgres + the API on http://localhost:8000
```

On start the API container applies migrations, seeds the catalog and demo data, and serves the API. Logs: `docker compose logs -f api`.

- **API:** http://localhost:8000/api/products
- **Admin site:** http://localhost:8000/admin/ — `admin@simbatech.et` / `admin12345` (set `ADMIN_PASSWORD` in `.env` before the first start to choose your own). Manage products, prices, rental plans, stock, promo codes, customers and orders here; changing an order's status updates the customer's tracking timeline.
- **Demo customer (for the website):** `demo@simbatech.et` / `simbatech123`. Promo code `SIMBA10` gives 10% off purchases.
- **Store settings** (name, city, address, phone, hours, policies shown across the site) live in the admin under *Catalog › Store settings*. Content pages (Help, Delivery, Returns, Terms, …) are under *Pages*; messages from the contact form under *Contact messages*.

## Run it without Docker

```bash
python -m venv .venv && .venv/Scripts/activate      # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
docker compose up -d db                              # or point DATABASE_URL at any Postgres 16
python manage.py migrate
python manage.py seed
python manage.py runserver 8000
```

`python manage.py seed` is safe to re-run: it refreshes the catalog and recreates the demo customer's orders.

## Layout

```
config/       settings, root urls
core/         pricing rules (core/pricing.py), error format (core/errors.py), API url table (core/urls.py)
accounts/     User (phone or email + password), sessions, addresses, wishlist
catalog/      categories, brands, products, rental plans, add-ons, promo codes, newsletter; `seed` command
cart/         carts (guest carts live in the session and merge on sign-in)
orders/       checkout, orders, tracking events, rental extensions
```

### Auth

Session cookie (`sessionid`, httpOnly). Sign up / sign in with a phone number (09…/07…) or an email address. Signed-in POST/PATCH/DELETE requests must send the `csrftoken` cookie's value in an `X-CSRFToken` header (`GET /api/auth/csrf` sets the cookie). The website proxies `/api/*` to this server so it shares the cookie without CORS.

### Money and rules

All amounts are whole birr (ETB). Rentals use the product's day rate or a cheaper multi-day plan (1 day / 3 days / 1 week / 2 weeks) plus add-ons per day. Purchases of ETB 100,000+ ship free (otherwise ETB 500); same-day delivery adds ETB 450; rental delivery and collection are free; the deposit is refundable and not part of the total charged. See `core/pricing.py`.

### Integrations (optional — the API runs in a development mode without them)

| What | Env keys | Without keys |
| --- | --- | --- |
| **Online payments** via [Chapa](https://chapa.co) (hosts the payment page: Telebirr, CBE Birr, cards) | `CHAPA_SECRET_KEY`, `CHAPA_WEBHOOK_SECRET`, `API_PUBLIC_URL` | Telebirr / card orders are marked **paid** immediately (`payment.simulated`). Pay-on-delivery always stays pending until delivery. |
| **Sign in with Google** | `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` (redirect URI `<API_PUBLIC_URL>/api/auth/google/callback`) | The site's Google button is disabled. |
| **SMS one-time codes** (phone sign-in, password reset by phone) via Africa's Talking | `SMS_BACKEND=africastalking`, `AT_USERNAME`, `AT_API_KEY`, `AT_SENDER_ID` | Codes are printed to the log and, while `DEBUG=1`, returned to the site as `devCode` so you can test. |
| **Password-reset emails** | `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `DEFAULT_FROM_EMAIL` | Emails are printed to the log and, while `DEBUG=1`, the link is returned as `devLink`. |

Payment flow with Chapa: checkout creates the order as *pending* and answers with `payment.redirectUrl`; the site sends the customer to Chapa; Chapa returns them to `/api/payments/return` (which verifies the transaction and redirects to the order page) and also calls `/api/payments/webhook`. Unpaid orders can be paid later with `POST /api/payments/start`. See `orders/payments.py`. Only a card's last four digits are ever sent to this API.

## API

All responses are JSON. Errors are `{"error": "<message>", "field": "<input path>"?}` with a fitting status (401 sign in, 404 not found, 409 conflict, 422 invalid input).

| Method | Path | What |
| --- | --- | --- |
| GET | `/api/shell` | `{user, cart, wishlist}` for the current visitor |
| GET | `/api/auth/csrf` · `/api/auth/config` · `/api/auth/me` | CSRF cookie · which sign-in methods are on · current user (`PATCH` updates name/email/phone) |
| POST | `/api/auth/signup` · `/api/auth/signin` · `/api/auth/signout` | `{name, identifier, password}` · `{identifier, password, remember}` |
| POST | `/api/auth/otp/send` · `/api/auth/otp/verify` | phone sign-in: `{phone}` → code by SMS · `{phone, code, name?}` |
| GET | `/api/auth/google/start?next=` · `/api/auth/google/callback` | sign in with Google |
| POST | `/api/auth/password/forgot` · `/reset` · `/change` | `{identifier}` · `{uid, token, password}` or `{phone, code, password}` · `{current, password}` |
| GET/PATCH | `/api/auth/notifications` | `{sms, email, remind, deals}` |
| GET/POST · PATCH/DELETE | `/api/payment-methods` · `/api/payment-methods/<id>` | saved Telebirr numbers / card reminders (brand, last 4, expiry only) |
| GET | `/api/products?q=&mode=buy\|rent&dept=&brand=&min=&max=&sort=` | search / filter |
| GET | `/api/products/<slug>` · `/api/categories` · `/api/brands` · `/api/bundles` | catalog (add `deals=1` to the list for sale items) |
| GET/POST/DELETE | `/api/products/<slug>/reviews` | reviews with a star distribution · write / update yours · delete yours |
| GET | `/api/settings` · `/api/pages` · `/api/pages/<slug>` | store details · content pages |
| POST | `/api/contact` | `{topic, name, contact, message}` |
| GET/POST | `/api/cart` | cart · add `{productId, mode, qty?, variant?, rentStart?, rentDays?, addOns?}` |
| POST | `/api/cart/bundle` | `{bundleId, rentStart?, rentDays?}` books every product in a rental bundle |
| PATCH/DELETE | `/api/cart/items/<id>` | change qty / dates / save for later · remove |
| POST/DELETE | `/api/cart/promo` | apply `{code}` · remove |
| POST | `/api/checkout` | place the order (see `orders/serializers.py`); answers `{orderId, number, payment: {status, redirectUrl?}}` |
| GET | `/api/orders` · `/api/orders/<id>` · `/api/orders/track?number=&phone=` | my orders · one order · public tracking |
| POST · GET · POST | `/api/payments/start` · `/api/payments/return` · `/api/payments/webhook` | pay an unpaid order · gateway return · gateway webhook |
| POST | `/api/rentals/<itemId>/extend` | `{days}` → `{charge}` |
| GET/POST | `/api/wishlist` | list · `{productId, saved}` |
| GET/POST · PATCH/DELETE | `/api/addresses` · `/api/addresses/<id>` | saved addresses |
| POST | `/api/newsletter` | `{email}` |

## Production notes

Set `DEBUG=0`, a real `SECRET_KEY`, `ALLOWED_HOSTS` and `FRONTEND_ORIGIN` (your site's URL; a comma-separated list is allowed, the first one receives sign-in and payment redirects). Signed-in requests from any other origin are rejected by the CSRF check. With `DEBUG=0` the container serves the API with gunicorn and cookies are marked `Secure`, so it must sit behind HTTPS.
