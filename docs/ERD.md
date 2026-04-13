# SerpantSupply — Entity Relationship Diagram

```
┌─────────────────────────────┐         ┌─────────────────────────────┐
│           User              │         │         Email2FACode         │
│─────────────────────────────│         │─────────────────────────────│
│ PK  id          (int)       │────1:N──│ PK  id          (int)       │
│     username    (varchar)   │         │ FK  user_id     (int)       │
│     email       (varchar)   │         │     code        (varchar 6) │
│     password    (varchar)   │         │     created_at  (datetime)  │
│     is_staff    (bool)      │         └─────────────────────────────┘
│     date_joined (datetime)  │
└──────────────┬──────────────┘
               │
       ┌───────┴────────┐
       │                │
       │ (seller FK)    │ (buyer FK)
       ▼                ▼
┌─────────────────────────────┐         ┌─────────────────────────────┐
│          Product            │         │           Sale               │
│─────────────────────────────│         │─────────────────────────────│
│ PK  id          (int)       │────1:1──│ PK  id          (int)       │
│ FK  seller_id   (int)       │         │ FK  seller_id   (int)       │
│     name        (varchar)   │         │ FK  product_id  (int)       │
│     price       (decimal)   │         │ FK  buyer_id    (int, null) │
│     description (text)      │         │     item_name   (varchar)   │
│     image       (image)     │         │     price       (decimal)   │
│     condition   (varchar)   │         │     listed_at   (datetime)  │
│     is_sold     (bool)      │         └─────────────────────────────┘
│     created_at  (datetime)  │
└──────────────┬──────────────┘
               │
               │ (product FK)
               ▼
┌─────────────────────────────┐
│          Purchase           │
│─────────────────────────────│
│ PK  id           (int)      │
│ FK  user_id      (int)      │
│ FK  product_id   (int)      │
│     purchased_at (datetime) │
└─────────────────────────────┘
```

## Relationships

| Relationship         | Type  | Description                          |
|----------------------|-------|--------------------------------------|
| User → Email2FACode  | 1:N   | A user can have multiple codes (old ones deleted on new login) |
| User → Product       | 1:N   | A user can list many products as seller |
| User → Purchase      | 1:N   | A user can make many purchases       |
| Product → Purchase   | 1:1   | A product can only be purchased once |
| Product → Sale       | 1:1   | One sale record per listed product   |
| User → Sale (buyer)  | 1:N   | A user can appear as buyer on many sales |

## Notes
- `Product.is_sold` is flipped to `True` on successful purchase/PayPal payment
- `Email2FACode` records are deleted after successful verification or on new login
- `Sale` is created when a product is listed; `buyer` is populated when purchased
