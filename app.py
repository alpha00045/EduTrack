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
    conn.close()
    return render_template("index.html", students=students)

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
