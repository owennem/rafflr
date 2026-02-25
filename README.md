# Rafflr

A raffle-based marketplace where users list products and buyers purchase raffle tickets instead of buying directly. Winners are selected automatically based on ticket limits or time deadlines.

## Features

- User registration with email verification
- Create and manage raffle listings
- Purchase tickets with Stripe integration
- Automatic raffle draws based on:
  - Ticket limit (when all tickets are sold)
  - Deadline (at a specific date/time)
  - Both (whichever comes first)
- Winner selection weighted by ticket count
- Email notifications for winners and sellers
- Admin dashboard for managing users, listings, and transactions

## Tech Stack

- **Backend**: FastAPI (Python 3.10+)
- **Database**: SQLite with SQLAlchemy ORM
- **Auth**: JWT tokens with password hashing (bcrypt)
- **Payments**: Stripe integration
- **Email**: SMTP (configurable for SendGrid/Mailgun)
- **Background Tasks**: APScheduler
- **Frontend**: Jinja2 templates + HTMX + Tailwind CSS

## Setup

1. Clone the repository:
```bash
cd rafflr
```

2. Create a virtual environment and activate it:
```bash
python -m venv venv
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Copy the environment file and configure it:
```bash
cp .env.example .env
```

Edit `.env` with your settings:
- `SECRET_KEY`: Generate a secure random key
- `STRIPE_SECRET_KEY`: Your Stripe secret key
- `STRIPE_PUBLISHABLE_KEY`: Your Stripe publishable key
- `STRIPE_WEBHOOK_SECRET`: Your Stripe webhook secret
- `SMTP_*`: Your email SMTP settings

5. Run the application:
```bash
uvicorn app.main:app --reload
```

6. Open http://localhost:8000 in your browser

## Stripe Setup

1. Create a Stripe account at https://stripe.com
2. Get your API keys from the Stripe Dashboard
3. For webhooks, create an endpoint pointing to `/payments/webhook`
4. Use test card `4242 4242 4242 4242` for testing

## Creating an Admin User

After registering a user, you can make them an admin by:

1. Using SQLite directly:
```bash
sqlite3 rafflr.db
UPDATE users SET is_admin = 1 WHERE email = 'your-email@example.com';
```

2. Or through the Python shell:
```python
from app.database import SessionLocal
from app.models.user import User

db = SessionLocal()
user = db.query(User).filter(User.email == 'your-email@example.com').first()
user.is_admin = True
db.commit()
```

## Project Structure

```
rafflr/
├── app/
│   ├── main.py              # FastAPI app entry point
│   ├── config.py            # Settings and environment variables
│   ├── database.py          # SQLAlchemy setup
│   ├── models/              # Database models
│   ├── schemas/             # Pydantic schemas
│   ├── routers/             # API routes
│   ├── services/            # Business logic
│   ├── templates/           # Jinja2 HTML templates
│   └── static/              # CSS, JS, images
├── requirements.txt
├── .env.example
└── README.md
```

## API Endpoints

### Authentication
- `GET /auth/register` - Registration page
- `POST /auth/register` - Register new user
- `GET /auth/login` - Login page
- `POST /auth/login` - Login user
- `GET /auth/logout` - Logout user
- `GET /auth/verify?token=` - Verify email
- `GET /auth/forgot-password` - Forgot password page
- `POST /auth/forgot-password` - Request password reset
- `GET /auth/reset-password?token=` - Reset password page
- `POST /auth/reset-password` - Reset password

### Listings
- `GET /listings` - Browse listings
- `GET /listings/create` - Create listing page
- `POST /listings/create` - Create new listing
- `GET /listings/{id}` - View listing
- `GET /listings/{id}/edit` - Edit listing page
- `POST /listings/{id}/edit` - Update listing
- `POST /listings/{id}/cancel` - Cancel listing
- `POST /listings/{id}/draw` - Manually draw winner

### Tickets
- `POST /tickets/purchase` - Purchase tickets
- `GET /tickets/success` - Purchase success page

### Payments
- `POST /payments/webhook` - Stripe webhook handler

### Dashboard
- `GET /dashboard` - User dashboard
- `GET /dashboard/listings` - User's listings
- `GET /dashboard/tickets` - User's tickets
- `GET /dashboard/wins` - User's wins
- `GET /profile` - User profile

### Admin
- `GET /admin` - Admin dashboard
- `GET /admin/users` - Manage users
- `POST /admin/users/{id}/toggle-admin` - Toggle admin status
- `POST /admin/users/{id}/verify` - Verify user email
- `GET /admin/listings` - Manage listings
- `GET /admin/transactions` - View transactions

## License

MIT
