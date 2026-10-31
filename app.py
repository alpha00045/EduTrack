from flask import (
    Flask,
    request,
    render_template,
    redirect,
    flash,
    Response,
    send_file,
    session
)

from functools import wraps
from io import BytesIO
import hmac

import os
import psycopg2

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment


app = Flask(__name__)

# Load sensitive configuration from environment variables.
SECRET_KEY = os.getenv("SECRET_KEY")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

missing_settings = [
    name for name, value in {
        "SECRET_KEY": SECRET_KEY,
        "ADMIN_USERNAME": ADMIN_USERNAME,
        "ADMIN_PASSWORD": ADMIN_PASSWORD,
    }.items()
    if not value
]

if missing_settings:
    raise RuntimeError(
        "Missing required environment variables: "
        + ", ".join(missing_settings)
    )

app.secret_key = SECRET_KEY

def get_db_connection():
    DATABASE_URL = os.getenv("DATABASE_URL")
    return psycopg2.connect(DATABASE_URL)


def calculate_average(marks):
    valid_marks = [mark for mark in marks if mark is not None]

    if not valid_marks:
        return 0

    return round(sum(valid_marks) / len(valid_marks), 2)


def calculate_grade(average):

    if average >= 90:
        return "A1"
    elif average >= 80:
        return "A2"
    elif average >= 70:
        return "B1"
    elif average >= 60:
        return "B2"
    elif average >= 50:
        return "C1"
    elif average >= 40:
        return "C2"
    elif average >= 33:
        return "D"
    else:
        return "F"
        
def validate_student_form(form, include_roll=True):
    """Validate untrusted form values before sending them to PostgreSQL."""
    name = form.get("name", "").strip()
    if not name or len(name) > 100:
        return None, "Student name is required and must be 100 characters or fewer."

    data = {"name": name}
    if include_roll:
        try:
            roll = int(form.get("roll", ""))
            if roll <= 0:
                raise ValueError
            data["roll"] = roll
        except (TypeError, ValueError):
            return None, "Roll number must be a positive whole number."

    for subject in ("math", "science", "english"):
        try:
            mark = int(form.get(subject, ""))
        except (TypeError, ValueError):
            return None, f"{subject.title()} marks must be a whole number from 0 to 100."
        if mark < 0 or mark > 100:
            return None, f"{subject.title()} marks must be between 0 and 100."
        data[subject] = mark

    return data, None


def admin_required(f):

    @wraps(f)
    def decorated_function(*args, **kwargs):

        if "admin" not in session:

            flash("Please login as Admin first.", "warning")

            return redirect("/login")

        return f(*args, **kwargs)

    return decorated_function

@app.route("/")
def index():

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            roll_number,
            name,
            math,
            science,
            english
        FROM students
    """)

    students = cur.fetchall()

    cur.close()
    conn.close()

    student_data = []

    for student in students:

        average = calculate_average([
            student[2],
            student[3],
            student[4]
        ])

        grade = calculate_grade(average)

        student_data.append({
            "roll": student[0],
            "name": student[1],
            "math": student[2],
            "science": student[3],
            "english": student[4],
            "average": average,
            "grade": grade
        })

# Highest average first
    student_data.sort(
        key=lambda x: x["average"],
        reverse=True
    )

    total_students = len(student_data)

    top_students = student_data[:10]

    averages = [
        student["average"]
        for student in student_data
        if student["average"] > 0
    ]

    class_average = (
        round(sum(averages) / len(averages), 2)
        if averages
        else 0
    )

    highest = (
        max(averages)
        if averages
        else 0
    )

    subjects = 3

    return render_template(
        "students/list.html",
        students=top_students,
        total_students=total_students,
        class_average=class_average,
        highest=highest,
        subjects=subjects
    )
    
@app.route("/view_students")
def view_students():

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            roll_number,
            name,
            math,
            science,
            english
        FROM students
        ORDER BY roll_number
    """)

    students = cur.fetchall()

    cur.close()
    conn.close()

    student_data = []

    for student in students:

        average = calculate_average([
            student[2],
            student[3],
            student[4]
        ])

        grade = calculate_grade(average)

        student_data.append({
            "roll": student[0],
            "name": student[1],
            "math": student[2],
            "science": student[3],
            "english": student[4],
            "average": average,
            "grade": grade
        })

    return render_template(
        "students/view_students.html",
        students=student_data
    )

