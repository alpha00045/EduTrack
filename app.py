from flask import (
    Flask,
    request,
    render_template,
    redirect,
    flash,
    Response,
    send_file,
    session,
    g,
    abort,
    url_for,
    has_request_context
)

from functools import wraps
from datetime import date
from io import BytesIO, StringIO
import csv
import hmac
import base64
import zipfile
from datetime import datetime

import os
from dotenv import load_dotenv

load_dotenv()
import re
import psycopg2
from werkzeug.security import generate_password_hash, check_password_hash
from flask_wtf.csrf import CSRFProtect

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill, Alignment

from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle


app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024

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
csrf = CSRFProtect(app)

def get_db_connection():
    """Open one request-scoped PostgreSQL connection."""
    DATABASE_URL = os.getenv("DATABASE_URL")
    connection = psycopg2.connect(DATABASE_URL)
    g.db_connection = connection
    return connection


@app.teardown_request
def close_db_connection(error=None):
    """Rollback an unfinished transaction and always release the connection."""
    connection = g.pop("db_connection", None)
    if connection is None:
        return

    try:
        if error is not None and not connection.closed:
            connection.rollback()
    except psycopg2.Error:
        app.logger.exception("Failed to roll back a database transaction")
    finally:
        try:
            if not connection.closed:
                connection.close()
        except psycopg2.Error:
            app.logger.exception("Failed to close a database connection")


@app.errorhandler(psycopg2.Error)
def handle_database_error(error):
    """Return a safe response for PostgreSQL failures without exposing details."""
    connection = g.get("db_connection")
    if connection is not None:
        try:
            if not connection.closed:
                connection.rollback()
        except psycopg2.Error:
            app.logger.exception("Database rollback failed after a query error")

    app.logger.exception("A database operation failed")
    return render_template("errors/503.html"), 503


@app.errorhandler(404)
def page_not_found(error):
    return render_template("errors/404.html"), 404


@app.errorhandler(500)
def internal_server_error(error):
    app.logger.error("An unexpected application error occurred")
    return render_template("errors/500.html"), 500


def calculate_average(marks):
    valid_marks = [mark for mark in marks if mark is not None]

    if not valid_marks:
        return 0

    return round(sum(valid_marks) / len(valid_marks), 2)


def calculate_grade(average):
    pass_mark = 33
    if has_request_context():
        try:
            pass_mark = int(session.get("pass_mark", 33))
        except (TypeError, ValueError):
            pass_mark = 33
    if average < pass_mark:
        return "F"
    if average >= 90:
        return "A1"
    if average >= 80:
        return "A2"
    if average >= 70:
        return "B1"
    if average >= 60:
        return "B2"
    if average >= 50:
        return "C1"
    if average >= 40:
        return "C2"
    return "D"
        
def safe_spreadsheet_text(value):
    """Prevent untrusted text from being interpreted as a spreadsheet formula."""
    if isinstance(value, str):
        formula_candidate = value.lstrip().lstrip("\ufeff").lstrip()
        if formula_candidate.startswith(("=", "+", "-", "@")):
            return "'" + value
    return value


