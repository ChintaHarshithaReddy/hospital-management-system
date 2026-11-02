"""Hospital Management System - Flask + SQLite.

Run:  python app.py   then open http://127.0.0.1:5000
First login: admin / admin123  (change the password after logging in)
"""
import os
import sqlite3
from datetime import date
from functools import wraps

from flask import (Flask, abort, flash, g, redirect, render_template,
                   request, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hospital.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'staff'
);
CREATE TABLE IF NOT EXISTS doctors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    specialization TEXT NOT NULL,
    phone TEXT
);
CREATE TABLE IF NOT EXISTS patients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    age INTEGER NOT NULL,
    gender TEXT NOT NULL,
    phone TEXT NOT NULL,
    address TEXT,
    blood_group TEXT,
    notes TEXT,
    created_at TEXT DEFAULT CURRENT_DATE
);
CREATE TABLE IF NOT EXISTS appointments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    doctor_id INTEGER NOT NULL REFERENCES doctors(id) ON DELETE CASCADE,
    appt_date TEXT NOT NULL,
    appt_time TEXT NOT NULL,
    reason TEXT,
    status TEXT NOT NULL DEFAULT 'Scheduled'
);
CREATE TABLE IF NOT EXISTS prescriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    doctor_id INTEGER REFERENCES doctors(id) ON DELETE SET NULL,
    medicine TEXT NOT NULL,
    dosage TEXT NOT NULL,
    instructions TEXT,
    created_at TEXT DEFAULT CURRENT_DATE
);
CREATE TABLE IF NOT EXISTS bills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    description TEXT NOT NULL,
    amount REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'Unpaid',
    created_at TEXT DEFAULT CURRENT_DATE
);
"""


# ---------- Database helpers ----------
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DB_PATH)
    db.executescript(SCHEMA)
    if not db.execute("SELECT 1 FROM users").fetchone():
        db.execute("INSERT INTO users (username, password_hash, role) VALUES (?,?,?)",
                   ("admin", generate_password_hash("admin123"), "admin"))
        db.executemany("INSERT INTO doctors (name, specialization, phone) VALUES (?,?,?)", [
            ("Dr. Sharma", "General Medicine", "9000000001"),
            ("Dr. Rao", "Cardiology", "9000000002"),
            ("Dr. Iyer", "Pediatrics", "9000000003"),
            ("Dr. Khan", "Orthopedics", "9000000004"),
        ])
    db.commit()
    db.close()


# ---------- Auth ----------
def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if session.get("role") != "admin":
            flash("Only an admin can do that.", "error")
            return redirect(url_for("dashboard"))
        return view(*args, **kwargs)
    return wrapped


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = get_db().execute("SELECT * FROM users WHERE username = ?",
                                (request.form["username"].strip(),)).fetchone()
        if user and check_password_hash(user["password_hash"], request.form["password"]):
            session.clear()
            session.update(user_id=user["id"], username=user["username"], role=user["role"])
            nxt = request.args.get("next", "")
            return redirect(nxt if nxt.startswith("/") and not nxt.startswith("//") else url_for("dashboard"))
        flash("Wrong username or password.", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/users", methods=["GET", "POST"])
@admin_required
def users():
    db = get_db()
    if request.method == "POST":
        username, password = request.form["username"].strip(), request.form["password"]
        if len(password) < 6:
            flash("Password must be at least 6 characters.", "error")
        else:
            try:
                db.execute("INSERT INTO users (username, password_hash, role) VALUES (?,?,?)",
                           (username, generate_password_hash(password), request.form["role"]))
                db.commit()
                flash(f"User {username} created.", "ok")
            except sqlite3.IntegrityError:
                flash("That username already exists.", "error")
        return redirect(url_for("users"))
    return render_template("users.html", users=db.execute("SELECT id, username, role FROM users").fetchall())


@app.route("/password", methods=["POST"])
@login_required
def change_password():
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()
    new = request.form["new_password"]
    if not check_password_hash(user["password_hash"], request.form["old_password"]):
        flash("Current password is wrong.", "error")
    elif len(new) < 6:
        flash("New password must be at least 6 characters.", "error")
    else:
        db.execute("UPDATE users SET password_hash = ? WHERE id = ?", (generate_password_hash(new), user["id"]))
        db.commit()
        flash("Password changed.", "ok")
    return redirect(url_for("users") if session["role"] == "admin" else url_for("dashboard"))


# ---------- Dashboard ----------
@app.route("/")
@login_required
def dashboard():
    db = get_db()
    today = date.today().isoformat()
    one = lambda sql, *a: db.execute(sql, a).fetchone()[0]
    stats = {
        "patients": one("SELECT COUNT(*) FROM patients"),
        "doctors": one("SELECT COUNT(*) FROM doctors"),
        "today": one("SELECT COUNT(*) FROM appointments WHERE appt_date = ? AND status != 'Cancelled'", today),
        "unpaid": one("SELECT COALESCE(SUM(amount),0) FROM bills WHERE status = 'Unpaid'"),
        "revenue": one("SELECT COALESCE(SUM(amount),0) FROM bills WHERE status = 'Paid'"),
    }
    todays = db.execute("""SELECT a.*, p.name AS patient, d.name AS doctor FROM appointments a
        JOIN patients p ON p.id = a.patient_id JOIN doctors d ON d.id = a.doctor_id
        WHERE a.appt_date = ? ORDER BY a.appt_time""", (today,)).fetchall()
    recent = db.execute("SELECT * FROM patients ORDER BY id DESC LIMIT 5").fetchall()
    return render_template("dashboard.html", stats=stats, todays=todays, recent=recent)


# ---------- Patients ----------
def get_patient(pid):
    p = get_db().execute("SELECT * FROM patients WHERE id = ?", (pid,)).fetchone()
    if p is None:
        abort(404)
    return p


def patient_fields():
    f = request.form
    return (f["name"].strip(), int(f["age"]), f["gender"], f["phone"].strip(),
            f.get("address", "").strip(), f.get("blood_group", ""), f.get("notes", "").strip())


@app.route("/patients")
@login_required
def patients():
    q = request.args.get("q", "").strip()
    like = f"%{q}%"
    rows = get_db().execute(
        "SELECT * FROM patients WHERE name LIKE ? OR phone LIKE ? ORDER BY name", (like, like)).fetchall()
    return render_template("patients.html", patients=rows, q=q)


@app.route("/patients/add", methods=["GET", "POST"])
@login_required
def patient_add():
    if request.method == "POST":
        db = get_db()
        cur = db.execute("""INSERT INTO patients (name, age, gender, phone, address, blood_group, notes)
                            VALUES (?,?,?,?,?,?,?)""", patient_fields())
        db.commit()
        flash("Patient registered.", "ok")
        return redirect(url_for("patient_detail", pid=cur.lastrowid))
    return render_template("patient_form.html", patient=None)


@app.route("/patients/<int:pid>/edit", methods=["GET", "POST"])
@login_required
def patient_edit(pid):
    patient = get_patient(pid)
    if request.method == "POST":
        db = get_db()
        db.execute("""UPDATE patients SET name=?, age=?, gender=?, phone=?, address=?, blood_group=?, notes=?
                      WHERE id=?""", (*patient_fields(), pid))
        db.commit()
        flash("Patient updated.", "ok")
        return redirect(url_for("patient_detail", pid=pid))
    return render_template("patient_form.html", patient=patient)


@app.route("/patients/<int:pid>")
@login_required
def patient_detail(pid):
    db = get_db()
    return render_template(
        "patient_detail.html", p=get_patient(pid),
        appts=db.execute("""SELECT a.*, d.name AS doctor FROM appointments a JOIN doctors d ON d.id=a.doctor_id
                            WHERE a.patient_id=? ORDER BY a.appt_date DESC, a.appt_time DESC""", (pid,)).fetchall(),
        rx=db.execute("""SELECT r.*, d.name AS doctor FROM prescriptions r LEFT JOIN doctors d ON d.id=r.doctor_id
                         WHERE r.patient_id=? ORDER BY r.id DESC""", (pid,)).fetchall(),
        bills=db.execute("SELECT * FROM bills WHERE patient_id=? ORDER BY id DESC", (pid,)).fetchall(),
        doctors=db.execute("SELECT * FROM doctors ORDER BY name").fetchall())


@app.route("/patients/<int:pid>/delete", methods=["POST"])
@admin_required
def patient_delete(pid):
    db = get_db()
    db.execute("DELETE FROM patients WHERE id = ?", (pid,))
    db.commit()
    flash("Patient and all their records deleted.", "ok")
    return redirect(url_for("patients"))


# ---------- Doctors ----------
@app.route("/doctors", methods=["GET", "POST"])
@login_required
def doctors():
    db = get_db()
    if request.method == "POST":
        if session["role"] != "admin":
            flash("Only an admin can add doctors.", "error")
        else:
            db.execute("INSERT INTO doctors (name, specialization, phone) VALUES (?,?,?)",
                       (request.form["name"].strip(), request.form["specialization"].strip(), request.form["phone"].strip()))
            db.commit()
            flash("Doctor added.", "ok")
        return redirect(url_for("doctors"))
    rows = db.execute("""SELECT d.*, (SELECT COUNT(*) FROM appointments a WHERE a.doctor_id=d.id AND a.status='Scheduled') AS upcoming
                         FROM doctors d ORDER BY d.name""").fetchall()
    return render_template("doctors.html", doctors=rows)


@app.route("/doctors/<int:did>/delete", methods=["POST"])
@admin_required
def doctor_delete(did):
    db = get_db()
    db.execute("DELETE FROM doctors WHERE id = ?", (did,))
    db.commit()
    flash("Doctor removed.", "ok")
    return redirect(url_for("doctors"))


# ---------- Appointments ----------
@app.route("/appointments", methods=["GET", "POST"])
@login_required
def appointments():
    db = get_db()
    if request.method == "POST":
        f = request.form
        clash = db.execute("""SELECT 1 FROM appointments WHERE doctor_id=? AND appt_date=? AND appt_time=?
                              AND status != 'Cancelled'""", (f["doctor_id"], f["appt_date"], f["appt_time"])).fetchone()
        if clash:
            flash("That doctor is already booked at this date and time.", "error")
        else:
            db.execute("""INSERT INTO appointments (patient_id, doctor_id, appt_date, appt_time, reason)
                          VALUES (?,?,?,?,?)""", (f["patient_id"], f["doctor_id"], f["appt_date"], f["appt_time"], f.get("reason", "").strip()))
            db.commit()
            flash("Appointment booked.", "ok")
        return redirect(request.referrer or url_for("appointments"))
    status = request.args.get("status", "")
    sql = """SELECT a.*, p.name AS patient, d.name AS doctor FROM appointments a
             JOIN patients p ON p.id=a.patient_id JOIN doctors d ON d.id=a.doctor_id"""
    args = ()
    if status:
        sql += " WHERE a.status = ?"
        args = (status,)
    rows = db.execute(sql + " ORDER BY a.appt_date DESC, a.appt_time DESC", args).fetchall()
    return render_template("appointments.html", appts=rows, status=status,
                           patients=db.execute("SELECT id, name FROM patients ORDER BY name").fetchall(),
                           doctors=db.execute("SELECT id, name, specialization FROM doctors ORDER BY name").fetchall(),
                           today=date.today().isoformat())


@app.route("/appointments/<int:aid>/status", methods=["POST"])
@login_required
def appointment_status(aid):
    new = request.form["status"]
    if new not in ("Scheduled", "Completed", "Cancelled"):
        abort(400)
    db = get_db()
    db.execute("UPDATE appointments SET status = ? WHERE id = ?", (new, aid))
    db.commit()
    return redirect(request.referrer or url_for("appointments"))


@app.route("/appointments/<int:aid>/delete", methods=["POST"])
@login_required
def appointment_delete(aid):
    db = get_db()
    db.execute("DELETE FROM appointments WHERE id = ?", (aid,))
    db.commit()
    return redirect(request.referrer or url_for("appointments"))


# ---------- Prescriptions ----------
@app.route("/patients/<int:pid>/prescriptions", methods=["POST"])
@login_required
def prescription_add(pid):
    get_patient(pid)
    f = request.form
    db = get_db()
    db.execute("INSERT INTO prescriptions (patient_id, doctor_id, medicine, dosage, instructions) VALUES (?,?,?,?,?)",
               (pid, f.get("doctor_id") or None, f["medicine"].strip(), f["dosage"].strip(), f.get("instructions", "").strip()))
    db.commit()
    flash("Prescription added.", "ok")
    return redirect(url_for("patient_detail", pid=pid))


@app.route("/prescriptions/<int:rid>/delete", methods=["POST"])
@login_required
def prescription_delete(rid):
    db = get_db()
    db.execute("DELETE FROM prescriptions WHERE id = ?", (rid,))
    db.commit()
    return redirect(request.referrer or url_for("patients"))


# ---------- Billing ----------
@app.route("/billing", methods=["GET", "POST"])
@login_required
def billing():
    db = get_db()
    if request.method == "POST":
        try:
            amount = float(request.form["amount"])
            if amount <= 0:
                raise ValueError
        except ValueError:
            flash("Enter an amount greater than zero.", "error")
            return redirect(url_for("billing"))
        db.execute("INSERT INTO bills (patient_id, description, amount) VALUES (?,?,?)",
                   (request.form["patient_id"], request.form["description"].strip(), amount))
        db.commit()
        flash("Bill created.", "ok")
        return redirect(request.referrer or url_for("billing"))
    rows = db.execute("""SELECT b.*, p.name AS patient FROM bills b JOIN patients p ON p.id=b.patient_id
                         ORDER BY b.id DESC""").fetchall()
    return render_template("billing.html", bills=rows,
                           patients=db.execute("SELECT id, name FROM patients ORDER BY name").fetchall(),
                           unpaid=sum(b["amount"] for b in rows if b["status"] == "Unpaid"),
                           paid=sum(b["amount"] for b in rows if b["status"] == "Paid"))


@app.route("/billing/<int:bid>")
@login_required
def invoice(bid):
    bill = get_db().execute("""SELECT b.*, p.name AS patient, p.phone, p.address FROM bills b
                               JOIN patients p ON p.id=b.patient_id WHERE b.id=?""", (bid,)).fetchone()
    if bill is None:
        abort(404)
    return render_template("invoice.html", b=bill)


@app.route("/billing/<int:bid>/pay", methods=["POST"])
@login_required
def bill_pay(bid):
    db = get_db()
    db.execute("UPDATE bills SET status = 'Paid' WHERE id = ?", (bid,))
    db.commit()
    flash("Bill marked as paid.", "ok")
    return redirect(request.referrer or url_for("billing"))


@app.route("/billing/<int:bid>/delete", methods=["POST"])
@admin_required
def bill_delete(bid):
    db = get_db()
    db.execute("DELETE FROM bills WHERE id = ?", (bid,))
    db.commit()
    flash("Bill deleted.", "ok")
    return redirect(request.referrer or url_for("billing"))


@app.errorhandler(404)
def not_found(_e):
    return render_template("404.html"), 404


init_db()

if __name__ == "__main__":
    app.run(debug=True)
