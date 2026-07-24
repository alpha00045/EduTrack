from flask import Flask, request, render_template_string, redirect
import psycopg2

app = Flask(__name__)



@app.route('/')
def index():
    INTERNAL_URL = "postgresql://edutrack_db_qufk_user:WRnGZGxftYOAmNaG0uHTrc8Sgc6RdFmK@dpg-d9g9t9mrnols73c4lovg-a.singapore-postgres.render.com/edutrack_db_qufk"
    conn = psycopg2.connect(INTERNAL_URL)
    cur = conn.cursor()
    cur.execute("SELECT roll_number, name, math, science, english FROM students")
    students = cur.fetchall()
    conn.close()
    return render_template_string(HTML_TEMPLATE, students=students)

@app.route('/add', methods=['POST'])
def add():
    INTERNAL_URL = "postgresql://edutrack_db_qufk_user:WRnGZGxftYOAmNaG0uHTrc8Sgc6RdFmK@dpg-d9g9t9mrnols73c4lovg-a/edutrack_db_qufk"
    conn = psycopg2.connect(INTERNAL_URL)
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
