# CI/CD Pipeline — SerpantSupply

## Overview

```
Developer → git push → GitHub → GitHub Actions CI → Tests Pass → Deploy
```

## Pipeline Stages

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   1. Build   │───▶│  2. Test     │───▶│  3. Security │───▶│  4. Deploy   │
│              │    │              │    │     Scan     │    │              │
│ pip install  │    │ manage.py    │    │ safety check │    │ collectstatic│
│ requirements │    │ test         │    │ bandit scan  │    │ migrate      │
└──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
```

## GitHub Actions Workflow (.github/workflows/ci.yml)

```yaml
name: CI/CD Pipeline

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install safety bandit

      - name: Run migrations
        run: python manage.py migrate
        env:
          SECRET_KEY: test-secret-key-ci

      - name: Run tests
        run: python manage.py test tests --verbosity=2
        env:
          SECRET_KEY: test-secret-key-ci
          DEBUG: True

      - name: Security scan (dependencies)
        run: safety check -r requirements.txt

      - name: Security scan (code)
        run: bandit -r . -x ./tests,./venv

  deploy:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v3

      - name: Deploy to server
        run: |
          echo "Deploy step — SSH to server, pull latest, restart gunicorn"
          # ssh user@server "cd /app && git pull && pip install -r requirements.txt && python manage.py migrate && systemctl restart gunicorn"
```

## Monitoring & Logging

| Component     | Implementation                            |
|---------------|-------------------------------------------|
| App logs      | `logs/app.log` — all requests + events    |
| Security logs | `logs/security.log` — login, 2FA, 429s   |
| PayPal logs   | In `app.log` under `serpantsupply.paypal` |
| Log rotation  | 5 MB max, 3 backups kept                  |
| HTTP status   | Every request logged with method/path/ms  |

## Version Control Strategy

```
main ──────────────────────────────── (production)
  └─ develop ──────────────────────── (staging)
       ├─ feature/paypal-integration
       ├─ feature/jwt-api
       └─ fix/email-2fa
```