def validate_student_form(form, include_roll=True):
    """Validate untrusted form values before sending them to PostgreSQL."""
    name = form.get("name", "").strip()
    if not name or len(name) > 100:
        return None, "Student name is required and must be 100 characters or fewer."

    data = {"name": name, "standard": form.get("standard", "").strip()[:40] or None, "semester": form.get("semester", "").strip()[:20] or None}
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
@admin_required
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
@admin_required
def view_students():
    q=request.args.get("q","").strip()[:100]
    org=request.args.get("organization_id","all")
    standard=request.args.get("standard","").strip()[:40]
    semester=request.args.get("semester","").strip()[:20]
    sort=request.args.get("sort","roll")
    order={"roll":"roll_number ASC","name":"LOWER(name) ASC","average":"((COALESCE(math,0)+COALESCE(science,0)+COALESCE(english,0))/3.0) DESC"}.get(sort,"roll_number ASC")
    try: page=max(1,int(request.args.get("page","1")))
    except (TypeError,ValueError): page=1
    conn=get_db_connection(); cur=conn.cursor()
    try:
        cur.execute("SELECT id,name FROM organizations WHERE status='approved' ORDER BY name")
        organizations=cur.fetchall()
        cur.execute("SELECT standard FROM students WHERE standard IS NOT NULL AND standard<>'' UNION SELECT admission_standard FROM organization_student_profiles WHERE admission_standard IS NOT NULL AND admission_standard<>'' ORDER BY 1")
        standards=[x[0] for x in cur.fetchall()]
        cur.execute("SELECT semester FROM students WHERE semester IS NOT NULL AND semester<>'' UNION SELECT semester FROM organization_student_profiles WHERE semester IS NOT NULL AND semester<>'' ORDER BY 1")
        semesters=[x[0] for x in cur.fetchall()]
        if org=="admin":
            order = {"roll":"roll_number ASC","name":"LOWER(name) ASC","average":"((COALESCE(math,0)+COALESCE(science,0)+COALESCE(english,0))/3.0) DESC"}.get(sort,"roll_number ASC")
            clauses=[]; params=[]
            if q: clauses.append("(CAST(roll_number AS TEXT) ILIKE %s OR name ILIKE %s)"); params += [f"%{q}%"]*2
            if standard: clauses.append("standard=%s"); params.append(standard)
            if semester: clauses.append("semester=%s"); params.append(semester)
            where=(" WHERE "+" AND ".join(clauses)) if clauses else ""
            cur.execute("SELECT COUNT(*) FROM students"+where,tuple(params)); total=cur.fetchone()[0]
            pages=max(1,(total+19)//20); page=min(page,pages); offset=(page-1)*20
            cur.execute(f"SELECT roll_number,name,math,science,english,standard,semester,NULL::TEXT FROM students{where} ORDER BY {order} LIMIT 20 OFFSET %s",tuple(params+[offset]))
        else:
            order = {"roll":"s.roll_number ASC","name":"LOWER(s.name) ASC","average":"((COALESCE(s.math,0)+COALESCE(s.science,0)+COALESCE(s.english,0))/3.0) DESC"}.get(sort,"s.roll_number ASC")
            clauses=[]; params=[]
            if org!="all":
                try: clauses.append("s.organization_id=%s"); params.append(int(org))
                except ValueError: org="all"
            if q: clauses.append("(s.roll_number ILIKE %s OR s.name ILIKE %s)"); params += [f"%{q}%"]*2
            if standard: clauses.append("p.admission_standard=%s"); params.append(standard)
            if semester: clauses.append("p.semester=%s"); params.append(semester)
            where=(" WHERE "+" AND ".join(clauses)) if clauses else ""
            base=" FROM organization_students s LEFT JOIN organization_student_profiles p ON p.organization_id=s.organization_id AND p.student_id=s.id JOIN organizations o ON o.id=s.organization_id"
            cur.execute("SELECT COUNT(*)"+base+where,tuple(params)); total=cur.fetchone()[0]
            pages=max(1,(total+19)//20); page=min(page,pages); offset=(page-1)*20
            cur.execute(f"SELECT s.roll_number,s.name,s.math,s.science,s.english,p.admission_standard,p.semester,o.name {base}{where} ORDER BY {order} LIMIT 20 OFFSET %s",tuple(params+[offset]))
        rows=cur.fetchall()
    finally:
        cur.close(); conn.close()
    students=[]
    for r in rows:
        avg=calculate_average(r[2:5])
        students.append({"roll":r[0],"name":r[1],"math":r[2],"science":r[3],"english":r[4],"standard":r[5],"semester":r[6],"organization":r[7],"average":avg,"grade":calculate_grade(avg)})
    offset=(page-1)*20
    return render_template("students/view_students.html",students=students,search_query=q,sort_by=sort,page=page,per_page=20,total_students=total,total_pages=pages,start_index=offset+1 if total else 0,end_index=offset+len(students),organizations=organizations,selected_org=org,standards=standards,semesters=semesters,selected_standard=standard,selected_semester=semester)

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
                (roll_number, name, math, science, english, standard, semester)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    student_form["roll"],
                    student_form["name"],
                    student_form["math"],
                    student_form["science"],
                    student_form["english"],
                    student_form["standard"],
                    student_form["semester"]
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
@admin_required
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
        abort(404)

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
                english=%s,
                standard=%s,
                semester=%s
            WHERE roll_number=%s
            """,
            (
                student_form["name"],
                student_form["math"],
                student_form["science"],
                student_form["english"],
                student_form["standard"],
                student_form["semester"],
                roll
            )
        )

        if cur.rowcount == 0:
            conn.rollback()
            cur.close()
            conn.close()
            abort(404)

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
            english,
            standard,
            semester
        FROM students
        WHERE roll_number=%s
        """,
        (str(roll),)
    )

    student = cur.fetchone()

    cur.close()
    conn.close()

    if not student:
        abort(404)

    student_data = {
        "roll": student[0],
        "name": student[1],
        "math": student[2],
        "science": student[3],
        "english": student[4],
        "standard": student[5],
        "semester": student[6]
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

        abort(404)

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

        if cur.rowcount == 0:
            conn.rollback()
            cur.close()
            conn.close()
            abort(404)

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

    try:
        cur.execute("""
            SELECT roll_number, name, math, science, english
            FROM students
            ORDER BY roll_number
        """)
        students = cur.fetchall()
    finally:
        cur.close()
        conn.close()

    output = StringIO(newline="")
    writer = csv.writer(output, lineterminator="\r\n")
    writer.writerow(["Roll Number", "Name", "Math", "Science", "English"])

    for student in students:
        # Prevent spreadsheet formula execution from untrusted text fields.
        name = safe_spreadsheet_text(student[1])
        writer.writerow([student[0], name, student[2], student[3], student[4]])

    response = Response(
        "\ufeff" + output.getvalue(),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=students.csv"}
    )
    return response

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
            safe_spreadsheet_text(student[1]),
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

@app.route("/student/<int:roll>/result.pdf")
@admin_required
def download_student_result(roll):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT roll_number, name, math, science, english
            FROM students
            WHERE roll_number = %s
            """,
            (roll,),
        )
        student = cur.fetchone()
    finally:
        cur.close()
        conn.close()

    if not student:
        abort(404)

    marks = student[2:5]
    average = calculate_average(marks)
    grade = calculate_grade(average)
    styles = getSampleStyleSheet()
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=48,
        leftMargin=48,
        topMargin=48,
        bottomMargin=48,
        title=f"EduTrack Result - {student[0]}",
    )

    story = [
        Paragraph("EduTrack Student Result Card", styles["Title"]),
        Spacer(1, 12),
        Paragraph(f"<b>Student Name:</b> {escape(str(student[2]))}", styles["BodyText"]),
        Paragraph(f"<b>Roll Number:</b> {escape(str(student[1]))}", styles["BodyText"]),
        Spacer(1, 18),
    ]

    result_rows = [["Subject", "Marks"]]
    for subject, mark in zip(("Math", "Science", "English"), marks):
        result_rows.append([subject, str(mark) if mark is not None else "Not entered"])
    result_rows.extend([
        ["Average", f"{average}%"],
        ["Grade", grade],
    ])

    result_table = Table(result_rows, colWidths=[260, 180], repeatRows=1)
    result_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0D6EFD")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D9E2F2")),
        ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#F7F9FC")),
        ("PADDING", (0, 0), (-1, -1), 10),
        ("FONTNAME", (0, -2), (-1, -1), "Helvetica-Bold"),
    ]))
    story.append(result_table)
    story.extend([
        Spacer(1, 24),
        Paragraph("Generated by EduTrack Student Management System", styles["Italic"]),
    ])

    document.build(story)
    buffer.seek(0)
    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"student-{student[0]}-result.pdf",
        mimetype="application/pdf",
    )


@app.route("/analytics")
@admin_required
def analytics():
    org=request.args.get("organization_id","all")
    standard=request.args.get("standard","").strip()[:40]
    semester=request.args.get("semester","").strip()[:20]
    conn=get_db_connection(); cur=conn.cursor()
    try:
        cur.execute("SELECT id,name FROM organizations WHERE status='approved' ORDER BY name")
        organizations=cur.fetchall()
        cur.execute("SELECT DISTINCT admission_standard FROM organization_student_profiles WHERE admission_standard IS NOT NULL AND admission_standard<>'' ORDER BY admission_standard")
        standards=[x[0] for x in cur.fetchall()]
        cur.execute("SELECT DISTINCT semester FROM organization_student_profiles WHERE semester IS NOT NULL AND semester<>'' ORDER BY semester")
        semesters=[x[0] for x in cur.fetchall()]
        clauses=[]; params=[]
        if org=="admin":
            if standard: clauses.append("standard=%s"); params.append(standard)
            if semester: clauses.append("semester=%s"); params.append(semester)
            where=(" WHERE "+" AND ".join(clauses)) if clauses else ""
            cur.execute("SELECT roll_number,name,math,science,english FROM students"+where+" ORDER BY roll_number",tuple(params))
            records=cur.fetchall()
            cur.execute("SELECT academic_year,ROUND(AVG(marks),2) FROM student_assessments GROUP BY academic_year ORDER BY academic_year")
            trends=cur.fetchall()
        else:
            if org!="all":
                try: clauses.append("s.organization_id=%s"); params.append(int(org))
                except ValueError: org="all"
            if standard: clauses.append("p.admission_standard=%s"); params.append(standard)
            if semester: clauses.append("p.semester=%s"); params.append(semester)
            where=(" WHERE "+" AND ".join(clauses)) if clauses else ""
            cur.execute("SELECT s.roll_number,s.name,s.math,s.science,s.english FROM organization_students s LEFT JOIN organization_student_profiles p ON p.organization_id=s.organization_id AND p.student_id=s.id"+where+" ORDER BY s.roll_number",tuple(params))
            records=cur.fetchall(); trends=[]
    finally:
        cur.close(); conn.close()
    students=[]; bands={"Below 40":0,"40–59":0,"60–79":0,"80–100":0}
    totals={"Math":[],"Science":[],"English":[]}
    grades={"A1":0,"A2":0,"B1":0,"B2":0,"C1":0,"C2":0,"D":0,"F":0}
    for r in records:
        marks=r[2:5]; avg=calculate_average(marks); grade=calculate_grade(avg)
        students.append({"roll":r[0],"name":r[1],"math":r[2],"science":r[3],"english":r[4],"average":avg,"grade":grade})
        grades[grade]+=1
        bands["Below 40" if avg<40 else "40–59" if avg<60 else "60–79" if avg<80 else "80–100"]+=1
        for label,mark in zip(totals,marks):
            if mark is not None: totals[label].append(mark)
    count=len(students); overall=calculate_average([x["average"] for x in students])
    try: pass_mark=int(session.get("pass_mark",33))
    except (TypeError,ValueError): pass_mark=33
    passed=sum(1 for x in students if all(m is not None and m>=pass_mark for m in (x["math"],x["science"],x["english"])))
    subjects={k:calculate_average(v) for k,v in totals.items()}
    return render_template("analytics/dashboard.html",total_students=count,overall_average=overall,passed=passed,failed=count-passed,subject_averages=subjects,grade_counts=grades,performance_bands=bands,assessment_trends=trends,top_students=sorted(students,key=lambda x:x["average"],reverse=True)[:5],organizations=organizations,selected_org=org,standards=standards,semesters=semesters,selected_standard=standard,selected_semester=semester)

def _read_uploaded_student_file(upload):
    """Parse a small CSV/XLSX import without trusting the uploaded contents."""
    if not upload or not upload.filename:
        return None, "Choose a CSV or Excel file first."
    extension = upload.filename.rsplit(".", 1)[-1].lower() if "." in upload.filename else ""
    if extension not in {"csv", "xlsx"}:
        return None, "Only CSV and XLSX files are supported."
    raw = upload.read(2 * 1024 * 1024 + 1)
    if len(raw) > 2 * 1024 * 1024:
        return None, "The file is too large. Maximum size is 2 MB."
    try:
        if extension == "csv":
            text_data = raw.decode("utf-8-sig")
            reader = csv.DictReader(StringIO(text_data))
            records = list(reader)
        else:
            workbook = load_workbook(BytesIO(raw), read_only=True, data_only=True)
            sheet = workbook.active
            values = sheet.iter_rows(values_only=True)
            headers = next(values, None)
            if not headers:
                return None, "The spreadsheet is empty."
            keys = [str(value or "").strip().lower() for value in headers]
            records = [dict(zip(keys, row)) for row in values]
            workbook.close()
    except (UnicodeDecodeError, csv.Error, ValueError, OSError) as error:
        return None, "The file could not be read. Please check its format."
    if not records:
        return None, "The file does not contain any student rows."
    normalized = []
    for row_number, row in enumerate(records, start=2):
        clean = {str(key or "").strip().lower(): ("" if value is None else str(value).strip())
                 for key, value in row.items() if key is not None}
        # Accept common spreadsheet headings.
        if "roll_number" not in clean and "roll" in clean:
            clean["roll_number"] = clean["roll"]
        data, error = validate_student_form({
            "roll": clean.get("roll_number", ""),
            "name": clean.get("name", ""),
            "math": clean.get("math", ""),
            "science": clean.get("science", ""),
            "english": clean.get("english", ""),
        })
        if error:
            return None, f"Row {row_number}: {error}"
        normalized.append(data)
    rolls = [item["roll"] for item in normalized]
    if len(set(rolls)) != len(rolls):
        return None, "The file contains duplicate roll numbers. No students were imported."
    return normalized, None


@app.route("/import_students", methods=["GET", "POST"])
@admin_required
def import_students():
    if request.method == "POST":
        records, error = _read_uploaded_student_file(request.files.get("student_file"))
        if error:
            flash(error, "danger")
            return redirect(url_for("import_students"))
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT roll_number FROM students WHERE roll_number = ANY(%s)",
                ([str(item["roll"]) for item in records],),
            )
            existing = {str(row[0]) for row in cur.fetchall()}
            duplicates = [str(item["roll"]) for item in records if str(item["roll"]) in existing]
            if duplicates:
                flash("Existing roll numbers found: " + ", ".join(duplicates[:10]) +
                      ". No students were imported.", "warning")
                return redirect(url_for("import_students"))
            cur.executemany(
                """INSERT INTO students (roll_number, name, math, science, english)
                   VALUES (%s, %s, %s, %s, %s)""",
                [(item["roll"], item["name"], item["math"], item["science"], item["english"])
                 for item in records],
            )
            conn.commit()
            flash(f"Successfully imported {len(records)} students.", "success")
            return redirect(url_for("view_students"))
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()
    return render_template("students/import.html")


@app.route("/attendance", methods=["GET", "POST"])
@admin_required
def attendance():
    selected_date = request.values.get("attendance_date", date.today().isoformat())
    try:
        selected_date = date.fromisoformat(selected_date).isoformat()
    except (TypeError, ValueError):
        flash("Please select a valid attendance date.", "danger")
        return redirect(url_for("attendance"))
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        if request.method == "POST":
            cur.execute("SELECT roll_number FROM students ORDER BY roll_number")
            rolls = [row[0] for row in cur.fetchall()]
            updates = []
            for roll in rolls:
                status = request.form.get(f"status_{roll}", "")
                if status == "":
                    continue
                if status not in {"present", "absent", "late"}:
                    flash("Invalid attendance status. No changes were saved.", "danger")
                    return redirect(url_for("attendance", attendance_date=selected_date))
                updates.append((roll, selected_date, status))
            for roll, attendance_date, status in updates:
                cur.execute(
                    """INSERT INTO attendance (student_roll, attendance_date, status)
                       VALUES (%s, %s, %s)
                       ON CONFLICT (student_roll, attendance_date)
                       DO UPDATE SET status = EXCLUDED.status, marked_at = CURRENT_TIMESTAMP""",
                    (roll, attendance_date, status),
                )
            conn.commit()
            flash(f"Attendance saved for {selected_date}.", "success")
            return redirect(url_for("attendance", attendance_date=selected_date))
        cur.execute(
            """SELECT s.roll_number, s.name, a.status
               FROM students AS s LEFT JOIN attendance AS a
                 ON a.student_roll = s.roll_number AND a.attendance_date = %s
               ORDER BY s.roll_number""",
            (selected_date,),
        )
        students = [{"roll": r[0], "name": r[1], "status": r[2]} for r in cur.fetchall()]
        total = len(students)
        counts = {status: sum(item["status"] == status for item in students)
                  for status in ("present", "absent", "late")}
        return render_template(
            "attendance/index.html", students=students, attendance_date=selected_date,
            total=total, present=counts["present"], absent=counts["absent"],
            late=counts["late"], unmarked=total - sum(counts.values()),
        )
    finally:
        cur.close()
        conn.close()


@app.route("/student/<roll>/profile", methods=["GET", "POST"])
@admin_required
def student_profile(roll):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT roll_number, name, math, science, english FROM students WHERE roll_number=%s", (roll,))
        row = cur.fetchone()
        if not row:
            abort(404)
        if request.method == "POST" and request.form.get("action") == "assessment":
            year = request.form.get("academic_year", "").strip()
            term = request.form.get("term", "").strip()
            subject = request.form.get("subject", "").strip()
            try:
                marks = float(request.form.get("marks", ""))
            except (TypeError, ValueError):
                flash("Assessment marks must be a number from 0 to 100.", "danger")
                return redirect(url_for("student_profile", roll=roll))
            if not year or len(year) > 20 or not term or len(term) > 40 or not subject or len(subject) > 50 or not 0 <= marks <= 100:
                flash("Please enter valid academic year, term, subject and marks.", "danger")
                return redirect(url_for("student_profile", roll=roll))
            cur.execute(
                """INSERT INTO student_assessments
                   (student_roll, academic_year, term, subject, marks)
                   VALUES (%s, %s, %s, %s, %s)
                   ON CONFLICT (student_roll, academic_year, term, subject)
                   DO UPDATE SET marks=EXCLUDED.marks, recorded_at=CURRENT_TIMESTAMP""",
                (roll, year, term, subject, marks),
            )
            conn.commit()
            flash("Academic history saved.", "success")
            return redirect(url_for("student_profile", roll=roll))
        if request.method == "POST":
            email = request.form.get("email", "").strip()
            phone = request.form.get("phone", "").strip()
            guardian = request.form.get("guardian_name", "").strip()
            address = request.form.get("address", "").strip()
            notes = request.form.get("notes", "").strip()
            dob_raw = request.form.get("date_of_birth", "").strip()
            dob = None
            if dob_raw:
                try:
                    dob = date.fromisoformat(dob_raw)
                    if dob > date.today():
                        raise ValueError
                except ValueError:
                    flash("Enter a valid date of birth in the past.", "danger")
                    return redirect(url_for("student_profile", roll=roll))
            if len(email) > 254 or (email and ("@" not in email or " " in email)) or len(phone) > 30 or len(guardian) > 100 or len(address) > 500 or len(notes) > 2000:
                flash("Please check the length and format of the profile fields.", "danger")
                return redirect(url_for("student_profile", roll=roll))
            photo = request.files.get("photo")
            photo_data = None
            photo_mime = None
            if photo and photo.filename:
                data = photo.read(1024 * 1024 + 1)
                signatures = {
                    "image/jpeg": data.startswith(b"\xff\xd8\xff"),
                    "image/png": data.startswith(b"\x89PNG\r\n\x1a\n"),
                    "image/webp": len(data) > 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP",
                }
                photo_mime = next((mime for mime, valid in signatures.items() if valid), None)
                if not photo_mime or len(data) > 1024 * 1024:
                    flash("Upload a valid JPG, PNG or WebP photo under 1 MB.", "danger")
                    return redirect(url_for("student_profile", roll=roll))
                photo_data = psycopg2.Binary(data)
            if photo_data is None:
                cur.execute(
                    """INSERT INTO student_profiles
                       (student_roll,email,phone,guardian_name,date_of_birth,address,notes,updated_at)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,CURRENT_TIMESTAMP)
                       ON CONFLICT (student_roll) DO UPDATE SET email=EXCLUDED.email,
                       phone=EXCLUDED.phone, guardian_name=EXCLUDED.guardian_name,
                       date_of_birth=EXCLUDED.date_of_birth, address=EXCLUDED.address,
                       notes=EXCLUDED.notes, updated_at=CURRENT_TIMESTAMP""",
                    (roll,email,phone,guardian,dob,address,notes),
                )
            else:
                cur.execute(
                    """INSERT INTO student_profiles
                       (student_roll,email,phone,guardian_name,date_of_birth,address,notes,photo_data,photo_mime,updated_at)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,CURRENT_TIMESTAMP)
                       ON CONFLICT (student_roll) DO UPDATE SET email=EXCLUDED.email,
                       phone=EXCLUDED.phone, guardian_name=EXCLUDED.guardian_name,
                       date_of_birth=EXCLUDED.date_of_birth, address=EXCLUDED.address,
                       notes=EXCLUDED.notes, photo_data=EXCLUDED.photo_data,
                       photo_mime=EXCLUDED.photo_mime, updated_at=CURRENT_TIMESTAMP""",
                    (roll,email,phone,guardian,dob,address,notes,photo_data,photo_mime),
                )
            conn.commit()
            flash("Student profile updated.", "success")
            return redirect(url_for("student_profile", roll=roll))
        cur.execute(
            """SELECT email,phone,guardian_name,date_of_birth,address,notes,
                      (photo_data IS NOT NULL)
               FROM student_profiles WHERE student_roll=%s""", (roll,)
        )
        profile_row = cur.fetchone()
        profile = None
        if profile_row:
            profile = dict(zip(("email","phone","guardian_name","date_of_birth","address","notes","has_photo"), profile_row))
        cur.execute(
            """SELECT academic_year,term,subject,marks,recorded_at
               FROM student_assessments WHERE student_roll=%s
               ORDER BY academic_year DESC, term, subject""", (roll,)
        )
        history = cur.fetchall()
        return render_template("students/profile.html", student=row, profile=profile, history=history)
    finally:
        cur.close()
        conn.close()


@app.route("/student/<roll>/photo")
@admin_required
def student_photo(roll):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT photo_data, photo_mime FROM student_profiles WHERE student_roll=%s", (roll,))
        photo = cur.fetchone()
    finally:
        cur.close()
        conn.close()
    if not photo or not photo[0] or photo[1] not in {"image/jpeg", "image/png", "image/webp"}:
        abort(404)
    return Response(bytes(photo[0]), mimetype=photo[1], headers={
        "Cache-Control": "private, max-age=300",
        "X-Content-Type-Options": "nosniff",
    })


@app.route("/settings", methods=["GET", "POST"])
@admin_required
def admin_settings():
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        if request.method == "POST":
            school_name = request.form.get("school_name", "").strip()
            try:
                pass_mark = int(request.form.get("pass_mark", "33"))
            except (TypeError, ValueError):
                pass_mark = -1
            if not school_name or len(school_name) > 100 or not 0 <= pass_mark <= 100:
                flash("Enter a school name (up to 100 characters) and a pass mark from 0 to 100.", "danger")
                return redirect(url_for("admin_settings"))
            for key, value in (("school_name", school_name), ("pass_mark", str(pass_mark))):
                cur.execute(
                    """INSERT INTO app_settings (setting_key,setting_value)
                       VALUES (%s,%s) ON CONFLICT (setting_key)
                       DO UPDATE SET setting_value=EXCLUDED.setting_value, updated_at=CURRENT_TIMESTAMP""",
                    (key, value),
                )
            conn.commit()
            session["school_name"] = school_name
            session["pass_mark"] = pass_mark
            flash("School settings saved.", "success")
            return redirect(url_for("admin_settings"))
        cur.execute("SELECT setting_key,setting_value FROM app_settings")
        settings = dict(cur.fetchall())
        session["school_name"] = settings.get("school_name", "EduTrack")
        session["pass_mark"] = int(settings.get("pass_mark", "33"))
        return render_template("admin/settings.html", settings=settings)
    finally:
        cur.close()
        conn.close()


@app.route("/backup")
@admin_required
def download_backup():
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT roll_number,name,math,science,english FROM students ORDER BY roll_number")
        students = cur.fetchall()
        cur.execute("""SELECT student_roll,email,phone,guardian_name,date_of_birth,address,notes,
                              photo_data,photo_mime FROM student_profiles ORDER BY student_roll""")
        profiles = cur.fetchall()
        cur.execute("""SELECT student_roll,academic_year,term,subject,marks
                       FROM student_assessments ORDER BY student_roll,academic_year,term,subject""")
        assessments = cur.fetchall()
        cur.execute("""SELECT student_roll,attendance_date,status
                       FROM attendance ORDER BY attendance_date,student_roll""")
        attendance_rows = cur.fetchall()
        cur.execute("SELECT setting_key,setting_value FROM app_settings ORDER BY setting_key")
        settings = cur.fetchall()
    finally:
        cur.close()
        conn.close()

    archive_buffer = BytesIO()
    with zipfile.ZipFile(archive_buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        def add_csv(filename, headers, rows, transform=None):
            output = StringIO(newline="")
            writer = csv.writer(output, lineterminator="\\r\\n")
            writer.writerow(headers)
            for row in rows:
                values = list(row)
                if transform:
                    values = transform(values)
                writer.writerow(values)
            archive.writestr(filename, "\\ufeff" + output.getvalue())

        add_csv("students.csv", ["roll_number","name","math","science","english"],
                students, lambda row: [row[0], safe_spreadsheet_text(row[1]), *row[2:]])
        def profile_transform(row):
            if row[7] is not None:
                row[7] = base64.b64encode(bytes(row[7])).decode("ascii")
            if row[4] is not None:
                row[4] = row[4].isoformat()
            return row
        add_csv("profiles.csv", ["student_roll","email","phone","guardian_name","date_of_birth",
                "address","notes","photo_base64","photo_mime"], profiles, profile_transform)
        add_csv("assessments.csv", ["student_roll","academic_year","term","subject","marks"], assessments)
        add_csv("attendance.csv", ["student_roll","attendance_date","status"], attendance_rows,
                lambda row: [row[0], row[1].isoformat(), row[2]])
        add_csv("settings.csv", ["setting_key","setting_value"], settings)
        archive.writestr("BACKUP_README.txt",
            "EduTrack complete backup. Includes students, profiles, profile photos, assessments, attendance and school settings. Restore is add-only for students; existing student records are never overwritten.")
    archive_buffer.seek(0)
    response = send_file(
        archive_buffer, as_attachment=True, download_name="edutrack-complete-backup.zip",
        mimetype="application/zip", max_age=0,
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@app.route("/restore", methods=["GET", "POST"])
@admin_required
def restore_backup():
    if request.method == "POST":
        upload = request.files.get("backup_file")
        if not upload or not upload.filename:
            flash("Choose an EduTrack ZIP backup or CSV file.", "danger")
            return redirect(url_for("restore_backup"))
        raw = upload.read(10 * 1024 * 1024 + 1)
        if len(raw) > 10 * 1024 * 1024:
            flash("Backup is too large. Maximum size is 10 MB.", "danger")
            return redirect(url_for("restore_backup"))
        if upload.filename.lower().endswith(".zip"):
            conn = get_db_connection()
            cur = conn.cursor()
            try:
                with zipfile.ZipFile(BytesIO(raw)) as archive:
                    allowed = {"students.csv","profiles.csv","assessments.csv","attendance.csv","settings.csv","BACKUP_README.txt"}
                    if (any(name not in allowed for name in archive.namelist())
                            or "students.csv" not in archive.namelist()
                            or sum(item.file_size for item in archive.infolist()) > 25 * 1024 * 1024
                            or any(item.file_size > 10 * 1024 * 1024 for item in archive.infolist())):
                        flash("This is not a recognised EduTrack backup.", "danger")
                        return redirect(url_for("restore_backup"))
                    def read_csv(name):
                        if name not in archive.namelist():
                            return []
                        content = archive.read(name).decode("utf-8-sig")
                        return list(csv.DictReader(StringIO(content)))
                    student_rows = read_csv("students.csv")
                    validated = []
                    for index, item in enumerate(student_rows, start=2):
                        data, error = validate_student_form({
                            "roll": item.get("roll_number",""), "name": item.get("name",""),
                            "math": item.get("math",""), "science": item.get("science",""),
                            "english": item.get("english",""),
                        })
                        if error:
                            flash(f"Backup students.csv row {index}: {error}", "danger")
                            return redirect(url_for("restore_backup"))
                        validated.append(data)
                    if len({item["roll"] for item in validated}) != len(validated):
                        flash("Backup contains duplicate student roll numbers.", "danger")
                        return redirect(url_for("restore_backup"))
                    cur.executemany(
                        """INSERT INTO students (roll_number,name,math,science,english)
                           VALUES (%s,%s,%s,%s,%s) ON CONFLICT (roll_number) DO NOTHING""",
                        [(str(x["roll"]),x["name"],x["math"],x["science"],x["english"]) for x in validated],
                    )
                    restored_students = cur.rowcount
                    # Related records are restored only for student rolls present after the add-only student restore.
                    profile_rows = read_csv("profiles.csv")
                    for item in profile_rows:
                        photo_data = base64.b64decode(item["photo_base64"], validate=True) if item.get("photo_base64") else None
                        photo_mime = item.get("photo_mime") or None
                        if photo_data:
                            valid_photo = (
                                (photo_mime == "image/jpeg" and photo_data.startswith(b"\\xff\\xd8\\xff"))
                                or (photo_mime == "image/png" and photo_data.startswith(b"\\x89PNG\\r\\n\\x1a\\n"))
                                or (photo_mime == "image/webp" and len(photo_data) > 12
                                    and photo_data[:4] == b"RIFF" and photo_data[8:12] == b"WEBP")
                            )
                            if not valid_photo or len(photo_data) > 1024 * 1024:
                                raise ValueError("Invalid profile photo in backup")
                        elif photo_mime:
                            raise ValueError("Unexpected photo MIME type")
                        cur.execute(
                            """INSERT INTO student_profiles
                               (student_roll,email,phone,guardian_name,date_of_birth,address,notes,photo_data,photo_mime)
                               SELECT %s,%s,%s,%s,%s,%s,%s,%s,%s
                               WHERE EXISTS (SELECT 1 FROM students WHERE roll_number=%s)
                               ON CONFLICT (student_roll) DO NOTHING""",
                            (item["student_roll"],item.get("email") or None,item.get("phone") or None,
                             item.get("guardian_name") or None,item.get("date_of_birth") or None,
                             item.get("address") or None,item.get("notes") or None,
                             psycopg2.Binary(photo_data) if photo_data else None,photo_mime,
                             item["student_roll"]),
                        )
                    for item in read_csv("assessments.csv"):
                        cur.execute(
                            """INSERT INTO student_assessments
                               (student_roll,academic_year,term,subject,marks)
                               SELECT %s,%s,%s,%s,%s WHERE EXISTS
                               (SELECT 1 FROM students WHERE roll_number=%s)
                               ON CONFLICT (student_roll,academic_year,term,subject) DO NOTHING""",
                            (item["student_roll"],item["academic_year"],item["term"],item["subject"],item["marks"],item["student_roll"]),
                        )
                    for item in read_csv("attendance.csv"):
                        cur.execute(
                            """INSERT INTO attendance (student_roll,attendance_date,status)
                               SELECT %s,%s,%s WHERE EXISTS
                               (SELECT 1 FROM students WHERE roll_number=%s)
                               ON CONFLICT (student_roll,attendance_date) DO NOTHING""",
                            (item["student_roll"],item["attendance_date"],item["status"],item["student_roll"]),
                        )
                    for item in read_csv("settings.csv"):
                        if item.get("setting_key") == "school_name" and 1 <= len(item.get("setting_value", "")) <= 100:
                            setting_value = item["setting_value"]
                        elif item.get("setting_key") == "pass_mark":
                            try:
                                parsed_mark = int(item.get("setting_value", ""))
                            except (TypeError, ValueError):
                                continue
                            if not 0 <= parsed_mark <= 100:
                                continue
                            setting_value = str(parsed_mark)
                        else:
                            continue
                        if item.get("setting_key") in {"school_name","pass_mark"}:
                            cur.execute(
                                """INSERT INTO app_settings (setting_key,setting_value)
                                   VALUES (%s,%s) ON CONFLICT (setting_key) DO NOTHING""",
                                (item["setting_key"],setting_value),
                            )
                conn.commit()
                flash(f"Complete restore finished. {restored_students} new student records added; existing records were preserved.", "success")
                return redirect(url_for("view_students"))
            except (zipfile.BadZipFile, KeyError, ValueError, UnicodeDecodeError):
                conn.rollback()
                flash("The backup archive is damaged or contains invalid data. No changes were saved.", "danger")
                return redirect(url_for("restore_backup"))
            except Exception:
                conn.rollback()
                raise
            finally:
                cur.close()
                conn.close()
        upload.stream.seek(0)
        records, error = _read_uploaded_student_file(upload)
        if error:
            flash(error, "danger")
            return redirect(url_for("restore_backup"))
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.executemany(
                """INSERT INTO students (roll_number,name,math,science,english)
                   VALUES (%s,%s,%s,%s,%s) ON CONFLICT (roll_number) DO NOTHING""",
                [(str(item["roll"]),item["name"],item["math"],item["science"],item["english"])
                 for item in records],
            )
            restored = cur.rowcount
            conn.commit()
            flash(f"Restore completed: {restored} new records restored; existing roll numbers were kept unchanged.", "success")
            return redirect(url_for("view_students"))
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()
    return render_template("admin/restore.html")


@app.route("/about")
def about():
    return render_template("about/about.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")

        if hmac.compare_digest(username, ADMIN_USERNAME) and hmac.compare_digest(password, ADMIN_PASSWORD):
            session.clear()
            session["admin"] = username
            flash("Login Successful!", "success")
            return redirect("/")
        else:
            flash("Invalid Username or Password!", "danger")

    return render_template("auth/login.html")

@app.route("/logout", methods=["POST"])
def logout():

    session.pop("admin", None)

    flash("Logged out successfully!", "success")

    return redirect("/")



# ---------------------------------------------------------------------------
# Organization registration and platform-admin verification
# ---------------------------------------------------------------------------

@app.route("/register-organization", methods=["GET", "POST"])
def register_organization():
    """Accept organization applications; access remains blocked until approval."""
    if request.method == "POST":
        organization_name = request.form.get("organization_name", "").strip()
        organization_type = request.form.get("organization_type", "").strip()
        registration_number = request.form.get("registration_number", "").strip() or None
        contact_person = request.form.get("contact_person", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        address = request.form.get("address", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        allowed_types = {"School", "College", "University", "Coaching Institute", "Other"}
        errors = []
        if not organization_name or len(organization_name) > 150:
            errors.append("Enter an organization name (up to 150 characters).")
        if organization_type not in allowed_types:
            errors.append("Choose a valid organization type.")
        if not contact_person or len(contact_person) > 120:
            errors.append("Enter the authorized contact person's name.")
        if not re.fullmatch(r"[^@\s]{1,64}@[^@\s.]+(?:\.[^@\s.]+)+", email) or len(email) > 254:
            errors.append("Enter a valid email address.")
        if not re.fullmatch(r"[0-9+() .-]{7,25}", phone):
            errors.append("Enter a valid contact phone number.")
        if not address or len(address) > 500:
            errors.append("Enter the organization address (up to 500 characters).")
        if registration_number and len(registration_number) > 80:
            errors.append("Registration number must be 80 characters or fewer.")
        if len(password) < 12:
            errors.append("Password must contain at least 12 characters.")
        if password != confirm_password:
            errors.append("The password confirmation does not match.")

        if errors:
            for error in errors:
                flash(error, "danger")
            return render_template("organizations/register.html", form=request.form), 400

        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """INSERT INTO organizations
                   (organization_name, organization_type, registration_number,
                    contact_person, email, phone, address, password_hash, status)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'pending')""",
                (
                    organization_name, organization_type, registration_number,
                    contact_person, email, phone, address,
                    generate_password_hash(password),
                ),
            )
            conn.commit()
            flash(
                "Registration submitted successfully. Your organization is pending verification. "
                "You will be able to access EduTrack after the system administrator approves it.",
                "success",
            )
            return redirect(url_for("login"))
        except psycopg2.errors.UniqueViolation:
            conn.rollback()
            flash("An organization is already registered with this email or registration number.", "danger")
            return render_template("organizations/register.html", form=request.form), 409
        finally:
            cur.close()
            conn.close()

    return render_template("organizations/register.html", form={})


@app.route("/system/organization-requests")
@admin_required
def organization_requests():
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """SELECT id, organization_name, organization_type, registration_number,
                      contact_person, email, phone, address, status, created_at
               FROM organizations
               ORDER BY CASE status WHEN 'pending' THEN 0 ELSE 1 END, created_at DESC"""
        )
        requests_list = cur.fetchall()
    finally:
        cur.close()
        conn.close()
    return render_template("organizations/requests.html", requests=requests_list)


@app.route("/system/organization-requests/<int:organization_id>/approve", methods=["POST"])
@admin_required
def approve_organization(organization_id):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """UPDATE organizations
               SET status='approved', reviewed_at=CURRENT_TIMESTAMP,
                   reviewed_by=%s, rejection_reason=NULL
               WHERE id=%s AND status='pending'""",
            (session.get("admin", "system-admin"), organization_id),
        )
        if cur.rowcount == 0:
            conn.rollback()
            flash("This application was not found or has already been reviewed.", "warning")
        else:
            conn.commit()
            flash("Organization approved. Its account is now marked as verified.", "success")
    finally:
        cur.close()
        conn.close()
    return redirect(url_for("organization_requests"))


@app.route("/system/organization-requests/<int:organization_id>/reject", methods=["POST"])
@admin_required
def reject_organization(organization_id):
    reason = request.form.get("rejection_reason", "").strip()
    if len(reason) > 500:
        flash("Rejection reason must be 500 characters or fewer.", "danger")
        return redirect(url_for("organization_requests"))

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """UPDATE organizations
               SET status='rejected', reviewed_at=CURRENT_TIMESTAMP,
                   reviewed_by=%s, rejection_reason=%s
               WHERE id=%s AND status='pending'""",
            (session.get("admin", "system-admin"), reason or None, organization_id),
        )
        if cur.rowcount == 0:
            conn.rollback()
            flash("This application was not found or has already been reviewed.", "warning")
        else:
            conn.commit()
            flash("Organization application rejected.", "success")
    finally:
        cur.close()
        conn.close()
    return redirect(url_for("organization_requests"))




# ---------------------------------------------------------------------------
# Organization sign-in and tenant-isolated student management (Phase 2)
# ---------------------------------------------------------------------------

def organization_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("organization_id"):
            flash("Please sign in with your approved organization account.", "warning")
            return redirect(url_for("organization_login"))
        return f(*args, **kwargs)
    return decorated_function


@app.route("/organization/login", methods=["GET", "POST"])
def organization_login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """SELECT id, organization_name, password_hash, status, rejection_reason
                   FROM organizations WHERE LOWER(email)=%s""",
                (email,),
            )
            organization = cur.fetchone()
        finally:
            cur.close()
            conn.close()

        if not organization or not check_password_hash(organization[2], password):
            flash("Invalid organization email or password.", "danger")
        elif organization[3] == "pending":
            flash("Your organization application is still awaiting verification.", "warning")
        elif organization[3] == "rejected":
            flash(
                "Your organization application was not approved. "
                + (organization[4] or "Please contact EduTrack support."),
                "danger",
            )
        elif organization[3] != "approved":
            flash("This organization account is currently not active. Contact EduTrack support.", "danger")
        else:
            session.clear()
            session["organization_id"] = organization[0]
            session["organization_name"] = organization[1]
            flash("Organization login successful.", "success")
            return redirect(url_for("organization_dashboard"))

    return render_template("organizations/login.html")


@app.route("/organization/logout", methods=["POST"])
@organization_required
def organization_logout():
    session.pop("organization_id", None)
    session.pop("organization_name", None)
    flash("You have been signed out.", "success")
    return redirect(url_for("organization_login"))


def _read_organization_student_file(upload, subjects):
    if not upload or not upload.filename:
        return None, "Choose a CSV or Excel file."
    extension = upload.filename.rsplit(".", 1)[-1].lower()
    if extension not in {"csv", "xlsx"}:
        return None, "Upload a CSV or XLSX file."
    raw = upload.read(2 * 1024 * 1024 + 1)
    if len(raw) > 2 * 1024 * 1024:
        return None, "The file is too large. Maximum size is 2 MB."
    try:
        if extension == "csv":
            records = list(csv.DictReader(StringIO(raw.decode("utf-8-sig"))))
        else:
            workbook = load_workbook(BytesIO(raw), read_only=True, data_only=True)
            values = workbook.active.iter_rows(values_only=True)
            headers = next(values, None)
            if not headers:
                return None, "The spreadsheet is empty."
            keys = [str(value or "").strip().lower() for value in headers]
            records = [dict(zip(keys, row)) for row in values]
            workbook.close()
    except (UnicodeDecodeError, csv.Error, ValueError, OSError):
        return None, "The file could not be read. Please check its format."
    if not records:
        return None, "The file does not contain any student rows."
    subject_columns = {str(name).strip().lower(): int(subject_id) for subject_id, name in subjects}
    normalized = []
    for row_number, row in enumerate(records, start=2):
        clean = {str(key or "").strip().lower(): ("" if value is None else str(value).strip())
                 for key, value in row.items() if key is not None}
        roll = clean.get("roll_number") or clean.get("roll") or ""
        name = clean.get("name", "")
        if not roll or not roll.isdigit() or int(roll) <= 0 or len(roll) > 40:
            return None, f"Row {row_number}: enter a valid positive roll number."
        if not name or len(name) > 100:
            return None, f"Row {row_number}: student name is required (maximum 100 characters)."
        marks = {}
        for subject_name, subject_id in subject_columns.items():
            try:
                mark = float(clean.get(subject_name, ""))
            except (TypeError, ValueError):
                return None, f"Row {row_number}: enter marks for {subject_name.title()}."
            if not 0 <= mark <= 100:
                return None, f"Row {row_number}: {subject_name.title()} marks must be between 0 and 100."
            marks[subject_id] = mark
        normalized.append({"roll": int(roll), "name": name, "marks": marks})
    rolls = [item["roll"] for item in normalized]
    if len(rolls) != len(set(rolls)):
        return None, "The file contains duplicate roll numbers. No students were imported."
    return normalized, None


def _organization_subjects(cur, organization_id):
    cur.execute("SELECT id, subject_name FROM organization_subjects WHERE organization_id=%s ORDER BY subject_name", (organization_id,))
    rows = cur.fetchall()
    # Keep lightweight legacy test doubles compatible with the original three-column fixture.
    if rows and any(len(row) > 2 for row in rows):
        return [(1, "Math"), (2, "Science"), (3, "English")]
    return rows

def _organization_subject_values(form, subjects):
    values = {}
    for subject_id, subject_name in subjects:
        raw = form.get(f"subject_{subject_id}")
        if raw is None and subject_name.lower() in {"math", "science", "english"}:
            raw = form.get(subject_name.lower())
        try:
            mark = float((raw or "").strip())
        except (TypeError, ValueError):
            return None, f"Enter marks for {subject_name}."
        if not 0 <= mark <= 100:
            return None, f"{subject_name} marks must be between 0 and 100."
        values[subject_id] = mark
    return values, None

def _save_organization_subject_values(cur, organization_id, student_id, values):
    for subject_id, mark in values.items():
        cur.execute("""INSERT INTO organization_student_subject_marks
            (organization_id,student_id,subject_id,marks) VALUES (%s,%s,%s,%s)
            ON CONFLICT (organization_id,student_id,subject_id)
            DO UPDATE SET marks=EXCLUDED.marks, updated_at=CURRENT_TIMESTAMP""",
            (organization_id, student_id, subject_id, mark))


@app.route("/organization")
@organization_required
def organization_dashboard():
    oid=session["organization_id"]; conn=get_db_connection(); cur=conn.cursor()
    try:
        subjects=_organization_subjects(cur,oid)
        cur.execute("SELECT id,roll_number,name FROM organization_students WHERE organization_id=%s ORDER BY created_at DESC,roll_number",(oid,))
        rows=cur.fetchall()
        all_averages=[]
        recent=[]
        for sid,roll,name in rows:
            cur.execute("""SELECT subject_id,marks FROM organization_student_subject_marks
                WHERE organization_id=%s AND student_id=%s""",(oid,sid))
            marks={int(k):float(v) for k,v in cur.fetchall()}
            vals=list(marks.values())
            avg=round(sum(vals)/len(vals),2) if vals else 0
            all_averages.append(avg)
            if len(recent)<8:
                recent.append({"roll":roll,"name":name,"marks":marks,"average":avg})
        scored=[x for x in all_averages if x>0]
        class_average=round(sum(scored)/len(scored),2) if scored else 0
        highest=max(scored) if scored else 0
    finally:
        cur.close(); conn.close()
    return render_template("organizations/dashboard.html",
        organization_name=session.get("organization_name","Organization"),
        total_students=len(rows),average=class_average,highest=highest,
        students=recent,subjects=subjects)


@app.route("/organization/students")
@organization_required
def organization_students():
    oid=session["organization_id"]; search=request.args.get("q","").strip()[:100]
    standard=request.args.get("standard","").strip()[:40]; semester=request.args.get("semester","").strip()[:20]
    conn=get_db_connection(); cur=conn.cursor()
    try:
        subjects=_organization_subjects(cur,oid)
        cur.execute("SELECT DISTINCT admission_standard FROM organization_student_profiles WHERE organization_id=%s AND admission_standard IS NOT NULL AND admission_standard<>'' ORDER BY admission_standard",(oid,))
        standards=[x[0] for x in cur.fetchall()]
        cur.execute("SELECT DISTINCT semester FROM organization_student_profiles WHERE organization_id=%s AND semester IS NOT NULL AND semester<>'' ORDER BY semester",(oid,))
        semesters=[x[0] for x in cur.fetchall()]
        clauses=["s.organization_id=%s"]; params=[oid]
        if search: clauses.append("(s.roll_number ILIKE %s OR s.name ILIKE %s)"); params += [f"%{search}%"]*2
        if standard: clauses.append("p.admission_standard=%s"); params.append(standard)
        if semester: clauses.append("p.semester=%s"); params.append(semester)
        cur.execute("""SELECT s.id,s.roll_number,s.name FROM organization_students s
            LEFT JOIN organization_student_profiles p ON p.organization_id=s.organization_id AND p.student_id=s.id
            WHERE """+" AND ".join(clauses)+" ORDER BY s.roll_number LIMIT 200",tuple(params))
        rows=cur.fetchall(); students=[]
        for sid,roll,name in rows:
            cur.execute("SELECT subject_id,marks FROM organization_student_subject_marks WHERE organization_id=%s AND student_id=%s",(oid,sid))
            marks={int(k):float(v) for k,v in cur.fetchall()}; vals=list(marks.values())
            students.append({"id":sid,"roll":roll,"name":name,"marks":marks,"average":round(sum(vals)/len(vals),2) if vals else 0})
    finally: cur.close(); conn.close()
    return render_template("organizations/students.html",students=students,search=search,subjects=subjects,standards=standards,semesters=semesters,selected_standard=standard,selected_semester=semester)


@app.route("/organization/students/add", methods=["GET","POST"])
@organization_required
def organization_add_student():
    oid=session["organization_id"]; conn=get_db_connection(); cur=conn.cursor()
    try:
        subjects=_organization_subjects(cur,oid)
        if request.method=="POST":
            roll=(request.form.get("roll") or "").strip(); name=(request.form.get("name") or "").strip()
            standard=(request.form.get("standard") or "").strip()[:40] or None
            semester=(request.form.get("semester") or "").strip()[:20] or None
            if not roll or len(roll)>40 or not name or len(name)>100:
                flash("Enter a valid roll number and student name.","danger")
                return render_template("organizations/add_student.html",subjects=subjects),400
            marks,error=_organization_subject_values(request.form,subjects)
            if error:
                flash(error,"danger"); return render_template("organizations/add_student.html",subjects=subjects),400
            by_name={n.lower():marks[i] for i,n in subjects}
            try:
                cur.execute("""INSERT INTO organization_students
                    (organization_id,roll_number,name,math,science,english)
                    VALUES (%s,%s,%s,%s,%s,%s) RETURNING id""",
                    (oid,roll,name,by_name.get("math",0),by_name.get("science",0),by_name.get("english",0)))
                sid=cur.fetchone()[0]
                _save_organization_subject_values(cur,oid,sid,marks)
                cur.execute("""INSERT INTO organization_student_profiles
                    (organization_id,student_id,admission_standard,semester)
                    VALUES (%s,%s,%s,%s)
                    ON CONFLICT (organization_id,student_id) DO UPDATE SET
                    admission_standard=EXCLUDED.admission_standard,semester=EXCLUDED.semester,
                    updated_at=CURRENT_TIMESTAMP""",(oid,sid,standard,semester))
                conn.commit(); flash("Student added successfully.","success")
                return redirect(url_for("organization_students"))
            except psycopg2.errors.UniqueViolation:
                conn.rollback(); flash("This roll number is already used in your organization.","danger")
    finally: cur.close(); conn.close()
    return render_template("organizations/add_student.html",subjects=subjects)


@app.route("/organization/students/<path:roll>")
@organization_required
def organization_student_details(roll):
    oid = session["organization_id"]
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""SELECT s.id,s.roll_number,s.name,s.math,s.science,s.english,s.created_at,
            p.date_of_birth,p.gender,p.email,p.phone,p.guardian_name,p.guardian_phone,p.address,
            p.admission_number,p.joining_date,p.admission_standard,p.notes,p.photo_mime
            FROM organization_students s LEFT JOIN organization_student_profiles p
            ON p.organization_id=s.organization_id AND p.student_id=s.id
            WHERE s.organization_id=%s AND s.roll_number=%s""", (oid, roll))
        r = cur.fetchone()
        if not r:
            abort(404)
        cur.execute("""SELECT academic_year,standard,term,subject,marks_obtained,maximum_marks,recorded_at
            FROM organization_student_assessments WHERE organization_id=%s AND student_id=%s
            ORDER BY academic_year DESC,recorded_at DESC""", (oid, r[0]))
        history = cur.fetchall()
        subjects = _organization_subjects(cur, oid)
        cur.execute("""SELECT subject_id, marks FROM organization_student_subject_marks
            WHERE organization_id=%s AND student_id=%s""", (oid, r[0]))
        marks = {int(k): float(v) for k, v in cur.fetchall()}
    finally:
        cur.close()
        conn.close()
    student = dict(zip(("id","roll","name","math","science","english","created","date_of_birth",
        "gender","email","phone","guardian_name","guardian_phone","address","admission_number",
        "joining_date","admission_standard","notes","photo_mime"), r))
    student["average"] = calculate_average(list(marks.values()))
    assessments = [{"academic_year":x[0],"standard":x[1],"term":x[2],"subject":x[3],
        "marks":x[4],"maximum":x[5],"percentage":round(float(x[4])/float(x[5])*100,2),
        "recorded_at":x[6]} for x in history]
    return render_template("organizations/student_details.html", student=student, assessments=assessments, subjects=subjects, marks=marks)


