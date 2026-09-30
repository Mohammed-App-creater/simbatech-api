# Simbatech API (Django)

Backend for the Simbatech store (buy or rent by the day, Ethiopian market). Django 5.2 + Django REST Framework,
PostgreSQL. The website is the separate repo `../simbatech-web` (Next.js), see its CLAUDE.md.

- Production: https://simbatech-api.onrender.com (Render, Python runtime, auto-deploys from `main`)
- Database: Neon Postgres (pooled connection string in `DATABASE_URL`)
- Admin: `/admin/` (`admin@simbatech.et`; password from `ADMIN_PASSWORD` at first seed)
- The site proxies `/api/*` to this API, so the browser sees one origin and the session cookie is first-party.

## Layout

- `config/` settings (all config from env vars, see `.env.example`), root urls (`/` is a health check).
- `core/urls.py` the API url table; `core/pricing.py` pricing rules; `core/errors.py` error format.
- `accounts/` User (phone or email + password), sessions, addresses, wishlist, saved payment methods,
  notification prefs, OTP codes (`otp.py`, `sms.py`), Google sign-in (`google.py`), password reset.
- `catalog/` categories, brands, products (+ variants, rental plans, add-ons, specs), reviews, bundles, promo codes,
  content pages, contact messages, **StoreSettings** (city, phone, hours, policies shown across the site).
  `catalog/dto.py` shapes products the way the site's screens expect — keep those keys stable.
- `cart/` guest carts live in the session and merge into the account on sign-in.
- `orders/` checkout (`services.py`), payments (`payments.py`), tracking, rental extensions.
- `backoffice/` the staff API behind the site's `/admin` pages: `/api/admin/*` (overview, orders, review approval,
  products, messages, customers, promo codes, store details). Every view extends `StaffView` (`is_staff` only:
  401 signed out, 403 for customers). No models of its own. Django's `/admin/` still covers the rest
  (categories, brands, bundles, content pages, staff accounts).

## Conventions

- Money is whole birr (ETB) as integers. Shop time zone is Africa/Addis_Ababa (`shop_today()`).
- Every error leaves as `{"error": "<customer-facing message>", "field": "<input path>"?}` with a fitting status
  (raise `core.errors.ApiError`). The site shows `field` errors inline.
- Phones are Ethiopian mobiles, normalised by `accounts.identity.normalize_phone` to `0911234567` (7 or 9 after 0).
- **Reviews need approval**: `Review.status` is `pending` until staff approve it (a customer's edit puts it back
  to pending). Only approved reviews are in `reviews_payload().items` and in the product's rating; `mine` carries
  the author's own review with its status. Call `product.recompute_rating()` after any status change.
- Rules: free delivery at ETB 100,000 purchases (else 500), same-day +450, rental delivery free,
  deposit refundable and not in `total`.
- `python manage.py seed` refreshes catalog + demo data; **`seed --if-empty` in deploys** so admin edits are never
  overwritten. Demo customer `demo@simbatech.et` / `simbatech123`.

## Integrations (each works in a development mode without keys)

- **Payments — Chapa** (`CHAPA_SECRET_KEY`, `CHAPA_WEBHOOK_SECRET`). Without a key, Telebirr/card orders are
  recorded as paid (`payment.simulated`). Webhook URL in the Chapa dashboard:
  `https://simbatech-api.onrender.com/api/payments/webhook`; its "Secret hash" = `CHAPA_WEBHOOK_SECRET`.
  Chapa sends two signature headers; both are accepted, and payments are always re-verified with Chapa's API.
- **Google sign-in** (`GOOGLE_CLIENT_ID/SECRET`). Redirect URI registered in Google:
  `https://simbatech-e-commerce.vercel.app/api/auth/google/callback`.
- **`API_PUBLIC_URL` must be the website's URL** (https://simbatech-e-commerce.vercel.app), not the API's:
  Google and Chapa callbacks must come back through the site's proxy so the session cookie matches.
- **Email — Brevo SMTP**: `EMAIL_HOST=smtp-relay.brevo.com`, **`EMAIL_PORT=2525`** (Render's free plan blocks
  25/465/587; a blocked port hangs until gunicorn kills the worker), login `…@smtp-brevo.com`, password = SMTP key.
  Brevo blocks unknown IPs by default (`525 5.7.1 Unauthorized IP address`): IP blocking is turned off under
  Brevo → Security → Authorized IPs. `EMAIL_TIMEOUT` (default 10s) keeps a bad mail server from hanging requests.
- **SMS codes** — `SMS_BACKEND=console` logs codes (and returns `devCode` while `DEBUG=1`); `africastalking` sends.

## Render settings

- Build: `pip install -r requirements.txt && python manage.py collectstatic --noinput`
- Start: `python manage.py migrate --noinput && python manage.py seed --if-empty && gunicorn config.wsgi:application --bind 0.0.0.0:$PORT`
- Env: see `.env.prod` locally (git-ignored; holds real secrets — never commit it or paste it into chat).
  `FRONTEND_ORIGIN` = site URL (comma-separated list allowed, first one receives redirects).
- `DATABASE_URL` query options (`?sslmode=require&channel_binding=require`) are passed through to libpq.
- Free plan sleeps after ~15 min idle; first request then takes ~30–50s.

## Local development

`docker compose up -d` (Postgres + API on :8000, migrates and seeds itself), or a venv:
`pip install -r requirements.txt`, `python manage.py migrate && python manage.py seed && python manage.py runserver`.
Check with `python manage.py check`.

## Working with the owner

- Commit and push to `main` when a piece of work is done and checks pass (Render deploys from it).
- Commit messages end with the `Co-Authored-By` line given in the session.
