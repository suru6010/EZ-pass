from flask import Flask, request, render_template, redirect, url_for, flash, session
from random import randint
from datetime import datetime, timedelta
from twilio.rest import Client
import mysql.connector

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Required for session and flash

# Database connection

db = mysql.connector.connect(
    host="localhost",
    user="root",
    database="ezpass"
)
cursor = db.cursor()

# Twilio Configuration
TWILIO_ACCOUNT_SID = "!ASjiovewr9r3280qHUQ12E1U[DN"
TWILIO_AUTH_TOKEN = "!ASjiovewr9r3280qHUQ12E1U[DN"
TWILIO_PHONE_NUMBER = "+12317296435"

# ----------------------- HOME AND STUDENT ROUTES ------------------------

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/student')
def student_home():
    return render_template('index.html')

@app.route('/signup')
def signup():
    return render_template('signup.html')

@app.route('/submit_signup', methods=['POST'])
def handle_student_signup():
    email = request.form.get("email")
    password = request.form.get("password")
    confirm_password = request.form.get("confirm_password")

    if password != confirm_password:
        return "Passwords do not match!"

    cursor.execute("SELECT * FROM students WHERE email = %s", (email,))
    if cursor.fetchone():
        return "Email already registered."

    cursor.execute("INSERT INTO students (email, password) VALUES (%s, %s)", (email, password))
    db.commit()
    return redirect(url_for('login'))

@app.route('/login')
def login():
    return render_template('login.html')

@app.route('/submit_login', methods=['POST'])
def handle_student_login():
    email = request.form.get("email")
    password = request.form.get("password")

    cursor.execute("SELECT * FROM students WHERE email = %s AND password = %s", (email, password))
    student = cursor.fetchone()

    if student:
        session['email'] = email
        return redirect(url_for('student_dashboard'))
    else:
        return "Invalid email or password."

@app.route('/student_dashboard')
def student_dashboard():
    email = session.get('email')
    if not email:
        return redirect(url_for('login'))

    cursor.execute("SELECT * FROM student_details WHERE email = %s", (email,))
    student = cursor.fetchone()
    if not student:
        return "Student not found!"

    name, roll, course, dept, room, parent_number, email = student[1:]

    cursor.execute("SELECT date, purpose FROM homepasses WHERE email = %s ORDER BY date DESC", (email,))
    homepasses = cursor.fetchall()

    cursor.execute("SELECT date, purpose FROM outpasses WHERE email = %s ORDER BY date DESC", (email,))
    outpasses = cursor.fetchall()

    return render_template('student_dashboard.html', name=name, roll_number=roll,
                           course=course, department=dept, room_number=room,
                           parent_phone_number=parent_number, email=email,
                           homepasses=homepasses, outpasses=outpasses)

@app.route('/apply_homepass')
def apply_homepass():
    email = session.get('email')
    return render_template('homepass_form.html', email=email)

@app.route('/submit_homepass', methods=['POST'])
def submit_homepass():
    email = request.form.get('email')
    date = request.form.get('date')
    purpose = request.form.get('purpose')

    cursor.execute("SELECT parent_phone_number, name FROM student_details WHERE email = %s", (email,))
    result = cursor.fetchone()

    if not result:
        return "Student not found!"

    parent_number, name = result

    otp = randint(100000, 999999)
    expiry = datetime.now() + timedelta(minutes=5)
    cursor.execute("INSERT INTO otp_verification (email, otp, expires_at) VALUES (%s, %s, %s)",
                   (email, otp, expiry))
    db.commit()

    # Send OTP via Twilio
    try:
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        client.messages.create(
            body=f"Hello! OTP for approving {name}'s homepass is {otp}. Valid for 5 minutes.",
            from_=TWILIO_PHONE_NUMBER,
            to=parent_number
        )
    except Exception as e:
        return f"Failed to send OTP: {str(e)}"

    return render_template("verify_otp.html", email=email, date=date, purpose=purpose)

@app.route('/verify_otp', methods=['POST'])
def verify_otp():
    email = request.form.get("email")
    otp = request.form.get("otp")
    date = request.form.get("date")
    purpose = request.form.get("purpose")

    cursor.execute("SELECT otp, expires_at FROM otp_verification WHERE email = %s ORDER BY id DESC LIMIT 1", (email,))
    record = cursor.fetchone()

    if not record:
        return "No OTP found."

    stored_otp, expires_at = record
    if otp == str(stored_otp) and datetime.now() < expires_at:
        cursor.execute("INSERT INTO passlog_ss2 (email, date, purpose, pass_type) VALUES (%s, %s, %s, 'Homepass')",
                       (email, date, purpose))
        cursor.execute("INSERT INTO passlog_ss1 (email, date, purpose, pass_type) VALUES (%s, %s, %s, 'Homepass')",
                       (email, date, purpose))
        cursor.execute("INSERT INTO homepasses (email, date, purpose) VALUES (%s, %s, %s)", (email, date, purpose))
        db.commit()
        return "Homepass generated successfully!"
    else:
        return "Invalid or expired OTP."

@app.route('/apply_outpass')
def apply_outpass():
    email = session.get('email')
    return render_template('outpass_form.html', email=email)

@app.route('/submit_outpass', methods=['POST'])
def submit_outpass():
    email = request.form.get("email")
    date = request.form.get("date")
    purpose = request.form.get("purpose")

    cursor.execute("INSERT INTO outpasses (email, date, purpose) VALUES (%s, %s, %s)", (email, date, purpose))
    cursor.execute("INSERT INTO passlog_ss1 (email, date, purpose, pass_type) VALUES (%s, %s, %s, 'Outpass')",
                   (email, date, purpose))
    cursor.execute("INSERT INTO passlog_ss2 (email, date, purpose, pass_type) VALUES (%s, %s, %s, 'Outpass')",
                   (email, date, purpose))
    db.commit()
    return "Outpass submitted successfully!"