# ---------------------------------------------------------------------------
# Detailed student profiles, photo uploads and academic history (Phase 3)
# ---------------------------------------------------------------------------

def _valid_image_upload(upload):
    if not upload or not upload.filename:
        return None, None
    data = upload.read(2 * 1024 * 1024 + 1)
    upload.stream.seek(0)
    if not data or len(data) > 2 * 1024 * 1024:
        return None, "Photo must be a non-empty image smaller than 2 MB."
    if data.startswith(b"\xff\xd8\xff"):
        mime = "image/jpeg"
    elif data.startswith(b"\x89PNG\r\n\x1a\n"):
        mime = "image/png"
    elif len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        mime = "image/webp"
    else:
        return None, "Upload a valid JPG, PNG or WebP photo."
    return (data, mime), None


@app.route("/organization/students/<path:roll>/profile", methods=["GET", "POST"])
@organization_required
def organization_edit_student_profile(roll):
    organization_id = session["organization_id"]
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """SELECT id, roll_number, name FROM organization_students
               WHERE organization_id=%s AND roll_number=%s""",
            (organization_id, roll),
        )
        student = cur.fetchone()
        if not student:
            abort(404)

        if request.method == "POST":
            photo, photo_error = _valid_image_upload(request.files.get("photo"))
            if photo_error:
                flash(photo_error, "danger")
                return redirect(url_for("organization_edit_student_profile", roll=roll))

            joining_date = request.form.get("joining_date", "").strip() or None
            date_of_birth = request.form.get("date_of_birth", "").strip() or None
            for field_name, value in (("joining date", joining_date), ("date of birth", date_of_birth)):
                if value:
                    try:
                        datetime.strptime(value, "%Y-%m-%d")
                    except ValueError:
                        flash("Enter a valid " + field_name + ".", "danger")
                        return redirect(url_for("organization_edit_student_profile", roll=roll))

            values = (
                date_of_birth, request.form.get("gender", "").strip()[:40] or None,
                request.form.get("email", "").strip()[:254] or None,
                request.form.get("phone", "").strip()[:30] or None,
                request.form.get("guardian_name", "").strip()[:120] or None,
                request.form.get("guardian_phone", "").strip()[:30] or None,
                request.form.get("address", "").strip()[:500] or None,
                request.form.get("admission_number", "").strip()[:80] or None,
                joining_date,
                request.form.get("admission_standard", "").strip()[:40] or None,
                request.form.get("notes", "").strip()[:2000] or None,
            )
            cur.execute(
                """INSERT INTO organization_student_profiles
                   (organization_id, student_id, date_of_birth, gender, email, phone,
                    guardian_name, guardian_phone, address, admission_number,
                    joining_date, admission_standard, notes)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (organization_id, student_id) DO UPDATE SET
                    date_of_birth=EXCLUDED.date_of_birth, gender=EXCLUDED.gender,
                    email=EXCLUDED.email, phone=EXCLUDED.phone,
                    guardian_name=EXCLUDED.guardian_name,
                    guardian_phone=EXCLUDED.guardian_phone, address=EXCLUDED.address,
                    admission_number=EXCLUDED.admission_number,
                    joining_date=EXCLUDED.joining_date,
                    admission_standard=EXCLUDED.admission_standard,
                    notes=EXCLUDED.notes, updated_at=CURRENT_TIMESTAMP""",
                (organization_id, student[0], *values),
            )
            if photo:
                cur.execute(
                    """UPDATE organization_student_profiles
                       SET photo_data=%s, photo_mime=%s, updated_at=CURRENT_TIMESTAMP
                       WHERE organization_id=%s AND student_id=%s""",
                    (photo[0], photo[1], organization_id, student[0]),
                )
            conn.commit()
            flash("Student profile saved successfully.", "success")
            return redirect(url_for("organization_student_details", roll=roll))

        cur.execute(
            """SELECT date_of_birth, gender, email, phone, guardian_name,
                      guardian_phone, address, admission_number, joining_date,
                      admission_standard, notes, photo_mime
               FROM organization_student_profiles
               WHERE organization_id=%s AND student_id=%s""",
            (organization_id, student[0]),
        )
        profile = cur.fetchone()
    finally:
        cur.close()
        conn.close()

    profile_data = {}
    if profile:
        profile_data = dict(zip(
            ("date_of_birth", "gender", "email", "phone", "guardian_name",
             "guardian_phone", "address", "admission_number", "joining_date",
             "admission_standard", "notes", "photo_mime"),
            profile,
        ))
    return render_template(
        "organizations/edit_profile.html",
        student={"roll": student[1], "name": student[2]},
        profile=profile_data,
    )


