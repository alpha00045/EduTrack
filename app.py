from flask import Flask, request, render_template, redirect
import psycopg2
import os
app = Flask(__name__)

@app.route('/')
def index():
    DATABASE_URL = os.getenv("DATABASE_URL")
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute("SELECT roll_number, name, math, science, english FROM students")
    students = cur.fetchall()
    student_data = []

    for s in students:
        marks = [m for m in [s[2], s[3], s[4]] if m is not None]
        if marks:
            average = round(sum(marks) / len(marks), 2)
        else:
            average = 0

        if average >= 90:
            grade = "A+"
        elif average >= 80:
            grade = "A"
        elif average >= 70:
            grade = "B"
        elif average >= 60:
            grade = "C"
        else:
            grade = "F"

        student_data.append({
            "roll": s[0],
            "name": s[1],
            "math": s[2],
            "science": s[3],
            "english": s[4],
            "average": average,
            "grade": grade
        })
    student_data.sort(key=lambda x: x["average"], reverse=True)
    total_students = len(students)
    averages = []
    highest = 0

    for student in students:
        marks = [m for m in [student[2], student[3], student[4]] if m is not None]
        if marks:
            avg = sum(marks) / len(marks)
            averages.append(avg)
            if avg > highest:
                highest = avg

    class_average = round(sum(averages) / len(averages), 2) if averages else 0
    subjects = 3

    conn.close()
    return render_template(
       "students/list.html",
        students=student_data,
        total_students=total_students,
        class_average=class_average,
        highest=round(highest, 2),
        subjects=subjects
    )

@app.route('/add', methods=['POST'])
def add():
    DATABASE_URL = os.getenv("DATABASE_URL")
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO students (roll_number, name) VALUES (%s, %s)", 
                    (request.form['roll'], request.form['name']))
        conn.commit()
    except psycopg2.IntegrityError:
        pass
    conn.close()
    return redirect('/')

if __name__ == "__main__":
    app.run(debug=True)
    
@app.route("/add_student")
def add_student():

    return render_template("students/add.html")