@app.route("/add_student", methods=["GET", "POST"])
@admin_required
def add_student():

    if request.method == "POST":

        student_form, validation_error = validate_student_form(request.form)
        if validation_error:
            flash(validation_error, "danger")
            return redirect("/add_student")

        conn = get_db_connection()
        cur = conn.cursor()

        try:

            cur.execute(
                """
                INSERT INTO students
                (roll_number, name, math, science, english)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    student_form["roll"],
                    student_form["name"],
                    student_form["math"],
                    student_form["science"],
                    student_form["english"]
                )
            )

            conn.commit()

            flash(
                "🎉 Student added successfully!",
                "success"
            )

            return redirect("/")

        except psycopg2.IntegrityError:

            conn.rollback()

            flash(
                "❌ Roll Number already exists!",
                "danger"
            )

            return redirect("/add_student")

        finally:

            cur.close()
            conn.close()

    return render_template("students/add.html")

@app.route("/student/<int:roll>")
def student_details(roll):

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            roll_number,
            name,
            math,
            science,
            english
        FROM students
        WHERE roll_number = %s
    """, (str(roll),))

    student = cur.fetchone()

    cur.close()
    conn.close()

    if not student:
        return "Student Not Found"

    average = calculate_average([
        student[2],
        student[3],
        student[4]
    ])

    grade = calculate_grade(average)

    student_data = {
        "roll": student[0],
        "name": student[1],
        "math": student[2],
        "science": student[3],
        "english": student[4],
        "average": average,
        "grade": grade
    }

    return render_template(
        "students/details.html",
        student=student_data
    )
    
@app.route("/edit_student/<roll>", methods=["GET", "POST"])
@admin_required
def edit_student(roll):

    conn = get_db_connection()
    cur = conn.cursor()

    if request.method == "POST":

        student_form, validation_error = validate_student_form(request.form, include_roll=False)
        if validation_error:
            cur.close()
            conn.close()
            flash(validation_error, "danger")
            return redirect(f"/edit_student/{roll}")

        cur.execute(
            """
            UPDATE students
            SET
                name=%s,
                math=%s,
                science=%s,
                english=%s
            WHERE roll_number=%s
            """,
            (
                student_form["name"],
                student_form["math"],
                student_form["science"],
                student_form["english"],
                roll
            )
        )

        conn.commit()

        flash(
            "✅ Student updated successfully!",
            "success"
        )

        cur.close()
        conn.close()

        return redirect("/")

    cur.execute(
        """
        SELECT
            roll_number,
            name,
            math,
            science,
            english
        FROM students
        WHERE roll_number=%s
        """,
        (str(roll),)
    )

    student = cur.fetchone()

    cur.close()
    conn.close()

    if not student:
        return "Student Not Found"

    student_data = {
        "roll": student[0],
        "name": student[1],
        "math": student[2],
        "science": student[3],
        "english": student[4]
    }

    return render_template(
        "students/edit.html",
        student=student_data
    )

@app.route("/delete_student/<roll>", methods=["GET", "POST"])
@admin_required
def delete_student(roll):

    conn = get_db_connection()
    cur = conn.cursor()

    # Find the student first
    cur.execute("""
        SELECT
            roll_number,
            name,
            math,
            science,
            english
        FROM students
        WHERE roll_number = %s
    """, (str(roll),))

    student = cur.fetchone()

    if not student:

        cur.close()
        conn.close()

        return "Student Not Found"

    student_data = {
        "roll": student[0],
        "name": student[1],
        "math": student[2],
        "science": student[3],
        "english": student[4]
    }

    # Delete only after confirmation
    if request.method == "POST":

        cur.execute(
            "DELETE FROM students WHERE roll_number = %s",
            (str(roll),)
        )

        conn.commit()

        cur.close()
        conn.close()

        flash(
            "🗑 Student deleted successfully!",
            "success"
        )

        return redirect("/")

    cur.close()
    conn.close()

    return render_template(
        "students/delete.html",
        student=student_data
    )