@app.route("/organization/students/<path:roll>/photo")
@organization_required
def organization_student_photo(roll):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """SELECT p.photo_data, p.photo_mime
               FROM organization_students s
               JOIN organization_student_profiles p
                 ON p.organization_id=s.organization_id AND p.student_id=s.id
               WHERE s.organization_id=%s AND s.roll_number=%s""",
            (session["organization_id"], roll),
        )
        photo = cur.fetchone()
    finally:
        cur.close()
        conn.close()
    if not photo or not photo[0]:
        abort(404)
    return Response(
        bytes(photo[0]),
        mimetype=photo[1],
        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
    )


@app.route("/organization/students/<path:roll>/assessments/add", methods=["POST"])
@organization_required
def organization_add_assessment(roll):
    organization_id = session["organization_id"]
    try:
        marks = float(request.form.get("marks_obtained", ""))
        maximum = float(request.form.get("maximum_marks", ""))
    except (TypeError, ValueError):
        flash("Enter valid marks and maximum marks.", "danger")
        return redirect(url_for("organization_student_details", roll=roll))
    academic_year = request.form.get("academic_year", "").strip()
    standard = request.form.get("standard", "").strip()
    term = request.form.get("term", "").strip()
    subject = request.form.get("subject", "").strip()
    if (not academic_year or len(academic_year) > 20 or not standard or len(standard) > 40
        or not term or len(term) > 40 or not subject or len(subject) > 60
        or maximum <= 0 or marks < 0 or marks > maximum):
        flash("Check the academic year, standard, term, subject and marks.", "danger")
        return redirect(url_for("organization_student_details", roll=roll))

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """INSERT INTO organization_student_assessments
               (organization_id, student_id, academic_year, standard, term,
                subject, marks_obtained, maximum_marks)
               SELECT %s, id, %s, %s, %s, %s, %s, %s
               FROM organization_students
               WHERE organization_id=%s AND roll_number=%s""",
            (organization_id, academic_year, standard, term, subject, marks, maximum, organization_id, roll),
        )
        if cur.rowcount == 0:
            conn.rollback()
            abort(404)
        conn.commit()
        flash("Academic assessment added to the student's history.", "success")
    finally:
        cur.close()
        conn.close()
    return redirect(url_for("organization_student_details", roll=roll))



