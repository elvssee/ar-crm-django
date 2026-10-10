# Architecture CRM (Django)

Multi-firm CRM for architecture firms. Python + Django. Each firm is a `Firm`; every user belongs to one firm.

## Setup (Windows PowerShell)

```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python manage.py makemigrations accounts
python manage.py migrate
python manage.py test
python manage.py runserver
```

Open http://127.0.0.1:8000 and sign up.

## Database

Leave `DATABASE_URL` empty in `.env` to use local SQLite. To use Supabase Postgres, paste the
**Session pooler** connection string into `DATABASE_URL`, then run `python manage.py migrate` again.

Never commit `.env`.
