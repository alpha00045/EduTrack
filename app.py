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

    # Dashboard Statistics
    total_students = len(students)

    averages = []
    highest = 0

    for student in students:
        marks = [student[2], student[3], student[4]]
        marks = [m for m in marks if m is not None]
        if marks:
            avg = sum(marks) / len(marks)
            averages.append(avg)
            if avg > highest:
                highest = avg

    class_average = round(sum(averages) / len(averages), 2) if averages else 0
    subjects = 3
    conn.close()
    return render_template("index.html", students=students, total_students=total_students, class_average=class_average, highest=highest, subjects=subjects)

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
