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

### Payments are simulated

There is no payment gateway account yet. Telebirr and card payments are recorded as **paid** when the order is placed; pay-on-delivery stays **pending**. Only the last four digits of a card are ever sent. Replace `settle_payment()` in `orders/services.py` with a real gateway integration (Telebirr, Chapa, …) before taking real money.

## API

All responses are JSON. Errors are `{"error": "<message>", "field": "<input path>"?}` with a fitting status (401 sign in, 404 not found, 409 conflict, 422 invalid input).

| Method | Path | What |
| --- | --- | --- |
| GET | `/api/shell` | `{user, cart, wishlist}` for the current visitor |
| GET | `/api/auth/csrf` · `/api/auth/me` | CSRF cookie · current user |
| POST | `/api/auth/signup` · `/api/auth/signin` · `/api/auth/signout` | `{name, identifier, password}` · `{identifier, password, remember}` |
| GET | `/api/products?q=&mode=buy\|rent&dept=&brand=&min=&max=&sort=` | search / filter |
| GET | `/api/products/<slug>` · `/api/categories` · `/api/brands` | catalog |
| GET/POST | `/api/cart` | cart · add `{productId, mode, qty?, rentStart?, rentDays?, addOns?}` |
| PATCH/DELETE | `/api/cart/items/<id>` | change qty / dates / save for later · remove |
| POST/DELETE | `/api/cart/promo` | apply `{code}` · remove |
| POST | `/api/checkout` | place the order (see `orders/serializers.py` for the payload) |
| GET | `/api/orders` · `/api/orders/<id>` | my orders · one order |
| POST | `/api/rentals/<itemId>/extend` | `{days}` → `{charge}` |
| GET/POST | `/api/wishlist` | list · `{productId, saved}` |
| GET/POST · PATCH/DELETE | `/api/addresses` · `/api/addresses/<id>` | saved addresses |
| POST | `/api/newsletter` | `{email}` |

## Production notes

Set `DEBUG=0`, a real `SECRET_KEY`, `ALLOWED_HOSTS` and `FRONTEND_ORIGIN` (your site's URL). With `DEBUG=0` the container serves the API with gunicorn and cookies are marked `Secure`, so it must sit behind HTTPS.