# Route for the ss1 Login page
@app.route("/security1")
def security1():
    return render_template("ss1login.html")

@app.route('/submit_security1_login', methods=['POST'])
def submit_security1_login():
    email = request.form.get("email")
    password = request.form.get("password")

    cursor.execute(
        "SELECT * FROM security WHERE security_email = %s AND security_password = %s",
        (email, password)
    )
    user = cursor.fetchone()

    if user:
        return redirect(url_for('security1_dashboard', email=email))
    else:
        return "Invalid email or password!"

# Route for the ss2 Login page
@app.route("/security2")
def security2():
    return render_template("ss2login.html")

@app.route("/security1_dashboard", methods=["GET", "POST"])
def security1_dashboard():
    selected_date = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))

    if request.method == "POST":
        for key in request.form:
            if key.startswith("out_"):
                pass_id = key.split("_")[1]
                if pass_id:
                    cursor.execute("UPDATE passlog_ss1 SET out_status = 1, out_time = %s WHERE id = %s",
                                   (datetime.now(), pass_id))
                    db.commit()

            elif key.startswith("in_"):
                pass_id = key.split("_")[1]
                if pass_id:
                    cursor.execute("UPDATE passlog_ss1 SET in_status = 1, in_time = %s WHERE id = %s",
                                   (datetime.now(), pass_id))
                    db.commit()

        return redirect(f"/security1_dashboard?date={selected_date}")

    # Fetching from passlog_ss1 and joining student_details for name and roll
    cursor.execute("""
        SELECT p.id, s.name, s.roll_number, p.purpose, p.pass_type, p.out_status, p.out_time, p.in_status, p.in_time
        FROM passlog_ss1 p
        JOIN student_details s ON p.email = s.email
        WHERE p.date = %s
    """, (selected_date,))
    
    rows = cursor.fetchall()

    passes = []
    for row in rows:
     if row[0] is not None:  # Ensure 'name' or some critical field isn't empty
        passes.append({
            "id": row[0],
            "name": row[1],
            "roll": row[2],
            "pass_type": row[3],
            "purpose": row[4],
            "out_status": row[5],
            "out_time": row[6],
            "in_status": row[7],
            "in_time": row[8]
        })

    return render_template("passlog_ss1.html", passes=passes, date=selected_date)

@app.route('/submit_security2_login', methods=['POST'])
def submit_security2_login():
    email = request.form.get("email")
    password = request.form.get("password")

    cursor.execute(
        "SELECT * FROM security WHERE security_email = %s AND security_password = %s",
        (email, password)
    )
    user = cursor.fetchone()

    if user:
        return redirect(url_for('security2_dashboard', email=email))
    else:
        return "Invalid email or password!"

@app.route("/security2_dashboard", methods=["GET", "POST"])
def security2_dashboard():
    selected_date = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))

    if request.method == "POST":
        for key in request.form:
            if key.startswith("out_"):
                pass_id = int(key.split("_")[1])
                cursor.execute("UPDATE passlog_ss2 SET out_status=1, out_time=%s WHERE id=%s",
                               (datetime.now(), pass_id))
                db.commit()

            elif key.startswith("in_"):
                pass_id = int(key.split("_")[1])
                cursor.execute("UPDATE passlog_ss2 SET in_status=1, in_time=%s WHERE id=%s",
                               (datetime.now(), pass_id))
                db.commit()

        return redirect(f"/security2_dashboard?date={selected_date}")

    # Fetching joined data
    cursor.execute("""
        SELECT p.id, s.name, s.roll_number, p.pass_type, p.purpose,
               p.out_status, p.out_time, p.in_status, p.in_time
        FROM passlog_ss2 p
        JOIN student_details s ON p.email = s.email
        WHERE p.date = %s
    """, (selected_date,))

    rows = cursor.fetchall()

    passes = []
    for row in rows:
        passes.append({
            "id": row[0],
            "name": row[1],
            "roll": row[2],
            "pass_type": row[3],
            "purpose": row[4],
            "out_status": row[5],
            "out_time": row[6],
            "in_status": row[7],
            "in_time": row[8]
        })

    return render_template("passlog_ss2.html", passes=passes, date=selected_date)

# Route for the warden Login page
@app.route("/warden")
def warden():
    return render_template("wardenlogin.html")

@app.route('/submit_warden_login', methods=['POST'])
def submit_warden_login():
    email = request.form.get("email")
    password = request.form.get("password")

    cursor.execute(
        "SELECT * FROM security WHERE security_email = %s AND security_password = %s",
        (email, password)
    )
    user = cursor.fetchone()

    if user:
        return redirect(url_for('warden_dashboard', email=email))
    else:
        return "Invalid email or password!"

@app.route("/warden_dashboard")
def warden_dashboard():
    cursor.execute("""
        SELECT s.name, s.roll_number, s.room_number, p.pass_type, p.purpose, p.out_time
        FROM passlog_ss2 p
        JOIN student_details s ON p.email = s.email
        WHERE p.out_status = 1 AND p.in_status = 0
        ORDER BY s.room_number
    """)
    rows = cursor.fetchall()

    students = []
    for row in rows:
        students.append({
            "name": row[0],
            "roll": row[1],
            "room": row[2],
            "pass_type": row[3],
            "purpose": row[4],
            "out_time": row[5]
        })

    return render_template("warden_dashboard_ss2.html", students=students)

if __name__ == "__main__":
    app.run(debug=True)



