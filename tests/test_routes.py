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



def test_attendance_page_requires_admin(client):
    response = client.get("/attendance")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_admin_can_view_daily_attendance(client, monkeypatch):
    login_as_admin(client)
    rows = [(101, "Asha Das", "present"), (102, "Ravi Kumar", None)]
    connection = FakeConnection(rows=rows)
    monkeypatch.setattr(student_app, "get_db_connection", lambda: connection)

    response = client.get("/attendance?attendance_date=2026-10-31")

    assert response.status_code == 200
    assert b"Attendance Management" in response.data
    assert b"Asha Das" in response.data
    assert b"Present" in response.data
    assert b"Unmarked" in response.data


def test_attendance_post_saves_statuses_in_one_transaction(client, monkeypatch):
    login_as_admin(client)
    connection = FakeConnection(rows=[(101,), (102,)])
    monkeypatch.setattr(student_app, "get_db_connection", lambda: connection)

    response = client.post(
        "/attendance",
        data={
            "attendance_date": "2026-10-31",
            "status_101": "present",
            "status_102": "late",
        },
    )

    assert response.status_code == 302
    assert connection.committed is True
    insert_queries = [
        query for query, _ in connection.fake_cursor.executed
        if "INSERT INTO attendance" in query
    ]
    assert len(insert_queries) == 2
    assert connection.fake_cursor.executed[-1][1] == (102, "2026-10-31", "late")


def test_invalid_attendance_status_is_not_saved(client, monkeypatch):
    login_as_admin(client)
    connection = FakeConnection(rows=[(101,)])
    monkeypatch.setattr(student_app, "get_db_connection", lambda: connection)

    response = client.post(
        "/attendance",
        data={"attendance_date": "2026-10-31", "status_101": "holiday"},
    )

    assert response.status_code == 302
    assert connection.committed is False
    assert len(connection.fake_cursor.executed) == 1


def test_invalid_attendance_date_is_rejected(client, monkeypatch):
    login_as_admin(client)

    def fail_if_db_is_used():
        pytest.fail("Invalid attendance date must be rejected before database access")

    monkeypatch.setattr(student_app, "get_db_connection", fail_if_db_is_used)
    response = client.get("/attendance?attendance_date=not-a-date")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/attendance")
