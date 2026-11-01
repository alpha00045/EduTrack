# EduTrack — Student Management System

A Flask and PostgreSQL web application for managing student records, academic marks, and performance analytics.

**Live application:** https://edutrack-o3bp.onrender.com  
**Source code:** https://github.com/alpha00045/EduTrack

## Features

### Student records
- Add, view, edit, and delete student records
- Unique roll-number handling
- Search, sort and paginate the student list\n- Bulk CSV / Excel import with all-or-nothing validation
- Validate names, roll numbers, and marks on the server
- Friendly not-found, server-error, and database-unavailable pages
- About page and responsive navigation

### Academic performance
- Extended student profiles with guardian/contact details, secure profile photos and academic assessment history\n- Daily attendance marking and date-wise summaries\n- Configurable school name and pass mark\n- Automatic average and grade calculation
- Dashboard with class statistics and top students
- Analytics dashboard with subject averages and grade distribution
- Pass/fail summary (a student passes when every subject mark is at least 33)

### Reports and administration
- Redesigned secure admin sign-in with show/hide password control
- Admin login and session-protected management routes
- Student names, marks, dashboard, details and reports are visible only to authenticated admins
- Command-line student tracker with transaction-safe operations and CSV-formatted backups
- CSV and Excel exports with spreadsheet-formula injection protection\n- Complete ZIP backup of students, profiles, photos, assessments, attendance and settings\n- Add-only restore that preserves existing student records
- Downloadable PDF student result cards for admins and organization users
- Flash messages for user feedback
- Environment-based admin credentials and Flask secret key

## Technology

| Area | Technology |
|---|---|
| Backend | Python, Flask |
| Database | PostgreSQL |
| Frontend | HTML, CSS, Bootstrap 5, JavaScript |
| Charts | Chart.js |
| Excel export | openpyxl |
| Production server | Gunicorn |
| Hosting | Render |

## Project structure

```text
EduTrack/
├── app.py
├── main.py
├── requirements.txt
├── requirements-dev.txt
├── Procfile
├── templates/
│   ├── about/
│   ├── analytics/
│   ├── auth/
│   ├── errors/
│   ├── layouts/
│   ├── partials/
│   └── students/
├── static/
│   ├── css/
│   ├── js/
│   └── images/
└── tests/
    ├── test_helpers.py
    ├── test_routes.py
    └── test_cli.py
```

## Run locally

1. Clone the repository:

   ```bash
   git clone https://github.com/alpha00045/EduTrack.git
   cd EduTrack
   ```

2. Create and activate a virtual environment:

   ```bash
   python -m venv .venv
   ```

   Windows PowerShell:

   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```

   macOS/Linux:

   ```bash
   source .venv/bin/activate
   ```

3. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

4. Configure environment variables. Do not commit real secrets or your `.env` file.

   ```text
   DATABASE_URL=your_postgresql_connection_string
   SECRET_KEY=generate_a_long_random_secret
   ADMIN_USERNAME=choose_an_admin_username
   ADMIN_PASSWORD=choose_a_strong_unique_password
   ```

5. Start the Flask application:

   ```bash
   python app.py
   ```

Open http://127.0.0.1:5000 in your browser.

## Run tests

Install development dependencies and run the automated tests:

```bash
pip install -r requirements-dev.txt
pytest
```

The automated test suite covers input validation, grade and average calculations, route behavior, authentication, CSRF enforcement, spreadsheet export safety, database failure handling, PDF result cards, and CLI operations. GitHub Actions runs the tests on pushes and pull requests to `main`.

## Deployment notes

The application is configured to run with Gunicorn in production. Set `DATABASE_URL`, `SECRET_KEY`, `ADMIN_USERNAME`, and `ADMIN_PASSWORD` in the hosting provider's environment settings. Never publish these values.

## Development status

EduTrack is actively being improved. Features and test coverage may change as the project develops. Please report bugs or suggest improvements through GitHub Issues.

## Author

**Sagar Nayak**  
GitHub: https://github.com/alpha00045


## Organization registration (Phase 1)

EduTrack now includes an organization application workflow:

1. Schools, colleges, universities and institutes can submit an application from **Register your organization** on the login page.
2. The application stores institution details and a securely hashed password with status `pending`.
3. The platform administrator reviews applications from **Organizations** in the admin navigation.
4. The administrator can approve or reject pending applications. Review actions are authenticated and protected by CSRF.

### Database migration

Review and manually apply `migrations/003_organization_registration.sql` to the configured PostgreSQL/Supabase database. The application does not execute schema migrations automatically.

The organization portal is developed separately from Platform Administration. Organization accounts cannot access the platform-wide Organizations approval/management area.


## Organization portal (Phase 2)

Approved organizations can sign in at `/organization/login`. Pending, rejected, or suspended applications are not allowed into the organization portal. The portal provides an organization dashboard and student list, add-student, and student-detail pages. Tenant student data is stored in dedicated organization tables, separate from the original single-admin `students` table. Every organization student query is filtered by the authenticated organization ID.

Review and manually apply `migrations/004_organization_tenant_data.sql` after migration 003. The migration also creates organization-specific profile, assessment-history and attendance tables for subsequent feature work. Do not run migrations against production until you have taken a backup and reviewed the SQL.


## Organization portal feature parity

Each approved organization has its own portal with tenant-scoped student management:

- Student dashboard, search, add, edit, delete and detailed profiles
- Academic assessment history and profile photo management
- CSV and Excel exports, bulk CSV/XLSX import, and individual result-card PDF downloads
- Daily attendance register and organization-level analytics
- Organization-specific pass-mark settings
- Complete organization backup and add-only ZIP restore (students, profiles/photos, assessment history, attendance and settings)

All organization data routes filter by the signed-in `organization_id`. Organization accounts do not receive the Platform Administration **Organizations** approval and management feature, and cannot access platform admin routes. Organization backup and restore operate only on the active organization's records.

### Organization settings migration

After migrations 003 and 004, review and manually apply `migrations/005_organization_settings.sql` to create the organization-specific settings table. Do not run it against a live database until you have a verified backup. No migration is executed automatically by the application.

### Safe rollout

1. Take a verified database backup.
2. Apply migrations 003, 004 and 005 in order, if they have not already been applied.
3. Test organization registration, approval, login, student CRUD, imports/exports, attendance, analytics, settings and backup/restore using a test organization and dummy data.
4. Keep the changes on the feature branch until the owner has reviewed and approved the pull request.
