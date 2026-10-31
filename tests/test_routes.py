import os

os.environ.setdefault("SECRET_KEY", "test-only-secret-key")
os.environ.setdefault("ADMIN_USERNAME", "test-admin")
os.environ.setdefault("ADMIN_PASSWORD", "test-password")

import csv
import io

import pytest
import psycopg2
from openpyxl import load_workbook
import app as student_app

REAL_GET_DB_CONNECTION = student_app.get_db_connection


ROWS = [
    (101, "Asha Das", 85, 90, 88),
    (102, "Ravi Kumar", 70, 75, 80),
]


_DEFAULT_ROW = object()


class FakeCursor:
    def __init__(self, rows=None, one=_DEFAULT_ROW):
        self.rows = rows if rows is not None else ROWS
        self.one = ROWS[0] if one is _DEFAULT_ROW else one
        self.executed = []
        self.closed = False
        self.rowcount = 1

    def execute(self, query, params=None):
        self.executed.append((query, params))

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return self.one

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, rows=None, one=_DEFAULT_ROW):
        self.fake_cursor = FakeCursor(rows=rows, one=one)
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def cursor(self):
        return self.fake_cursor

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


@pytest.fixture
def client(monkeypatch):
    student_app.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    monkeypatch.setattr(
        student_app, "get_db_connection", lambda: FakeConnection()
    )
    with student_app.app.test_client() as test_client:
        yield test_client


def login_as_admin(client):
    with client.session_transaction() as session:
        session["admin"] = "test-admin"


def test_home_page_requires_admin(client):
    response = client.get("/")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_home_page_renders_students_and_summary_for_admin(client):
    login_as_admin(client)
    response = client.get("/")
    assert response.status_code == 200
    assert b"Asha Das" in response.data


def test_students_page_requires_admin(client):
    response = client.get("/view_students")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_students_page_renders_records_for_admin(client):
    login_as_admin(client)
    response = client.get("/view_students")
    assert response.status_code == 200
    assert b"Ravi Kumar" in response.data


def test_student_details_page_requires_admin(client):
    response = client.get("/student/101")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_student_details_page_renders_record_for_admin(client):
    login_as_admin(client)
    response = client.get("/student/101")
    assert response.status_code == 200
    assert b"Asha Das" in response.data


def test_admin_route_redirects_unauthenticated_user(client):
    response = client.get("/add_student")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_analytics_requires_admin(client):
    response = client.get("/analytics")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_analytics_page_renders_for_admin(client):
    login_as_admin(client)
    response = client.get("/analytics")
    assert response.status_code == 200
    assert b"Analytics" in response.data


def test_login_accepts_configured_admin_credentials(client):
    response = client.post(
        "/login",
        data={"username": "test-admin", "password": "test-password"},
    )
    assert response.status_code == 302
    with client.session_transaction() as session:
        assert session["admin"] == "test-admin"


