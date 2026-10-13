# InvoicePro

InvoicePro is a Django application for small businesses to manage customers, products and services, invoices, and payments. It uses Django templates and server-rendered pages.

## Current features

- Owner registration and business setup
- Organization memberships with owner, manager, staff, and accountant roles
- Organization-scoped customers, catalog items, invoices, payments, and activity records
- Product stock tracking; services do not use stock
- Invoice PDFs and optional customer email
- Partial payment recording and payment reminders
- A dashboard with invoice, payment, and outstanding-balance information

Each organization can set a total tax percentage in Organization settings. The rate is saved on every new invoice so later setting changes do not change historical invoices. Confirm the correct tax treatment and any required tax breakdowns for your business before using invoices for real transactions. InvoicePro does not provide formal accounting, tax filing, payroll, or legal compliance services.

## Project layout

| App or folder | Responsibility |
| --- | --- |
| `api` | Versioned, read-only JSON endpoints and organization-scoped API permissions |
| `accounts` | Login, owner registration, and organization setup |
| `organizations` | Businesses, memberships, roles, and organization settings |
| `audit` | Organization activity records |
| `customers` | Customer records and customer lookup |
| `products` | Product and service catalog, including stock for products |
| `invoices` | Invoice creation, pricing, PDF generation, and reminders |
| `payments` | Payments recorded against invoices |
| `dashboard` | Business summary and public home page |
| `templates` | Django HTML templates |
| `static` | CSS and JavaScript files |

Every customer, catalog item, invoice, and payment belongs to an organization. Application views use the signed-in user's active membership to scope business data.

## Local setup on Windows

Use a Python version supported by the Django version pinned in `requirements.txt`.

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Create a local `.env` from `.env.example` if you do not already have one. Keep `.env` private and replace the example secret before using the application outside local development.

The default timezone is `Asia/Kolkata`; set `TIME_ZONE` in `.env` for another deployment timezone. If the app runs behind a reverse proxy, configure trusted client IP forwarding before changing `LOGIN_RATE_LIMIT_IP_HEADER` from `REMOTE_ADDR`.

When `DB_NAME` is unset, the project uses a local SQLite database. Set `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, and `DB_PORT` in `.env` to use PostgreSQL.

Apply database migrations and start the development server:

```powershell
python manage.py migrate
python manage.py runserver
```

Open <http://127.0.0.1:8000/>. Create an owner account at <http://127.0.0.1:8000/accounts/register/>. The Django admin is available at <http://127.0.0.1:8000/admin/> for local development.

## Payment reminder command

The project includes a management command for sending reminders according to each organization's reminder setting:

```powershell
python manage.py send_reminders
```

Configure a real email backend in `.env` before expecting emails to reach customers. The console backend in development and the dummy backend in production are treated as non-delivery: invoice emails are skipped with a user-visible message, and the reminder command leaves the reminder date unchanged so it can be retried after email is configured.

## JSON serialization

Django REST Framework serializers shape the JSON used by the invoice editor:

- `GET /customers/check/?phone=...` checks for a customer within the signed-in user's active organization.
- `GET /products/search/?q=...` searches active catalog items within that organization.

Both endpoints keep the existing response fields for the current browser interface. Their serializers live in `customers/serializers.py` and `products/serializers.py`.

Authenticated, read-only API v1 endpoints are also available for customers, catalog items, invoices, and payments under `/api/v1/`. They use the signed-in session, require an active organization membership, and only return records from that organization. List endpoints support `page` and `page_size` pagination (maximum 100); customer, catalog, invoice, and payment lists also accept a `q` search term. Catalog lists accept `type=product|service` and `status=active|inactive`. Write operations remain in the existing application flows so invoice pricing and payment validation cannot be bypassed.

## Database change safety

Keep migration files that have been applied to a shared database. Make later schema or data changes with new, forward migrations. Review data migrations before applying them, especially when they update invoice or payment records.