@app.route("/export_csv")
@admin_required
def export_csv():

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            roll_number,
            name,
            math,
            science,
            english
        FROM students
        ORDER BY roll_number
    """)

    students = cur.fetchall()

    cur.close()
    conn.close()

    def generate():

        yield "Roll Number,Name,Math,Science,English\n"

        for student in students:

            yield (
                f"{student[0]},"
                f"{student[1]},"
                f"{student[2]},"
                f"{student[3]},"
                f"{student[4]}\n"
            )

    return Response(
        generate(),
        mimetype="text/csv",
        headers={
            "Content-Disposition":
            "attachment; filename=students.csv"
        }
    )

@app.route("/export_excel")
@admin_required
def export_excel():

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            roll_number,
            name,
            math,
            science,
            english
        FROM students
        ORDER BY roll_number
    """)

    students = cur.fetchall()

    cur.close()
    conn.close()

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Students"

    sheet.append([
        "Roll Number",
        "Name",
        "Math",
        "Science",
        "English",
        "Average",
        "Grade"
    ])

    # Header styling
    header_fill = PatternFill(
        fill_type="solid",
        fgColor="0D6EFD"
    )

    header_font = Font(
        bold=True,
        color="FFFFFF"
    )

    center = Alignment(
        horizontal="center",
        vertical="center"
    )

    for cell in sheet[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = center

    # Add students
    for student in students:

        average = calculate_average([
            student[2],
            student[3],
            student[4]
        ])

        grade = calculate_grade(average)

        sheet.append([
            student[0],
            student[1],
            student[2],
            student[3],
            student[4],
            average,
            grade
        ])

    # Auto column width
    for column_cells in sheet.columns:

        max_length = 0
        column_letter = column_cells[0].column_letter

        for cell in column_cells:

            if cell.value is not None:
                max_length = max(
                    max_length,
                    len(str(cell.value))
                )

        sheet.column_dimensions[
            column_letter
        ].width = max_length + 5

    # Freeze header row
    sheet.freeze_panes = "A2"

    # Enable Excel filter
    sheet.auto_filter.ref = sheet.dimensions

    # Alignment
    left = Alignment(horizontal="left")
    center = Alignment(horizontal="center")

    for row in sheet.iter_rows(min_row=2):

        row[0].alignment = center
        row[1].alignment = left
        row[2].alignment = center
        row[3].alignment = center
        row[4].alignment = center
        row[5].alignment = center
        row[6].alignment = center

    # Create Excel file in memory
    excel_file = BytesIO()

    workbook.save(excel_file)

    excel_file.seek(0)

    return send_file(
        excel_file,
        download_name="students.xlsx",
        as_attachment=True,
        mimetype=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        )
    )

@app.route("/analytics")
@admin_required
def analytics():
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT roll_number, name, math, science, english
            FROM students
            ORDER BY roll_number
        """)
        records = cur.fetchall()
    finally:
        cur.close()
        conn.close()

    students = []
    subject_totals = {"Math": [], "Science": [], "English": []}
    grade_counts = {"A1": 0, "A2": 0, "B1": 0, "B2": 0,
                    "C1": 0, "C2": 0, "D": 0, "F": 0}

    for row in records:
        marks = row[2:5]
        average = calculate_average(marks)
        grade = calculate_grade(average)
        students.append({
            "roll": row[0], "name": row[1],
            "math": row[2], "science": row[3], "english": row[4],
            "average": average, "grade": grade
        })
        grade_counts[grade] += 1
        for label, mark in zip(subject_totals, marks):
            if mark is not None:
                subject_totals[label].append(mark)

    total_students = len(students)
    overall_average = calculate_average(
        [s["average"] for s in students]
    )
    passed = sum(
        1 for s in students
        if all(mark is not None and mark >= 33
               for mark in (s["math"], s["science"], s["english"]))
    )
    failed = total_students - passed
    subject_averages = {
        label: calculate_average(values)
        for label, values in subject_totals.items()
    }
    top_students = sorted(
        students, key=lambda item: item["average"], reverse=True
    )[:5]

    return render_template(
        "analytics/dashboard.html",
        total_students=total_students,
        overall_average=overall_average,
        passed=passed,
        failed=failed,
        subject_averages=subject_averages,
        grade_counts=grade_counts,
        top_students=top_students
    )


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        if hmac.compare_digest(username, ADMIN_USERNAME) and hmac.compare_digest(password, ADMIN_PASSWORD):
            session["admin"] = username
            flash("Login Successful!", "success")
            return redirect("/")
        else:
            flash("Invalid Username or Password!", "danger")

    return render_template("auth/login.html")

@app.route("/logout")
def logout():

    session.pop("admin", None)

    flash("Logged out successfully!", "success")

    return redirect("/")

if __name__ == "__main__":
    app.run(debug=True)
    
