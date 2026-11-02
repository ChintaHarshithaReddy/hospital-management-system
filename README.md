# Hospital Management System (Full-Stack)

A web-based Hospital Management System built with **Python Flask**, **SQLite**, HTML, CSS, and Jinja templates.

## Features
- **Staff login** with hashed passwords and two roles (admin, staff)
- **Dashboard:** patient and doctor counts, today's appointments, unpaid bills and revenue
- **Patients:** register, search, edit, view full history; admin-only delete
- **Doctors:** list with upcoming appointment counts; admin adds and removes
- **Appointments:** book, filter by status, complete, cancel, delete; blocks double-booking a doctor
- **Prescriptions:** add medicines and dosage to a patient record
- **Billing:** create bills, mark as paid, printable invoices
- **User management:** admin creates staff accounts; everyone can change their password

## Tech stack
Python 3, Flask, SQLite (built into Python), HTML5, CSS3, Jinja2

## Project structure
```
hospital-management-system/
├── app.py              # routes, database, login
├── requirements.txt
├── templates/          # HTML pages (Jinja)
├── static/style.css    # styling
└── README.md
```
The database file `hospital.db` is created automatically on first run.

## How to run (Windows PowerShell)
```
cd hospital-management-system
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app.py
```
Open http://127.0.0.1:5000 and log in with **admin / admin123**. Change the password under Users.

If `venv\Scripts\activate` is blocked, run `Set-ExecutionPolicy -Scope Process Bypass` first.

## Database tables
users, doctors, patients, appointments, prescriptions, bills (patients link to the others, and deleting a patient removes their records).

## Future improvements
- Doctor-specific logins and schedules
- Lab reports and file uploads
- Charts on the dashboard
- Deploy online (Render or PythonAnywhere)

## Author
Chinta Harshitha Reddy
