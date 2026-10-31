import psycopg2
import time
import sys
import os
import csv

# --- 5. SPINNER FUNCTIONS (Formatted to your requirements) ---
def saving_data_spinner(duration=2):
    spinner = ['|', '/', '-', '\\']
    end_time = time.time() + duration
    idx = 0
    print("Saving data... ", end="")
    while time.time() < end_time:
        sys.stdout.write(f"\rSaving data... {spinner[idx % len(spinner)]}")
        sys.stdout.flush() 
        idx += 1
        time.sleep(0.1) 
    sys.stdout.write("\rData Saved Successfully! \n")

def reloading_data_spinner(duration=2):
    spinner = ['|', '/', '-', '\\']
    end_time = time.time() + duration
    idx = 0
    print("Reloading program... ", end="")
    while time.time() < end_time:
        sys.stdout.write(f"\rReloading program... {spinner[idx % len(spinner)]}")
        sys.stdout.flush() 
        idx += 1
        time.sleep(0.1) 
    sys.stdout.write("\r Reloading Succesfull \n")

def run_spinner(duration=2):
    spinner = ['|', '/', '-', '\\']
    end_time = time.time() + duration
    idx = 0
    print("Loading data... ", end="")
    while time.time() < end_time:
        sys.stdout.write(f"\rLoading data... {spinner[idx % len(spinner)]}")
        sys.stdout.flush() 
        idx += 1
        time.sleep(0.1)
    sys.stdout.write("\rData Loaded Successfully! \n")


# --- 2. OBJECT-ORIENTED DESIGN & 6. DATABASE INTEGRATION ---
class Student:
    def __init__(self, name, roll_number, math=None, science=None, english=None):
        self.name = name.upper()
        self.roll_number = roll_number
        self.grades = {"Math": math, "Science": science, "English": english}

    def add_grades(self, math, science, english):
        self.grades["Math"] = math
        self.grades["Science"] = science
        self.grades["English"] = english

    def calculate_average(self):
        scores = [v for v in self.grades.values() if v is not None]
        if not scores: return 0.0
        return round(sum(scores) / len(scores), 2)
        
    def display_info(self):
        print('-' * 85)
        print(f"| {'SNO/ROLL:':<10} {self.roll_number:<15} | {'NAME:':<6} {self.name:<43} |")
        print('-' * 85)
        m = self.grades['Math'] if self.grades['Math'] is not None else 'N/A'
        s = self.grades['Science'] if self.grades['Science'] is not None else 'N/A'
        e = self.grades['English'] if self.grades['English'] is not None else 'N/A'
        print(f"| GRADES -> Math: {m:<10} Science: {s:<10} English: {e:<10}           |")
        print(f"| AVERAGE: {self.calculate_average():<71} |")
        print('-' * 85)

