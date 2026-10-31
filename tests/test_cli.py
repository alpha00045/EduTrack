import csv

import psycopg2

import main as cli_app


class FakeCursor:
    def __init__(self, one=None, execute_error=None):
        self.one = one
        self.execute_error = execute_error
        self.executed = []
        self.closed = False

    def execute(self, query, params=None):
        self.executed.append((query, params))
        if self.execute_error:
            raise self.execute_error

    def fetchone(self):
        return self.one

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self):
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def make_tracker(cursor):
    tracker = cli_app.StudentTracker.__new__(cli_app.StudentTracker)
    tracker.cursor = cursor
    tracker.conn = FakeConnection()
    return tracker


def test_duplicate_student_insert_rolls_back_transaction():
    cursor = FakeCursor(execute_error=psycopg2.IntegrityError("duplicate"))
    tracker = make_tracker(cursor)

    result = tracker.add_student("Asha", "101")

    assert result == "ERROR: STUDENT ALREADY EXISTS"
    assert tracker.conn.rolled_back is True
    assert tracker.conn.committed is False


def test_invalid_subject_is_rejected_without_building_sql():
    cursor = FakeCursor()
    tracker = make_tracker(cursor)

    result = tracker.subject_topper("math; DROP TABLE students")

    assert result == "ERROR: INVALID SUBJECT"
    assert cursor.executed == []


def test_class_average_displays_zero_instead_of_no_data():
    cursor = FakeCursor(one=(0.0,))
    tracker = make_tracker(cursor)

    result = tracker.class_average("math")

    assert result == "Class Average for Math: 0.0"
    assert "AVG(math)" in cursor.executed[0][0]


def test_backup_uses_csv_escaping_for_student_names(tmp_path, monkeypatch):
    tracker = make_tracker(FakeCursor())
    student = cli_app.Student('Das, "Asha"', "101", 80, 90, 85)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(tracker, "get_all_students", lambda: [student])

    assert tracker.backup_data() == "Data backed up to student_backup.txt"

    with open("student_backup.txt", newline="", encoding="utf-8") as file:
        rows = list(csv.reader(file))

    assert rows[0] == ["Roll Number", "Name", "Math", "Science", "English"]
    assert rows[1][1] == 'DAS, "ASHA"'


def test_cli_main_reloads_without_recursion_and_closes_database(monkeypatch):
    class StubTracker:
        closed = False

        def get_all_students(self):
            return []

        def close(self):
            self.closed = True

    tracker = StubTracker()
    choices = iter(["6", "7"])
    monkeypatch.setattr(cli_app, "StudentTracker", lambda: tracker)
    monkeypatch.setattr("builtins.input", lambda prompt="": next(choices))
    monkeypatch.setattr(cli_app, "reloading_data_spinner", lambda duration=1: None)
    monkeypatch.setattr(cli_app, "saving_data_spinner", lambda duration=1: None)

    cli_app.main()

    assert tracker.closed is True