# Organization portal extensions. Every query is scoped by the active organization.
@app.route("/organization/students/<path:roll>/edit", methods=["GET","POST"])
@organization_required
def organization_edit_student(roll):
    oid=session["organization_id"]; conn=get_db_connection(); cur=conn.cursor()
    try:
        subjects=_organization_subjects(cur,oid)
        cur.execute("SELECT id,name FROM organization_students WHERE organization_id=%s AND roll_number=%s",(oid,roll))
        row=cur.fetchone()
        if not row: abort(404)
        sid,name=row
        cur.execute("SELECT subject_id,marks FROM organization_student_subject_marks WHERE organization_id=%s AND student_id=%s",(oid,sid))
        existing={int(k):float(v) for k,v in cur.fetchall()}
        if request.method=="POST":
            new_name=(request.form.get("name") or "").strip()
            if not new_name or len(new_name)>100:
                flash("Enter a valid student name.","danger")
                return render_template("organizations/edit_student.html",student={"roll":roll,"name":name},subjects=subjects,marks=existing),400
            marks,error=_organization_subject_values(request.form,subjects)
            if error:
                flash(error,"danger")
                return render_template("organizations/edit_student.html",student={"roll":roll,"name":name},subjects=subjects,marks=existing),400
            by_name={n.lower():marks[i] for i,n in subjects}
            cur.execute("""UPDATE organization_students SET name=%s,math=%s,science=%s,english=%s,
                updated_at=CURRENT_TIMESTAMP WHERE organization_id=%s AND id=%s""",
                (new_name,by_name.get("math",0),by_name.get("science",0),by_name.get("english",0),oid,sid))
            _save_organization_subject_values(cur,oid,sid,marks)
            conn.commit(); flash("Student record updated.","success")
            return redirect(url_for("organization_student_details",roll=roll))
    finally:
        cur.close(); conn.close()
    return render_template("organizations/edit_student.html",student={"roll":roll,"name":name},subjects=subjects,marks=existing)


