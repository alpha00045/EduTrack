# EduTrack local setup (Windows)

1. Install Python 3.10+ and PostgreSQL access (Supabase PostgreSQL is supported).
2. Copy `.env.example` to `.env`.
3. Edit `.env` and set your PostgreSQL URL, a new random SECRET_KEY, ADMIN_USERNAME and ADMIN_PASSWORD.
4. Double-click `run_local.bat` or run it from Command Prompt.
5. Open http://127.0.0.1:5000.

The app loads `.env` automatically. Keep `.env` private and never commit it.

## Tests

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
pytest -q
```

## Organization registration

Public route: `/register-organization`
Organization login: `/organization/login`
Platform admin review: `/system/organization-requests` (after platform admin login).

Apply migrations 003 and 004 manually to a **separate test database** before testing organization registration. Do not test write workflows against a live database containing real records.