def test_login_rejects_invalid_credentials(client):
    response = client.post(
        "/login",
        data={"username": "wrong", "password": "wrong"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Invalid Username or Password" in response.data


def test_get_logout_is_not_allowed(client):
    login_as_admin(client)
    response = client.get("/logout")
    assert response.status_code == 405
    with client.session_transaction() as session:
        assert session.get("admin") == "test-admin"


def test_post_logout_clears_admin_session(client):
    login_as_admin(client)
    response = client.post("/logout")
    assert response.status_code == 302
    with client.session_transaction() as session:
        assert "admin" not in session


def test_post_without_csrf_token_is_rejected(client):
    student_app.app.config["WTF_CSRF_ENABLED"] = True
    response = client.post(
        "/login",
        data={"username": "test-admin", "password": "test-password"},
    )
    assert response.status_code == 400
    student_app.app.config["WTF_CSRF_ENABLED"] = False


def test_invalid_add_form_does_not_write_to_database(client, monkeypatch):
    login_as_admin(client)

    def fail_if_db_is_used():
        pytest.fail("Database should not be accessed for invalid form data")

    monkeypatch.setattr(student_app, "get_db_connection", fail_if_db_is_used)
    response = client.post(
        "/add_student",
        data={"roll": "0", "name": "", "math": "110", "science": "80", "english": "70"},
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/add_student")


def test_valid_add_form_commits_insert(client, monkeypatch):
    login_as_admin(client)
    connection = FakeConnection()
    monkeypatch.setattr(student_app, "get_db_connection", lambda: connection)

    response = client.post(
        "/add_student",
        data={
            "roll": "103",
            "name": "Meera Das",
            "math": "91",
            "science": "87",
            "english": "89",
        },
    )

    assert response.status_code == 302
    assert connection.committed is True
    assert "INSERT INTO students" in connection.fake_cursor.executed[0][0]


def test_csv_export_quotes_fields_and_neutralizes_formula_names(client, monkeypatch):
    login_as_admin(client)
    dangerous_rows = [(201, '=HYPERLINK("bad")', 80, 81, 82)]
    monkeypatch.setattr(
        student_app,
        "get_db_connection",
        lambda: FakeConnection(rows=dangerous_rows),
    )

    response = client.get("/export_csv")
    assert response.status_code == 200
    decoded = response.data.decode("utf-8-sig")
    parsed = list(csv.reader(io.StringIO(decoded)))
    assert parsed[1][1] == "'=HYPERLINK(\"bad\")"


def test_csv_export_requires_admin(client):
    response = client.get("/export_csv")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")



def test_database_connection_failure_returns_safe_503(client, monkeypatch):
    login_as_admin(client)

    def fail_to_connect(*args, **kwargs):
        raise psycopg2.OperationalError("private database connection details")

    monkeypatch.setattr(student_app, "get_db_connection", REAL_GET_DB_CONNECTION)
    monkeypatch.setattr(student_app.psycopg2, "connect", fail_to_connect)
    response = client.get("/")

    assert response.status_code == 503
    assert b"Service temporarily unavailable" in response.data
    assert b"private database connection details" not in response.data


def test_database_query_failure_rolls_back_and_closes_connection(client, monkeypatch):
    login_as_admin(client)

    class FailingCursor(FakeCursor):
        def execute(self, query, params=None):
            raise psycopg2.OperationalError("private query details")

    class FailingConnection(FakeConnection):
        def __init__(self):
            super().__init__()
            self.fake_cursor = FailingCursor()

    connection = FailingConnection()
    monkeypatch.setattr(student_app, "get_db_connection", REAL_GET_DB_CONNECTION)
    monkeypatch.setattr(
        student_app.psycopg2, "connect", lambda *args, **kwargs: connection
    )
    response = client.get("/")

    assert response.status_code == 503
    assert connection.rolled_back is True
    assert connection.closed is True
    assert b"private query details" not in response.data


def test_unknown_route_uses_custom_404_page(client):
    response = client.get("/this-page-does-not-exist")
    assert response.status_code == 404
    assert b"Page not found" in response.data



def test_about_page_renders(client):
    response = client.get("/about")
    assert response.status_code == 200
    assert b"About EduTrack" in response.data


def test_missing_student_details_returns_404(client, monkeypatch):
    login_as_admin(client)
    monkeypatch.setattr(
        student_app, "get_db_connection", lambda: FakeConnection(one=None)
    )
    response = client.get("/student/999")
    assert response.status_code == 404
    assert b"Page not found" in response.data


def test_missing_edit_student_returns_404_for_admin(client, monkeypatch):
    login_as_admin(client)
    monkeypatch.setattr(
        student_app, "get_db_connection", lambda: FakeConnection(one=None)
    )
    response = client.get("/edit_student/999")
    assert response.status_code == 404


def test_missing_delete_student_returns_404_for_admin(client, monkeypatch):
    login_as_admin(client)
    monkeypatch.setattr(
        student_app, "get_db_connection", lambda: FakeConnection(one=None)
    )
    response = client.get("/delete_student/999")
    assert response.status_code == 404


def test_login_with_missing_fields_returns_validation_message(client):
    response = client.post("/login", data={}, follow_redirects=True)
    assert response.status_code == 200
    assert b"Invalid Username or Password" in response.data



def test_pdf_result_export_requires_admin(client):
    response = client.get("/student/101/result.pdf")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_admin_can_download_student_result_pdf(client):
    login_as_admin(client)
    response = client.get("/student/101/result.pdf")

    assert response.status_code == 200
    assert response.mimetype == "application/pdf"
    assert response.data.startswith(b"%PDF")
    assert "student-101-result.pdf" in response.headers["Content-Disposition"]


def test_pdf_result_for_missing_student_returns_404(client, monkeypatch):
    login_as_admin(client)
    monkeypatch.setattr(
        student_app, "get_db_connection", lambda: FakeConnection(one=None)
    )
    response = client.get("/student/999/result.pdf")
    assert response.status_code == 404



def test_excel_export_neutralizes_formula_names(client, monkeypatch):
    login_as_admin(client)
    dangerous_rows = [(301, "  =HYPERLINK(\"bad\")", 80, 81, 82)]
    monkeypatch.setattr(
        student_app,
        "get_db_connection",
        lambda: FakeConnection(rows=dangerous_rows),
    )

    response = client.get("/export_excel")
    assert response.status_code == 200

    workbook = load_workbook(io.BytesIO(response.data), data_only=False)
    name_cell = workbook["Students"]["B2"]
    assert name_cell.value == "'  =HYPERLINK(\"bad\")"
    assert name_cell.data_type == "s"



@pytest.mark.parametrize("path", ["/", "/view_students", "/student/101"])
def test_student_data_pages_do_not_leak_records_to_guests(client, path):
    response = client.get(path, follow_redirects=True)
    assert response.status_code == 200
    assert b"Asha Das" not in response.data
    assert b"Ravi Kumar" not in response.data
    assert b"Please login as Admin first." in response.data


def test_about_page_remains_public(client):
    response = client.get("/about")
    assert response.status_code == 200
    assert b"About EduTrack" in response.data



def test_guest_navigation_hides_student_and_report_links(client):
    response = client.get("/about")
    assert response.status_code == 200
    assert b"Admin Login" in response.data
    assert b"Students" not in response.data
    assert b"Reports" not in response.data


def test_admin_navigation_shows_student_and_report_links(client):
    login_as_admin(client)
    response = client.get("/")
    assert response.status_code == 200
    assert b"Students" in response.data
    assert b"View Students" in response.data
    assert b"Reports" in response.data
    assert b"Export CSV" in response.data



def test_dashboard_has_personalized_greeting_and_quick_actions(client):
    login_as_admin(client)
    response = client.get("/")
    assert response.status_code == 200
    assert b"Welcome back" in response.data
    assert b"Class overview" in response.data
    assert b"Quick actions" in response.data
    assert b"dashboardDate" in response.data


def test_login_page_has_accessible_password_toggle(client):
    response = client.get("/login")
    assert response.status_code == 200
    assert b"loginUsername" in response.data
    assert b"loginPassword" in response.data
    assert b"togglePassword" in response.data
    assert b"csrf_token" in response.data


def test_theme_toggle_is_available_on_public_and_admin_pages(client):
    public_response = client.get("/about")
    assert public_response.status_code == 200
    assert b"themeToggle" in public_response.data

    login_as_admin(client)
    admin_response = client.get("/")
    assert admin_response.status_code == 200
    assert b"themeToggle" in admin_response.data



def test_student_directory_uses_database_pagination_and_search(client, monkeypatch):
    login_as_admin(client)

    class DirectoryCursor:
        def __init__(self):
            self.executed = []
            self.closed = False
            self.rows = [(301, "Asha Search", 90, 91, 92)]

        def execute(self, query, params=None):
            self.executed.append((query, params))

        def fetchone(self):
            return (45,)

        def fetchall(self):
            return self.rows

        def close(self):
            self.closed = True

    class DirectoryConnection:
        def __init__(self):
            self.cursor_instance = DirectoryCursor()
            self.closed = False

        def cursor(self):
            return self.cursor_instance

        def close(self):
            self.closed = True

    connection = DirectoryConnection()
    monkeypatch.setattr(student_app, "get_db_connection", lambda: connection)

    response = client.get("/view_students?q=Asha&page=2&sort=name")

    assert response.status_code == 200
    assert b"Asha Search" in response.data
    assert b"Showing 21" in response.data
    assert any("ILIKE" in query for query, _ in connection.cursor_instance.executed)
    assert any("LIMIT %s OFFSET %s" in query for query, _ in connection.cursor_instance.executed)
    assert connection.cursor_instance.executed[-1][1] == ("%Asha%", "%Asha%", 20, 20)
    assert connection.cursor_instance.closed is True
    assert connection.closed is True


def test_student_directory_invalid_page_falls_back_to_first_page(client, monkeypatch):
    login_as_admin(client)
    connection = FakeConnection(rows=ROWS)
    # The fake COUNT(*) response is adjusted to the two seeded records.
    connection.fake_cursor.one = (2,)
    monkeypatch.setattr(student_app, "get_db_connection", lambda: connection)

    response = client.get("/view_students?page=not-a-number")

    assert response.status_code == 200
    assert "Showing 1–2 of 2 students".encode("utf-8") in response.data


class UploadFixture:
    def __init__(self, filename, content):
        self.filename = filename
        self.stream = io.BytesIO(content)

    def read(self, size=-1):
        return self.stream.read(size)


def test_student_import_parser_accepts_valid_csv():
    upload = UploadFixture(
        "class.csv",
        b"roll_number,name,math,science,english\n301,Asha Search,90,91,92\n",
    )
    records, error = student_app._read_uploaded_student_file(upload)
    assert error is None
    assert records == [{
        "roll": 301, "name": "Asha Search",
        "math": 90, "science": 91, "english": 92,
    }]


def test_student_import_parser_rejects_duplicate_roll_numbers():
    upload = UploadFixture(
        "class.csv",
        b"roll_number,name,math,science,english\n301,Asha,90,91,92\n301,Ravi,80,81,82\n",
    )
    records, error = student_app._read_uploaded_student_file(upload)
    assert records is None
    assert "duplicate roll numbers" in error.lower()


def test_student_import_parser_rejects_invalid_marks_without_partial_rows():
    upload = UploadFixture(
        "class.csv",
        b"roll_number,name,math,science,english\n301,Asha,90,91,92\n302,Ravi,120,81,82\n",
    )
    records, error = student_app._read_uploaded_student_file(upload)
    assert records is None
    assert "Row 3" in error
    assert "between 0 and 100" in error


@pytest.mark.parametrize("path", [
    "/import_students", "/attendance", "/settings", "/backup",
    "/restore", "/student/101/profile", "/student/101/photo",
])
def test_new_management_features_require_admin(client, path):
    response = client.get(path)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_admin_can_open_student_import_page(client):
    login_as_admin(client)
    response = client.get("/import_students")
    assert response.status_code == 200
    assert b"Required columns" in response.data


def test_admin_navigation_includes_management_tools(client):
    login_as_admin(client)
    response = client.get("/")
    assert response.status_code == 200
    for label in (b"Bulk Import", b"Attendance", b"Settings", b"Download Backup", b"Restore Backup"):
        assert label in response.data


def test_configurable_pass_mark_changes_grade_in_request_context(client):
    with client.session_transaction() as session:
        session["pass_mark"] = 40
    with student_app.app.test_request_context("/"):
        from flask import session as request_session
        request_session["pass_mark"] = 40
        assert student_app.calculate_grade(39) == "F"
        assert student_app.calculate_grade(40) == "C2"


def test_organization_registration_starts_pending(client):
    response = client.post(
        "/register-organization",
        data={
            "organization_name": "Sample Public School",
            "organization_type": "School",
            "registration_number": "SCH-2026-001",
            "contact_person": "Asha Das",
            "email": "office@example.edu",
            "phone": "+91 9876543210",
            "address": "Bhubaneswar, Odisha",
            "password": "a-strong-test-password",
            "confirm_password": "a-strong-test-password",
        },
    )
    assert response.status_code == 302
    assert b"Registration submitted successfully" in response.data
    assert "INSERT INTO organizations" in t.fake_cursor.executed[0][0]
    assert t.committed is True


def test_organization_registration_rejects_short_password(client):
    response = client.post(
        "/register-organization",
        data={
            "organization_name": "Sample Public School",
            "organization_type": "School",
            "contact_person": "Asha Das",
            "email": "office@example.edu",
            "phone": "+91 9876543210",
            "address": "Bhubaneswar, Odisha",
            "password": "short",
            "confirm_password": "short",
        },
    )
    assert response.status_code == 400
    assert b"at least 12 characters" in response.data