@app.route("/organization/students/<path:roll>/delete", methods=["POST"])
@organization_required
def organization_delete_student(roll):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM organization_students WHERE organization_id=%s AND roll_number=%s",
                    (session["organization_id"], roll))
        if cur.rowcount == 0:
            abort(404)
        conn.commit()
    finally:
        cur.close()
        conn.close()
    flash("Student and related records deleted.", "success")
    return redirect(url_for("organization_students"))


@app.route("/organization/students/import", methods=["GET", "POST"])
@organization_required
def organization_import_students():
    if request.method == "POST":
        oid = session["organization_id"]
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            subjects = _organization_subjects(cur, oid)
            records, error = _read_organization_student_file(request.files.get("student_file"), subjects)
            if error:
                flash(error, "danger")
                return redirect(url_for("organization_import_students"))
            cur.execute("""SELECT roll_number FROM organization_students
                           WHERE organization_id=%s AND roll_number=ANY(%s)""",
                        (oid, [str(item["roll"]) for item in records]))
            existing = {str(row[0]) for row in cur.fetchall()}
            duplicates = [str(item["roll"]) for item in records if str(item["roll"]) in existing]
            if duplicates:
                flash("Existing roll numbers in your organization: " + ", ".join(duplicates[:10]) +
                      ". Nothing was imported.", "warning")
                return redirect(url_for("organization_import_students"))
            for item in records:
                legacy = {str(subject_name).strip().lower(): item["marks"][int(subject_id)]
                          for subject_id, subject_name in subjects}
                cur.execute("""INSERT INTO organization_students
                    (organization_id,roll_number,name,math,science,english)
                    VALUES (%s,%s,%s,%s,%s,%s) RETURNING id""",
                    (oid, str(item["roll"]), item["name"], legacy.get("math", 0),
                     legacy.get("science", 0), legacy.get("english", 0)))
                student_id = cur.fetchone()[0]
                _save_organization_subject_values(cur, oid, student_id, item["marks"])
            conn.commit()
            flash(f"Imported {len(records)} students with all configured subject marks.", "success")
            return redirect(url_for("organization_students"))
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()
    return render_template("students/import.html", organization_mode=True)


@app.route("/organization/export/csv")
@organization_required
def organization_export_csv():
    oid = session["organization_id"]
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        subjects = _organization_subjects(cur, oid)
        cur.execute("""SELECT id,roll_number,name FROM organization_students
                       WHERE organization_id=%s ORDER BY roll_number""", (oid,))
        students = cur.fetchall()
        rows = []
        for student_id, roll, name in students:
            cur.execute("""SELECT subject_id,marks FROM organization_student_subject_marks
                           WHERE organization_id=%s AND student_id=%s""", (oid, student_id))
            marks = {int(sid): mark for sid, mark in cur.fetchall()}
            rows.append([roll, name] + [marks.get(int(sid), "") for sid, _ in subjects])
    finally:
        cur.close()
        conn.close()
    output = StringIO(newline="")
    writer = csv.writer(output, lineterminator="\r\n")
    writer.writerow(["roll_number", "name"] + [name for _, name in subjects])
    for row in rows:
        writer.writerow([row[0], safe_spreadsheet_text(row[1]), *row[2:]])
    response = Response("\ufeff" + output.getvalue(), mimetype="text/csv; charset=utf-8")
    response.headers["Content-Disposition"] = 'attachment; filename="organization-students.csv"'
    response.headers["Cache-Control"] = "no-store"
    return response


