# EduTrack — Student Management System

A Flask and PostgreSQL web application for managing student records, academic marks, and performance analytics.

**Live application:** https://edutrack-o3bp.onrender.com  
**Source code:** https://github.com/alpha00045/EduTrack

## Features

### Student records
- Add, view, edit, and delete student records
- Unique roll-number handling
- Search and sort the student list
- Validate names, roll numbers, and marks on the server

### Academic performance
- Automatic average and grade calculation
- Dashboard with class statistics and top students
- Analytics dashboard with subject averages and grade distribution
- Pass/fail summary (a student passes when every subject mark is at least 33)

### Reports and administration
- Admin login and session-protected management routes
- CSV and Excel exports
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
    └── test_helpers.py
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

The current test suite covers input validation, average calculation, and grade boundaries. Route and database integration tests are planned.

## Deployment notes

The application is configured to run with Gunicorn in production. Set `DATABASE_URL`, `SECRET_KEY`, `ADMIN_USERNAME`, and `ADMIN_PASSWORD` in the hosting provider's environment settings. Never publish these values.

## Development status

EduTrack is actively being improved. Features and test coverage may change as the project develops. Please report bugs or suggest improvements through GitHub Issues.

## Author

**Sagar Nayak**  
GitHub: https://github.com/alpha00045
