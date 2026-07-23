# 🎓 EduTrack – Student Performance Tracker

A Python-based **Student Performance Tracking System** with both a **Command Line Interface (CLI)** and a **Flask-powered Web Dashboard**, backed by a **PostgreSQL cloud database** hosted on **Render**.

---

## 📌 Overview

EduTrack is a student management system designed to help teachers manage student records and academic performance efficiently.

The application provides two interfaces:

- 💻 Command Line Interface (CLI)
- 🌐 Web Dashboard (Flask)

Student records are stored in a PostgreSQL database hosted on Render, ensuring persistent cloud storage.

---

## ✨ Features

### 👨‍🎓 Student Management
- Add new students
- Unique Roll Number validation
- Persistent database storage

### 📚 Grade Management
- Assign grades
- Grade validation (0–100)
- Update existing student records

### 📊 Performance Analytics
- Calculate student average
- View subject topper
- View class average

### 💾 Backup
- Export all records to `student_backup.txt`

### 🌐 Web Dashboard
- View all students
- Add students from browser
- Real-time PostgreSQL synchronization

### ☁ Cloud Deployment
- Hosted on Render
- PostgreSQL Database
- Gunicorn Production Server

---

## 🛠 Tech Stack

| Category | Technology |
|----------|------------|
| **Language** | Python 3 |
| **Backend** | Flask |
| **Database** | PostgreSQL |
| **Deployment** | Render |
| **Server** | Gunicorn |
| **Version Control** | Git & GitHub |

---

## 📁 Project Structure

```text
EduTrack/
│
├── app.py
├── main.py
├── requirements.txt
├── Procfile
├── User_Guide.txt
├── student_backup.txt
├── students.db
└── README.md
```

---

## 🚀 Installation

### Clone the Repository

```bash
git clone https://github.com/alpha00045/EduTrack.git