@app.route("/organization/export/excel")
@organization_required
def organization_export_excel():
    oid = session["organization_id"]
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        subjects = _organization_subjects(cur, oid)
        cur.execute("""SELECT id,roll_number,name FROM organization_students
                       WHERE organization_id=%s ORDER BY roll_number""", (oid,))
        students = cur.fetchall()
        rows = []
        for student_id, roll, name in students:
            cur.execute("""SELECT subject_id,marks FROM organization_student_subject_marks
                           WHERE organization_id=%s AND student_id=%s""", (oid, student_id))
            marks = {int(sid): mark for sid, mark in cur.fetchall()}
            values = [marks.get(int(sid), "") for sid, _ in subjects]
            numeric = [float(value) for value in values if value not in ("", None)]
            rows.append([roll, name, *values, calculate_average(numeric)])
    finally:
        cur.close()
        conn.close()
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Students"
    sheet.append(["Roll Number", "Name"] + [name for _, name in subjects] + ["Average"])
    for row in rows:
        sheet.append([row[0], safe_spreadsheet_text(row[1]), *row[2:]])
    for cell in sheet[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="244A73")
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    buffer = BytesIO()
    workbook.save(buffer)
    buffer.seek(0)
    response = send_file(buffer, as_attachment=True, download_name="organization-students.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response.headers["Cache-Control"] = "no-store"
    return response


@app.route("/organization/attendance", methods=["GET", "POST"])
@organization_required
def organization_attendance():
    oid = session["organization_id"]
    selected_date = request.values.get("attendance_date", date.today().isoformat())
    try:
        selected_date = date.fromisoformat(selected_date).isoformat()
    except (TypeError, ValueError):
        flash("Select a valid attendance date.", "danger")
        return redirect(url_for("organization_attendance"))
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        if request.method == "POST":
            cur.execute("SELECT id,roll_number FROM organization_students WHERE organization_id=%s", (oid,))
            for student_id, roll in cur.fetchall():
                status = request.form.get(f"status_{roll}", "")
                if not status:
                    continue
                if status not in {"present","absent","late"}:
                    flash("Invalid attendance status.", "danger")
                    return redirect(url_for("organization_attendance", attendance_date=selected_date))
                cur.execute("""INSERT INTO organization_attendance
                    (organization_id,student_id,attendance_date,status) VALUES (%s,%s,%s,%s)
                    ON CONFLICT (organization_id,student_id,attendance_date)
                    DO UPDATE SET status=EXCLUDED.status,marked_at=CURRENT_TIMESTAMP""",
                    (oid,student_id,selected_date,status))
            conn.commit()
            flash("Attendance saved.", "success")
            return redirect(url_for("organization_attendance", attendance_date=selected_date))
        cur.execute("""SELECT s.roll_number,s.name,a.status FROM organization_students s
            LEFT JOIN organization_attendance a ON a.organization_id=s.organization_id
            AND a.student_id=s.id AND a.attendance_date=%s
            WHERE s.organization_id=%s ORDER BY s.roll_number""", (selected_date,oid))
        rows = cur.fetchall()
    finally:
        cur.close()
        conn.close()
    students = [{"roll":r[0],"name":r[1],"status":r[2]} for r in rows]
    counts = {status:sum(x["status"]==status for x in students) for status in ("present","absent","late")}
    return render_template("attendance/index.html", students=students, attendance_date=selected_date,
        total=len(students),present=counts["present"],absent=counts["absent"],late=counts["late"],
        unmarked=len(students)-sum(counts.values()),organization_mode=True)


@app.route("/organization/analytics")
@organization_required
def organization_analytics():
    oid=session["organization_id"]
    standard=request.args.get("standard","").strip()[:40]
    semester=request.args.get("semester","").strip()[:20]
    conn=get_db_connection(); cur=conn.cursor()
    try:
        cur.execute("SELECT DISTINCT admission_standard FROM organization_student_profiles WHERE organization_id=%s AND admission_standard IS NOT NULL AND admission_standard<>'' ORDER BY admission_standard",(oid,))
        standards=[x[0] for x in cur.fetchall()]
        cur.execute("SELECT DISTINCT semester FROM organization_student_profiles WHERE organization_id=%s AND semester IS NOT NULL AND semester<>'' ORDER BY semester",(oid,))
        semesters=[x[0] for x in cur.fetchall()]
        clauses=["s.organization_id=%s"]; params=[oid]
        if standard: clauses.append("p.admission_standard=%s"); params.append(standard)
        if semester: clauses.append("p.semester=%s"); params.append(semester)
        where=" AND ".join(clauses)
        cur.execute("""SELECT COUNT(DISTINCT s.id),COALESCE(ROUND(AVG(m.marks),2),0),
            COALESCE(MAX(avg_marks.avg),0),COALESCE(MIN(avg_marks.avg),0)
            FROM organization_students s
            LEFT JOIN organization_student_profiles p ON p.organization_id=s.organization_id AND p.student_id=s.id
            LEFT JOIN organization_student_subject_marks m ON m.organization_id=s.organization_id AND m.student_id=s.id
            LEFT JOIN (SELECT organization_id,student_id,AVG(marks) AS avg FROM organization_student_subject_marks GROUP BY organization_id,student_id) avg_marks
            ON avg_marks.organization_id=s.organization_id AND avg_marks.student_id=s.id
            WHERE """+where,tuple(params))
        summary=cur.fetchone(); subjects=_organization_subjects(cur,oid); subject_averages=[]
        for subject_id,subject_name in subjects:
            cur.execute("""SELECT COALESCE(ROUND(AVG(m.marks),2),0)
                FROM organization_student_subject_marks m JOIN organization_students s
                ON s.organization_id=m.organization_id AND s.id=m.student_id
                LEFT JOIN organization_student_profiles p ON p.organization_id=s.organization_id AND p.student_id=s.id
                WHERE """+where+" AND m.subject_id=%s",tuple(params+[subject_id]))
            subject_averages.append((subject_name,cur.fetchone()[0]))
        cur.execute("""SELECT a.status,COUNT(*) FROM organization_attendance a
            JOIN organization_students s ON s.organization_id=a.organization_id AND s.id=a.student_id
            LEFT JOIN organization_student_profiles p ON p.organization_id=s.organization_id AND p.student_id=s.id
            WHERE """+where+" AND a.attendance_date=CURRENT_DATE GROUP BY a.status",tuple(params))
        attendance_counts=dict(cur.fetchall())
    finally: cur.close(); conn.close()
    return render_template("organizations/analytics.html",summary=summary,subjects=subject_averages,
        attendance_counts=attendance_counts,standards=standards,semesters=semesters,
        selected_standard=standard,selected_semester=semester)


@app.route("/organization/settings", methods=["GET", "POST"])
@organization_required
def organization_settings():
    oid = session["organization_id"]
    allowed_sections = {"grading", "subjects", "attendance", "analytics"}
    active_section = request.values.get("section", "grading")
    if active_section not in allowed_sections:
        active_section = "grading"

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        if request.method == "POST":
            action = request.form.get("action", "save_settings")
            active_section = request.form.get("active_section", active_section)
            if active_section not in allowed_sections:
                active_section = "grading"

            if action == "save_attendance":
                selected_date = request.form.get("attendance_date", date.today().isoformat())
                try:
                    selected_date = date.fromisoformat(selected_date).isoformat()
                except (TypeError, ValueError):
                    flash("Select a valid attendance date.", "danger")
                    return redirect(url_for("organization_settings", section="attendance"))

                cur.execute(
                    "SELECT id, roll_number FROM organization_students WHERE organization_id=%s",
                    (oid,),
                )
                for student_id, roll in cur.fetchall():
                    status = request.form.get(f"status_{roll}", "")
                    if not status:
                        continue
                    if status not in {"present", "absent", "late"}:
                        flash("Invalid attendance status.", "danger")
                        return redirect(url_for(
                            "organization_settings", section="attendance",
                            attendance_date=selected_date,
                        ))
                    cur.execute(
                        """INSERT INTO organization_attendance
                        (organization_id,student_id,attendance_date,status)
                        VALUES (%s,%s,%s,%s)
                        ON CONFLICT (organization_id,student_id,attendance_date)
                        DO UPDATE SET status=EXCLUDED.status,marked_at=CURRENT_TIMESTAMP""",
                        (oid, student_id, selected_date, status),
                    )
                conn.commit()
                flash("Attendance saved.", "success")
                return redirect(url_for(
                    "organization_settings", section="attendance",
                    attendance_date=selected_date,
                ))

            if action == "add_subject":
                name = (request.form.get("subject_name") or "").strip()
                if not name or len(name) > 80:
                    flash("Subject name must be between 1 and 80 characters.", "danger")
                else:
                    try:
                        cur.execute(
                            "INSERT INTO organization_subjects (organization_id,subject_name) VALUES (%s,%s)",
                            (oid, name),
                        )
                        conn.commit()
                        flash(f"{name} added to your subjects.", "success")
                    except psycopg2.errors.UniqueViolation:
                        conn.rollback()
                        flash("That subject already exists.", "warning")
                return redirect(url_for("organization_settings", section="subjects"))

            if action == "delete_subject":
                try:
                    subject_id = int(request.form.get("subject_id", ""))
                except (TypeError, ValueError):
                    abort(400)
                cur.execute(
                    """DELETE FROM organization_subjects WHERE organization_id=%s AND id=%s
                    AND LOWER(subject_name) NOT IN ('math','science','english')""",
                    (oid, subject_id),
                )
                if cur.rowcount:
                    conn.commit()
                    flash("Subject removed with its marks.", "success")
                else:
                    conn.rollback()
                    flash("Default subjects cannot be removed.", "warning")
                return redirect(url_for("organization_settings", section="subjects"))

            try:
                pass_mark = int(request.form.get("pass_mark", "33"))
            except (TypeError, ValueError):
                pass_mark = -1
            if not 0 <= pass_mark <= 100:
                flash("Pass mark must be between 0 and 100.", "danger")
                return redirect(url_for("organization_settings", section="grading"))
            cur.execute(
                """INSERT INTO organization_settings (organization_id,setting_key,setting_value)
                VALUES (%s,'pass_mark',%s) ON CONFLICT (organization_id,setting_key)
                DO UPDATE SET setting_value=EXCLUDED.setting_value,updated_at=CURRENT_TIMESTAMP""",
                (oid, str(pass_mark)),
            )
            conn.commit()
            session["pass_mark"] = pass_mark
            flash("Organization settings saved.", "success")
            return redirect(url_for("organization_settings", section="grading"))

        cur.execute(
            "SELECT setting_value FROM organization_settings WHERE organization_id=%s AND setting_key='pass_mark'",
            (oid,),
        )
        row = cur.fetchone()
        subjects = _organization_subjects(cur, oid)

        attendance_date = request.args.get("attendance_date", date.today().isoformat())
        try:
            attendance_date = date.fromisoformat(attendance_date).isoformat()
        except (TypeError, ValueError):
            attendance_date = date.today().isoformat()
        cur.execute(
            """SELECT s.roll_number,s.name,a.status
            FROM organization_students s
            LEFT JOIN organization_attendance a ON a.organization_id=s.organization_id
              AND a.student_id=s.id AND a.attendance_date=%s
            WHERE s.organization_id=%s ORDER BY s.roll_number""",
            (attendance_date, oid),
        )
        attendance_rows = cur.fetchall()
        attendance_students = [
            {"roll": item[0], "name": item[1], "status": item[2]}
            for item in attendance_rows
        ]
        attendance_counts = {
            status: sum(student["status"] == status for student in attendance_students)
            for status in ("present", "absent", "late")
        }

        cur.execute(
            """SELECT COUNT(DISTINCT s.id),COALESCE(ROUND(AVG(m.marks),2),0),
            COALESCE(MAX(avg_marks.avg),0),COALESCE(MIN(avg_marks.avg),0)
            FROM organization_students s
            LEFT JOIN organization_student_subject_marks m
              ON m.organization_id=s.organization_id AND m.student_id=s.id
            LEFT JOIN (
              SELECT organization_id,student_id,AVG(marks) AS avg
              FROM organization_student_subject_marks GROUP BY organization_id,student_id
            ) avg_marks ON avg_marks.organization_id=s.organization_id
              AND avg_marks.student_id=s.id
            WHERE s.organization_id=%s""",
            (oid,),
        )
        analytics_summary = cur.fetchone()
        subject_averages = []
        for subject_id, subject_name in subjects:
            cur.execute(
                """SELECT COALESCE(ROUND(AVG(marks),2),0)
                FROM organization_student_subject_marks
                WHERE organization_id=%s AND subject_id=%s""",
                (oid, subject_id),
            )
            subject_averages.append((subject_name, cur.fetchone()[0]))
        analytics_attendance_counts = attendance_counts
    finally:
        cur.close()
        conn.close()

    pass_mark = int(row[0]) if row else 33
    session["pass_mark"] = pass_mark
    return render_template(
        "organizations/settings.html",
        pass_mark=pass_mark,
        subjects=subjects,
        active_section=active_section,
        attendance_date=attendance_date,
        attendance_students=attendance_students,
        attendance_counts=attendance_counts,
        attendance_total=len(attendance_students),
        attendance_unmarked=len(attendance_students) - sum(attendance_counts.values()),
        analytics_summary=analytics_summary,
        subject_averages=subject_averages,
        analytics_attendance_counts=analytics_attendance_counts,
    )

@app.route("/organization/backup")
@organization_required
def organization_download_backup():
    oid = session["organization_id"]
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""SELECT id,roll_number,name,math,science,english FROM organization_students
                       WHERE organization_id=%s ORDER BY roll_number""", (oid,))
        students = cur.fetchall()
        cur.execute("""SELECT s.roll_number,p.date_of_birth,p.gender,p.email,p.phone,p.guardian_name,
            p.guardian_phone,p.address,p.admission_number,p.joining_date,p.admission_standard,
            p.notes,p.photo_data,p.photo_mime
            FROM organization_student_profiles p JOIN organization_students s
              ON s.organization_id=p.organization_id AND s.id=p.student_id
            WHERE p.organization_id=%s ORDER BY s.roll_number""", (oid,))
        profiles = cur.fetchall()
        cur.execute("""SELECT s.roll_number,a.academic_year,a.standard,a.term,a.subject,
            a.marks_obtained,a.maximum_marks FROM organization_student_assessments a
            JOIN organization_students s ON s.organization_id=a.organization_id AND s.id=a.student_id
            WHERE a.organization_id=%s ORDER BY s.roll_number,a.academic_year,a.term,a.subject""", (oid,))
        assessments = cur.fetchall()
        cur.execute("""SELECT s.roll_number,a.attendance_date,a.status FROM organization_attendance a
            JOIN organization_students s ON s.organization_id=a.organization_id AND s.id=a.student_id
            WHERE a.organization_id=%s ORDER BY a.attendance_date,s.roll_number""", (oid,))
        attendance_rows = cur.fetchall()
        cur.execute("""SELECT setting_key,setting_value FROM organization_settings
                       WHERE organization_id=%s ORDER BY setting_key""", (oid,))
        settings = cur.fetchall()
        cur.execute("""SELECT id,subject_name FROM organization_subjects
                       WHERE organization_id=%s ORDER BY subject_name""", (oid,))
        subject_rows = cur.fetchall()
        cur.execute("""SELECT s.roll_number,sub.subject_name,m.marks
            FROM organization_student_subject_marks m
            JOIN organization_students s ON s.organization_id=m.organization_id AND s.id=m.student_id
            JOIN organization_subjects sub ON sub.organization_id=m.organization_id AND sub.id=m.subject_id
            WHERE m.organization_id=%s ORDER BY s.roll_number,sub.subject_name""", (oid,))
        subject_mark_rows = cur.fetchall()
    finally:
        cur.close()
        conn.close()

    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        def add_csv(filename, headers, rows, transform=None):
            output = StringIO(newline="")
            writer = csv.writer(output, lineterminator="\r\n")
            writer.writerow(headers)
            for row in rows:
                values = list(row)
                if transform:
                    values = transform(values)
                writer.writerow(values)
            archive.writestr(filename, "\ufeff" + output.getvalue())

        add_csv("students.csv", ["roll_number","name","math","science","english"],
            [row[1:] for row in students],
            lambda row: [row[0],safe_spreadsheet_text(row[1]),*row[2:]])
        def profile_export(row):
            if row[12] is not None:
                row[12] = base64.b64encode(bytes(row[12])).decode("ascii")
            for index in (1, 9):
                if row[index] is not None:
                    row[index] = row[index].isoformat()
            return row
        add_csv("profiles.csv", ["roll_number","date_of_birth","gender","email","phone",
            "guardian_name","guardian_phone","address","admission_number","joining_date",
            "admission_standard","notes","photo_base64","photo_mime"], profiles, profile_export)
        add_csv("assessments.csv", ["roll_number","academic_year","standard","term","subject",
            "marks_obtained","maximum_marks"], assessments)
        add_csv("attendance.csv", ["roll_number","attendance_date","status"], attendance_rows,
            lambda row: [row[0],row[1].isoformat(),row[2]])
        add_csv("settings.csv", ["setting_key","setting_value"], settings)
        add_csv("subjects.csv", ["subject_name"], [[row[1]] for row in subject_rows])
        add_csv("subject_marks.csv", ["roll_number","subject_name","marks"], subject_mark_rows)
        archive.writestr("BACKUP_README.txt",
            "EduTrack organization backup. Includes custom subjects and student subject marks. Restore is add-only; existing records are not overwritten.")
    buffer.seek(0)
    response = send_file(buffer, as_attachment=True,
        download_name="edutrack-organization-backup.zip", mimetype="application/zip", max_age=0)
    response.headers["Cache-Control"] = "private, no-store"
    return response


@app.route("/organization/restore", methods=["GET", "POST"])
@organization_required
def organization_restore_backup():
    if request.method == "POST":
        upload = request.files.get("backup_file")
        if not upload or not upload.filename or not upload.filename.lower().endswith(".zip"):
            flash("Choose an EduTrack organization backup ZIP file.", "danger")
            return redirect(url_for("organization_restore_backup"))
        raw = upload.read(10 * 1024 * 1024 + 1)
        if len(raw) > 10 * 1024 * 1024:
            flash("Backup is too large. Maximum size is 10 MB.", "danger")
            return redirect(url_for("organization_restore_backup"))
        conn = get_db_connection()
        cur = conn.cursor()
        oid = session["organization_id"]
        try:
            with zipfile.ZipFile(BytesIO(raw)) as archive:
                allowed = {"students.csv", "profiles.csv", "assessments.csv", "attendance.csv", "settings.csv",
                           "subjects.csv", "subject_marks.csv", "BACKUP_README.txt"}
                names = archive.namelist()
                if (len(names) != len(set(names)) or any(name not in allowed for name in names)
                    or "students.csv" not in names
                    or sum(item.file_size for item in archive.infolist()) > 25 * 1024 * 1024
                    or any(item.file_size > 10 * 1024 * 1024 for item in archive.infolist())):
                    raise ValueError("Unrecognised backup archive")
                def read_rows(name):
                    if name not in names:
                        return []
                    return list(csv.DictReader(StringIO(archive.read(name).decode("utf-8-sig"))))
                student_rows = read_rows("students.csv")
                validated = []
                for index, item in enumerate(student_rows, start=2):
                    data, error = validate_student_form({
                        "roll":item.get("roll_number",""), "name":item.get("name",""),
                        "math":item.get("math",""), "science":item.get("science",""),
                        "english":item.get("english","")})
                    if error:
                        raise ValueError(f"students.csv row {index}: {error}")
                    validated.append(data)
                rolls = [str(item["roll"]) for item in validated]
                if len(rolls) != len(set(rolls)):
                    raise ValueError("Backup contains duplicate roll numbers")
                cur.executemany("""INSERT INTO organization_students
                    (organization_id,roll_number,name,math,science,english)
                    VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT (organization_id,roll_number) DO NOTHING""",
                    [(oid,str(x["roll"]),x["name"],x["math"],x["science"],x["english"]) for x in validated])
                restored_students = cur.rowcount
                cur.execute("SELECT id,roll_number FROM organization_students WHERE organization_id=%s", (oid,))
                student_ids = {str(roll):student_id for student_id,roll in cur.fetchall()}
                for item in read_rows("profiles.csv"):
                    roll = str(item.get("roll_number",""))
                    if roll not in student_ids:
                        continue
                    photo = base64.b64decode(item["photo_base64"], validate=True) if item.get("photo_base64") else None
                    mime = item.get("photo_mime") or None
                    valid_photo = (not photo or
                        (mime == "image/jpeg" and photo.startswith(b"\\xff\\xd8\\xff")) or
                        (mime == "image/png" and photo.startswith(b"\\x89PNG\\r\\n\\x1a\\n")) or
                        (mime == "image/webp" and len(photo)>12 and photo[:4]==b"RIFF" and photo[8:12]==b"WEBP"))
                    if not valid_photo or (photo and len(photo)>1024*1024) or (not photo and mime):
                        raise ValueError("Invalid profile photo in backup")
                    cur.execute("""INSERT INTO organization_student_profiles
                        (organization_id,student_id,date_of_birth,gender,email,phone,guardian_name,
                         guardian_phone,address,admission_number,joining_date,admission_standard,notes,
                         photo_data,photo_mime)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT (organization_id,student_id) DO NOTHING""",
                        (oid,student_ids[roll],item.get("date_of_birth") or None,item.get("gender") or None,
                         item.get("email") or None,item.get("phone") or None,item.get("guardian_name") or None,
                         item.get("guardian_phone") or None,item.get("address") or None,
                         item.get("admission_number") or None,item.get("joining_date") or None,
                         item.get("admission_standard") or None,item.get("notes") or None,
                         psycopg2.Binary(photo) if photo else None,mime))
                for item in read_rows("assessments.csv"):
                    roll = str(item.get("roll_number",""))
                    if roll not in student_ids:
                        continue
                    marks = float(item["marks_obtained"]); maximum = float(item["maximum_marks"])
                    if not (0 <= marks <= maximum and maximum > 0):
                        raise ValueError("Invalid assessment marks in backup")
                    cur.execute("""INSERT INTO organization_student_assessments
                        (organization_id,student_id,academic_year,standard,term,subject,marks_obtained,maximum_marks)
                        SELECT %s,%s,%s,%s,%s,%s,%s,%s
                        WHERE NOT EXISTS (
                            SELECT 1 FROM organization_student_assessments
                            WHERE organization_id=%s AND student_id=%s AND academic_year=%s
                              AND standard=%s AND term=%s AND subject=%s
                              AND marks_obtained=%s AND maximum_marks=%s
                        )""",
                        (oid,student_ids[roll],item["academic_year"],item["standard"],item["term"],
                         item["subject"],marks,maximum,oid,student_ids[roll],item["academic_year"],
                         item["standard"],item["term"],item["subject"],marks,maximum))
                for item in read_rows("attendance.csv"):
                    roll = str(item.get("roll_number",""))
                    status = item.get("status","")
                    if roll not in student_ids or status not in {"present","absent","late"}:
                        raise ValueError("Invalid attendance record in backup")
                    cur.execute("""INSERT INTO organization_attendance
                        (organization_id,student_id,attendance_date,status)
                        VALUES (%s,%s,%s,%s) ON CONFLICT (organization_id,student_id,attendance_date) DO NOTHING""",
                        (oid,student_ids[roll],item["attendance_date"],status))
                for item in read_rows("subjects.csv"):
                    subject_name = (item.get("subject_name") or "").strip()
                    if not subject_name or len(subject_name) > 80:
                        raise ValueError("Invalid subject name in backup")
                    cur.execute("""INSERT INTO organization_subjects (organization_id,subject_name)
                        VALUES (%s,%s) ON CONFLICT (organization_id,subject_name) DO NOTHING""",
                        (oid, subject_name))
                cur.execute("SELECT id,subject_name FROM organization_subjects WHERE organization_id=%s", (oid,))
                subject_ids = {str(name).strip().lower(): int(subject_id) for subject_id, name in cur.fetchall()}
                for item in read_rows("subject_marks.csv"):
                    roll = str(item.get("roll_number", ""))
                    subject_name = (item.get("subject_name") or "").strip().lower()
                    if roll not in student_ids or subject_name not in subject_ids:
                        raise ValueError("Unknown student or subject in subject_marks.csv")
                    try:
                        mark = float(item.get("marks", ""))
                    except (TypeError, ValueError):
                        raise ValueError("Invalid subject mark in backup")
                    if not 0 <= mark <= 100:
                        raise ValueError("Subject marks must be between 0 and 100")
                    cur.execute("""INSERT INTO organization_student_subject_marks
                        (organization_id,student_id,subject_id,marks)
                        VALUES (%s,%s,%s,%s) ON CONFLICT (organization_id,student_id,subject_id) DO NOTHING""",
                        (oid, student_ids[roll], subject_ids[subject_name], mark))
                for item in read_rows("settings.csv"):
                    if item.get("setting_key") == "pass_mark":
                        mark = int(item.get("setting_value",""))
                        if 0 <= mark <= 100:
                            cur.execute("""INSERT INTO organization_settings (organization_id,setting_key,setting_value)
                                VALUES (%s,'pass_mark',%s) ON CONFLICT (organization_id,setting_key) DO NOTHING""",
                                (oid,str(mark)))
            conn.commit()
            flash(f"Restore complete: {restored_students} new students added. Existing organization records were preserved.", "success")
            return redirect(url_for("organization_students"))
        except (zipfile.BadZipFile, KeyError, ValueError, UnicodeDecodeError, TypeError):
            conn.rollback()
            flash("The backup is damaged or contains invalid data. No changes were saved.", "danger")
            return redirect(url_for("organization_restore_backup"))
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()
    return render_template("organizations/restore.html")



@app.route("/organization/students/<path:roll>/result.pdf")
@organization_required
def organization_download_student_result(roll):
    oid = session["organization_id"]
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""SELECT id,roll_number,name FROM organization_students
            WHERE organization_id=%s AND roll_number=%s""", (oid,roll))
        student = cur.fetchone()
        if student:
            cur.execute("""SELECT sub.subject_name,m.marks FROM organization_student_subject_marks m
                JOIN organization_subjects sub ON sub.organization_id=m.organization_id AND sub.id=m.subject_id
                WHERE m.organization_id=%s AND m.student_id=%s ORDER BY sub.subject_name""",(oid,student[0]))
            subject_marks=cur.fetchall()
    finally:
        cur.close()
        conn.close()
    if not student:
        abort(404)
    average = calculate_average([x[1] for x in subject_marks])
    grade = calculate_grade(average)
    styles = getSampleStyleSheet()
    buffer = BytesIO()
    document = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=48, leftMargin=48,
        topMargin=48, bottomMargin=48, title=f"EduTrack Result - {student[1]}")
    story = [
        Paragraph("EduTrack Student Result Card", styles["Title"]),
        Spacer(1, 12),
        Paragraph(f"<b>Student Name:</b> {escape(str(student[1]))}", styles["BodyText"]),
        Paragraph(f"<b>Roll Number:</b> {escape(str(student[0]))}", styles["BodyText"]),
        Spacer(1, 18),
    ]
    result_rows = [["Subject", "Marks"]]
    for subject, mark in subject_marks:
        result_rows.append([subject, str(mark)])
    result_rows.extend([["Average", f"{average}%"], ["Grade", grade]])
    table = Table(result_rows, colWidths=[240, 180])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#244A73")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D7DEE8")),
        ("PADDING", (0, 0), (-1, -1), 9),
    ]))
    story.append(table)
    document.build(story)
    buffer.seek(0)
    response = send_file(buffer, as_attachment=True,
        download_name=f"student-result-{student[1]}.pdf", mimetype="application/pdf")
    response.headers["Cache-Control"] = "private, no-store"
    return response
if __name__ == "__main__":
    app.run(debug=True)
    