class StudentTracker:
    def __init__(self):
        # 6. PostgreSQL Database
        DATABASE_URL = os.getenv("DATABASE_URL")
        self.conn = psycopg2.connect(DATABASE_URL)
        self.cursor = self.conn.cursor()
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS students 
                               (roll_number TEXT PRIMARY KEY, name TEXT, math REAL, science REAL, english REAL)''')
        self.conn.commit()

    # 1. Core Functionalities
    def add_student(self, name, roll_number):
        try:
            self.cursor.execute("INSERT INTO students (roll_number, name) VALUES (%s, %s)", (roll_number, name))
            self.conn.commit()
            return "Student Added Successfully"
        except psycopg2.IntegrityError:
            self.conn.rollback()
            return "ERROR: STUDENT ALREADY EXISTS"
        except psycopg2.Error:
            self.conn.rollback()
            return "ERROR: DATABASE OPERATION FAILED"

    def add_grades(self, roll_number, math, science, english):
        try:
            self.cursor.execute(
                "SELECT * FROM students WHERE roll_number=%s", (roll_number,)
            )
            if not self.cursor.fetchone():
                return "ERROR: STUDENT NOT FOUND"
            self.cursor.execute(
                "UPDATE students SET math=%s, science=%s, english=%s WHERE roll_number=%s",
                (math, science, english, roll_number),
            )
            self.conn.commit()
            return "Grades Assigned Successfully"
        except psycopg2.Error:
            self.conn.rollback()
            return "ERROR: DATABASE OPERATION FAILED"

    def get_all_students(self):
        self.cursor.execute("SELECT roll_number, name, math, science, english FROM students")
        return [Student(row[1], row[0], row[2], row[3], row[4]) for row in self.cursor.fetchall()]

    # 9. BONUS FEATURES
    def _subject_column(self, subject):
        return {"math": "math", "science": "science", "english": "english"}.get(
            str(subject).strip().lower()
        )

    def subject_topper(self, subject):
        column = self._subject_column(subject)
        if column is None:
            return "ERROR: INVALID SUBJECT"
        self.cursor.execute(
            f"SELECT name, {column} FROM students "
            f"WHERE {column} IS NOT NULL ORDER BY {column} DESC LIMIT 1"
        )
        row = self.cursor.fetchone()
        if row:
            return f"Topper in {column.title()}: {row[0]} with {row[1]} marks"
        return f"No data for {column.title()}"

    def class_average(self, subject):
        column = self._subject_column(subject)
        if column is None:
            return "ERROR: INVALID SUBJECT"
        self.cursor.execute(
            f"SELECT AVG({column}) FROM students WHERE {column} IS NOT NULL"
        )
        row = self.cursor.fetchone()
        if row and row[0] is not None:
            return f"Class Average for {column.title()}: {round(row[0], 2)}"
        return f"No data for {column.title()}"

    def backup_data(self):
        students = self.get_all_students()
        with open("student_backup.txt", "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Roll Number", "Name", "Math", "Science", "English"])
            for student in students:
                writer.writerow([
                    student.roll_number,
                    student.name,
                    student.grades["Math"],
                    student.grades["Science"],
                    student.grades["English"],
                ])
        return "Data backed up to student_backup.txt"

    def close(self):
        try:
            self.cursor.close()
        finally:
            self.conn.close()

# --- 5. LOOP FOR CONTINUOUS INTERACTION ---
def main():
    tracker = StudentTracker()
    try:
        show_students = True
        while True:
            if show_students:
                students = tracker.get_all_students()
                if not students:
                    print("\\n>>> NO STUDENTS ENROLLED")
                else:
                    print("EXISTING STUDENTS:\\n")
                    for student in students:
                        student.display_info()
                show_students = False

            print("\\n1. Add Student")
            print("2. Assign Grades")
            print("3. View Subject Topper (Bonus)")
            print("4. View Class Average (Bonus)")
            print("5. Save Data Locally (Bonus)")
            print("6. Reload")
            print("7. Exit")

            try:
                choice = int(input("\\nChoose an option: "))
            except ValueError:
                print("\\nINVALID INPUT: Enter a number from 1 to 7.")
                continue

            if choice == 1:
                name = input("Enter Student Name: ").strip()
                roll = input("Enter Roll Number: ").strip()
                if not name or not roll:
                    print("ERROR: Name and roll number are required.")
                    continue
                print(tracker.add_student(name, roll))
                show_students = True

            elif choice == 2:
                roll = input("Enter Roll Number: ").strip()
                try:
                    marks = [
                        int(input("Math Marks (0-100): ")),
                        int(input("Science Marks (0-100): ")),
                        int(input("English Marks (0-100): ")),
                    ]
                    if any(mark < 0 or mark > 100 for mark in marks):
                        print("ERROR: Marks must be between 0 and 100.")
                        continue
                    print(tracker.add_grades(roll, *marks))
                    show_students = True
                except ValueError:
                    print("ERROR: Enter whole-number marks from 0 to 100.")

            elif choice == 3:
                subject = input("Enter Subject (Math/Science/English): ")
                print(tracker.subject_topper(subject))

            elif choice == 4:
                subject = input("Enter Subject (Math/Science/English): ")
                print(tracker.class_average(subject))

            elif choice == 5:
                print(tracker.backup_data())

            elif choice == 6:
                reloading_data_spinner(1)
                show_students = True

            elif choice == 7:
                saving_data_spinner(1)
                print("\\nThank you for using >>> STUDENT TRACKER <<<\\n")
                break

            else:
                print("INVALID INPUT: Enter a number from 1 to 7.")
    finally:
        tracker.close()

if __name__ == '__main__':
    run_spinner(2)
    print('\nStudent Performance Tracker\n')
    main()