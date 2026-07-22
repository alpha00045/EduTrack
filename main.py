import psycopg2
import time
import sys
import os

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
        EXTERNAL_URL = "postgresql://edutrack_db_qufk_user:WRnGZGxftYOAmNaG0uHTrc8Sgc6RdFmK@dpg-d9g9t9mrnols73c4lovg-a.singapore-postgres.render.com/edutrack_db_qufk"
        self.conn = psycopg2.connect(EXTERNAL_URL)
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
            return "ERROR: STUDENT ALREADY EXISTS"

    def add_grades(self, roll_number, math, science, english):
        self.cursor.execute("SELECT * FROM students WHERE roll_number=%s", (roll_number,))
        if not self.cursor.fetchone():
            return "ERROR: STUDENT NOT FOUND"
        self.cursor.execute("UPDATE students SET math=%s, science=%s, english=%s WHERE roll_number=%s   ", (math, science, english, roll_number))
        self.conn.commit()
        return "Grades Assigned Successfully"

    def get_all_students(self):
        self.cursor.execute("SELECT roll_number, name, math, science, english FROM students")
        return [Student(row[1], row[0], row[2], row[3], row[4]) for row in self.cursor.fetchall()]

    # 9. BONUS FEATURES
    def subject_topper(self, subject):
        self.cursor.execute(f"SELECT name, {subject.lower()} FROM students WHERE {subject.lower()} IS NOT NULL ORDER BY {subject.lower()} DESC LIMIT 1")
        row = self.cursor.fetchone()
        if row: return f"Topper in {subject}: {row[0]} with {row[1]} marks"
        return f"No data for {subject}"

    def class_average(self, subject):
        self.cursor.execute(f"SELECT AVG({subject.lower()}) FROM students WHERE {subject.lower()} IS NOT NULL")
        row = self.cursor.fetchone()
        if row[0]: return f"Class Average for {subject}: {round(row[0], 2)}"
        return f"No data for {subject}"

    def backup_data(self):
        students = self.get_all_students()
        with open("student_backup.txt", "w") as f:
            for s in students:
                f.write(f"{s.roll_number},{s.name},{s.grades['Math']},{s.grades['Science']},{s.grades['English']}\n")
        return "Data backed up to student_backup.txt"

# --- 5. LOOP FOR CONTINUOUS INTERACTION ---
def main():
    tracker = StudentTracker()
    students = tracker.get_all_students()
    
    if not students:
        print('\n>>> NO STUDENTS ENROLLED')
    else:
        print('EXISTING STUDENTS:\n')
        for s in students:
            s.display_info()
            
    while True:
        print("\n1. Add Student")
        print("2. Assign Grades")
        print("3. View Subject Topper (Bonus)")
        print("4. View Class Average (Bonus)")
        print("5. Save Data Locally (Bonus)")
        print("6. Reload")
        print("7. Exit")
        
        try:
            choice = int(input("\nChoose an option: "))
        except ValueError:
            print('\n\n !!!!!!!!! INVALID INPUT')
            continue

        if choice == 1:
            print('\nFill The Data asked below:\n')
            name = input('Enter Student Name: ')
            roll = input('Enter Roll Number: ')
            print('\n', tracker.add_student(name, roll))
            
        elif choice == 2:
            roll = input('Enter Roll Number: ')
            try:
                # 4. Conditional Logic and Flow Control (0 to 100 validation)
                m = float(input("Math Grade (0-100): "))
                s = float(input("Science Grade (0-100): "))
                e = float(input("English Grade (0-100): "))
                
                if all(0 <= val <= 100 for val in [m, s, e]):
                    print('\n', tracker.add_grades(roll, m, s, e))
                else:
                    print('\nERROR: Grades must be between 0 and 100')
            except ValueError:
                print('\nERROR: Invalid Number')
                
        elif choice == 3:
            sub = input("Enter Subject (Math/Science/English): ")
            if sub.lower() in ['math', 'science', 'english']:
                print('\n', tracker.subject_topper(sub))
            else:
                print('\n Invalid Subject')
                
        elif choice == 4:
            sub = input("Enter Subject (Math/Science/English): ")
            if sub.lower() in ['math', 'science', 'english']:
                print('\n', tracker.class_average(sub))
            else:
                print('\n Invalid Subject')
                
        elif choice == 5:
            print('\n', tracker.backup_data())
            
        elif choice == 6:
            print('\n')
            reloading_data_spinner(2)
            print('\nStudent Performance Tracker\n')
            return main()
            
        elif choice == 7:
            saving_data_spinner(2)
            print('\nThank you for using >>> STUDENT TRACKER <<<\n\n')
            break
        else:
            print('\n\n !!!!!!!!! INVALID INPUT')

if __name__ == '__main__':
    run_spinner(2)
    print('\nStudent Performance Tracker\n')
    main()