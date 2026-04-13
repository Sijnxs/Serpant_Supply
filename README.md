# SerpantSupply 🐍

Professional Django marketplace with JWT REST API, PayPal payments, email 2FA, RBAC, and full CI/CD pipeline docs.

## Quick Start

```bash
# 1. Install
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Edit .env with your credentials

# 3. Setup database
python manage.py migrate
python manage.py createadmin   # optional: creates default admin

# 4. Run
python manage.py runserver
```

Visit: http://127.0.0.1:8000

## Environment Variables

| Variable               | Required | Description                          |
|------------------------|----------|--------------------------------------|
| `SECRET_KEY`           | Yes (prod)| Django secret key                   |
| `EMAIL_HOST_USER`      | For email | Gmail address for 2FA               |
| `EMAIL_HOST_PASSWORD`  | For email | Gmail App Password                  |
| `PAYPAL_CLIENT_ID`     | For payments | PayPal app client ID            |
| `PAYPAL_CLIENT_SECRET` | For payments | PayPal app client secret        |
| `PAYPAL_MODE`          | No       | `sandbox` (default) or `live`        |

## REST API

Base URL: `http://127.0.0.1:8000/api/`

| Method | Endpoint                      | Auth    | Description              |
|--------|-------------------------------|---------|--------------------------|
| POST   | `/auth/register/`             | None    | Register + get JWT       |
| POST   | `/auth/login/`                | None    | Login + get JWT          |
| POST   | `/auth/refresh/`              | None    | Refresh access token     |
| GET    | `/auth/me/`                   | JWT     | Current user profile     |
| GET    | `/products/`                  | None    | List products            |
| POST   | `/products/create/`           | JWT     | Create listing           |
| GET    | `/products/<id>/`             | None    | Product detail           |
| PATCH  | `/products/<id>/manage/`      | JWT+Own | Update listing           |
| DELETE | `/products/<id>/manage/`      | JWT+Own | Delete listing           |
| GET    | `/my/listings/`               | JWT     | My listings              |
| GET    | `/my/purchases/`              | JWT     | My purchases             |
| POST   | `/payments/create-order/`     | JWT     | Create PayPal order      |
| GET    | `/payments/execute/`          | JWT     | Execute PayPal payment   |
| GET    | `/admin/stats/`               | Admin   | Dashboard stats          |
| GET    | `/admin/users/`               | Admin   | All users                |

## Run Tests

```bash
python manage.py test tests --verbosity=2
```

## PayPal Setup

1. Go to https://developer.paypal.com
2. Create a sandbox app → copy Client ID + Secret
3. Set `PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET`, `PAYPAL_MODE=sandbox` in `.env`
4. Use sandbox buyer account to test purchases

## Project Structure

```
serpantsupply/
├── accounts/           # Auth, 2FA, profile, middleware
├── marketplace/        # Products, purchases, sales
├── api/                # REST API, JWT, PayPal endpoints
├── templates/          # Shared base template
├── tests/              # Integration test suite
├── docs/               # ERD, CI/CD, System Design, Postman
├── logs/               # app.log + security.log (gitignored)
└── serpantsupply/      # Django project config
```

## Docs

- `docs/ERD.md` — Entity Relationship Diagram
- `docs/CICD_PIPELINE.md` — CI/CD pipeline + GitHub Actions config
- `docs/SYSTEM_DESIGN.md` — System architecture + data flows
- `docs/postman_collection.json` — Import into Postman for API testing
