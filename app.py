from flask import Flask, render_template, request, redirect, url_for, session, send_file
from werkzeug.utils import secure_filename
from PyPDF2 import PdfReader
import sqlite3
import os
import csv
from io import StringIO

app = Flask(__name__)
app.secret_key = 'secret'
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# DB setup
def init_db():
    with sqlite3.connect('database.db') as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS scans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            resume_text TEXT,
            job_desc TEXT,
            score INTEGER
        )''')

# Text similarity (simple word overlap)
def calculate_score(resume_text, job_desc):
    resume_words = set(resume_text.lower().split())
    job_words = set(job_desc.lower().split())
    if not job_words:
        return 0
    return int(100 * len(resume_words & job_words) / len(job_words))

# Extract text from PDF
def extract_text_from_pdf(pdf_path):
    text = ""
    reader = PdfReader(pdf_path)
    for page in reader.pages:
        text += page.extract_text()
    return text

# Routes
@app.route('/landing')
def landing():
    return render_template('landing.html')

@app.route('/')
def index():
    return redirect('/landing')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form['username'] == 'admin' and request.form['password'] == 'admin':
            session['user'] = request.form['username']
            return redirect('/home')
        return "Invalid credentials"
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect('/login')

@app.route('/home')
def home():
    if 'user' not in session:
        return redirect('/login')
    return render_template('index.html')

@app.route('/scan', methods=['POST'])
def scan():
    if 'user' not in session:
        return redirect('/login')
    
    resume = request.files['resume']
    job_desc = request.form['job_desc']
    filename = secure_filename(resume.filename)
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    resume.save(filepath)

    resume_text = extract_text_from_pdf(filepath)
    score = calculate_score(resume_text, job_desc)

    # Save to DB
    with sqlite3.connect('database.db') as conn:
        conn.execute("INSERT INTO scans (username, resume_text, job_desc, score) VALUES (?, ?, ?, ?)",
                     (session['user'], resume_text, job_desc, score))

    return render_template('result.html', score=score)

@app.route('/history')
def history():
    if 'user' not in session:
        return redirect('/login')
    with sqlite3.connect('database.db') as conn:
        cursor = conn.execute("SELECT id, resume_text, job_desc, score FROM scans WHERE username=?", (session['user'],))
        records = cursor.fetchall()
    return render_template('history.html', records=records)

@app.route('/export')
def export():
    if 'user' not in session:
        return redirect('/login')

    with sqlite3.connect('database.db') as conn:
        cursor = conn.execute("SELECT id, resume_text, job_desc, score FROM scans WHERE username=?", (session['user'],))
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(['ID', 'Resume Snippet', 'Job Description', 'Score'])
        for row in cursor.fetchall():
            writer.writerow([row[0], row[1][:50], row[2][:50], row[3]])

    output.seek(0)
    return send_file(
        output,
        mimetype='text/csv',
        download_name='scan_history.csv',
        as_attachment=True
    )

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5006)
