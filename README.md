# InvoicePro - Django Billing Management System

InvoicePro is a professional billing and invoice management system built using Python and Django. The project helps businesses manage customers, invoices, products, and payments efficiently.

---

## Features

- User Authentication System
- Dashboard Analytics
- Customer Management
- Product Management
- Invoice Generation
- Payment Tracking
- PDF Invoice Support
- Responsive UI Design
- Search and Filtering
- Django Admin Panel

---

## Technologies Used

- Python
- Django
- HTML5
- CSS3
- Bootstrap
- JavaScript
- postgreSQL

---

## Project Structure

```text
InvoicePro/
│
├── accounts/
├── customers/
├── dashboard/
├── invoices/
├── payments/
├── products/
├── static/
├── templates/
├── manage.py
└── requirements.txt
```

---

# Installation and Setup

## 1. Clone the Repository

```bash
git clone https://github.com/shahvishw/django-billing-system.git
```
## 2. Navigate to Project Directory

```bash
cd InvoicePro
```
## 3. Create Virtual Environment

Windows:
```bash
python -m venv venv
```

## 4. Activate Virtual Environment

Windows:
```bash
venv\\Scripts\\activate
```

Mac/Linux:
```bash
source venv/bin/activate
```

## 5. Install Required Dependencies
```bash
pip install -r requirements.txt
```
## 6. Apply Database Migrations
```bash
python manage.py migrate
```

## 7. Create Superuser (Optional)
```bash
python manage.py createsuperuser
```

## 8. Run Development Server
```bash
python manage.py runserver
```

## Access the Application

Open browser and visit:
```bash
http://127.0.0.1:8000/
```

Admin Panel:
```bash
http://127.0.0.1:8000/admin/
```

# Author
Developed by VISHW SHAH