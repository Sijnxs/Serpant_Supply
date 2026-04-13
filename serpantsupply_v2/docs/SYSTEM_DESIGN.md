# System Design — SerpantSupply

## Integrated Modules

```
┌─────────────────────────────────────────────────────────────────┐
│                        SerpantSupply                            │
│                                                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────┐  │
│  │   accounts   │    │ marketplace  │    │      api         │  │
│  │              │    │              │    │                  │  │
│  │ • register   │    │ • listings   │    │ • REST endpoints │  │
│  │ • login/2FA  │    │ • buy/sell   │    │ • JWT auth       │  │
│  │ • profile    │    │ • search     │    │ • PayPal         │  │
│  │ • rate limit │    │ • filter     │    │ • RBAC           │  │
│  └──────┬───────┘    └──────┬───────┘    └────────┬─────────┘  │
│         │                  │                      │            │
│  ┌──────▼──────────────────▼──────────────────────▼──────────┐ │
│  │                    SQLite Database                         │ │
│  │  User  Email2FACode  Product  Purchase  Sale              │ │
│  └───────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
         │                    │                      │
         ▼                    ▼                      ▼
    Gmail SMTP           File System            PayPal API
   (2FA emails)         (media/images)       (sandbox/live)
```

## Data Flow: Purchase via PayPal

```
User clicks Buy
      │
      ▼
buy_product view → render buy_confirm.html
      │
      ▼ (PayPal SDK renders button)
User clicks PayPal button
      │
      ▼
POST /api/payments/create-order/  [JWT authenticated]
      │
      ▼
paypalrestsdk.Payment.create()  →  PayPal API
      │
      ▼
Returns approve_url
      │
      ▼
User redirected to PayPal → approves payment
      │
      ▼
PayPal redirects to /api/payments/execute/?paymentId=...&PayerID=...
      │
      ▼
paypalrestsdk.Payment.execute() → PayPal API
      │
      ▼
product.is_sold = True
Purchase.objects.create()
Sale buyer updated
      │
      ▼
Redirect to profile with success message

## Security Layers

1. Authentication: Django session (UI) + JWT Bearer tokens (API)
2. 2FA: Email OTP required on every login
3. RBAC: IsOwnerOrReadOnly, IsSellerOrAdmin, IsAdminUser permissions
4. Rate limiting: 100 req/min per IP (middleware)
5. Input validation: DRF serializers + Django form validation
6. CSRF protection: Django CSRF middleware on all HTML forms
7. Password hashing: Django PBKDF2 (default)
8. Logging: All security events logged to security.log
