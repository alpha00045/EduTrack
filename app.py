from flask import Flask, request, render_template_string, redirect
import psycopg2

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Student Tracker</title>
    <style>
        body { font-family: Arial; padding: 20px; }
        table { border-collapse: collapse; width: 80%; margin-top: 20px; }
        th, td { border: 1px solid black; padding: 8px; text-align: left; }
        th { background-color: #f2f2f2; }
    </style>
</head>
<body>
    <h2>Student Performance Tracker (Web Interface)</h2>
    <form method="POST" action="/add">
        <input type="text" name="roll" placeholder="Roll Number" required>
        <input type="text" name="name" placeholder="Student Name" required>
        <button type="submit">Add Student</button>
    </form>
    
    <table>
        <tr>
            <th>Roll Number</th>
            <th>Name</th>
            <th>Math</th>
            <th>Science</th>
            <th>English</th>
        </tr>
        {% for s in students %}
        <tr>
            <td>{{ s[0] }}</td>
            <td>{{ s[1] }}</td>
            <td>{{ s[2] if s[2] != None else 'N/A' }}</td>
            <td>{{ s[3] if s[3] != None else 'N/A' }}</td>
            <td>{{ s[4] if s[4] != None else 'N/A' }}</td>
        </tr>
        {% endfor %}
    </table>
</body>
</html>
"""

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
