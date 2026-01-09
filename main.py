import streamlit as st
import google.generativeai as genai
import smtplib
import ssl
import datetime
import urllib.parse
import sqlite3
import hashlib
import re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from fpdf import FPDF
from PIL import Image

# --- 1. SETTINGS & SECRETS SETUP ---
st.set_page_config(page_title="COOL FINDS | ADVOCATE ELITE", layout="wide")

try:
    API_KEY = st.secrets["GEMINI_API_KEY"]
    SENDER_EMAIL = st.secrets["SENDER_EMAIL"]
    SENDER_APP_PASSWORD = st.secrets["SENDER_APP_PASSWORD"]
    
    genai.configure(api_key=API_KEY)
    model = genai.GenerativeModel('gemini-2.5-flash')
except Exception as e:
    st.error("Missing credentials in .streamlit/secrets.toml. Please ensure GEMINI_API_KEY, SENDER_EMAIL, and SENDER_APP_PASSWORD are set.")
    st.stop()

# --- 2. DATABASE ARCHITECTURE (The "Memory" System) ---
def init_db():
    conn = sqlite3.connect('advocate_elite.db')
    c = conn.cursor()
    # Table for Users
    c.execute('CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT, enroll_id TEXT)')
    # Table for Hearings (Docket)
    c.execute('CREATE TABLE IF NOT EXISTS hearings (id INTEGER PRIMARY KEY, username TEXT, case_name TEXT, hearing_date TEXT)')
    # Table for Invoices
    c.execute('CREATE TABLE IF NOT EXISTS invoices (id INTEGER PRIMARY KEY, username TEXT, client_name TEXT, amount REAL, date TEXT)')
    # Table for Saved Drafts
    c.execute('CREATE TABLE IF NOT EXISTS drafts (id INTEGER PRIMARY KEY, username TEXT, doc_type TEXT, content TEXT, date TEXT)')
    conn.commit()
    conn.close()

def make_hashes(password): return hashlib.sha256(str.encode(password)).hexdigest()
def check_hashes(password, hashed_text): return make_hashes(password) == hashed_text
init_db()

# --- 3. HELPER FUNCTIONS ---

def safe_unicode(text):
    """Sanitize text for FPDF"""
    replacements = {"₹": "Rs.", "—": "-", "‘": "'", "’": "'", "“": '"', "”": '"', "…": "...", "–": "-"}
    for k, v in replacements.items(): text = text.replace(k, v)
    return text.encode('latin-1', 'replace').decode('latin-1')

def generate_pdf(content, title="Legal_Document"):
    """Generates PDF and fixes the bytearray/Python 3.14 error"""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(200, 10, txt=title.upper(), ln=True, align='C')
    pdf.ln(10)
    pdf.set_font("Arial", size=11)
    clean_text = safe_unicode(content)
    pdf.multi_cell(0, 10, txt=clean_text)
    return bytes(pdf.output())

def send_real_email_with_attachment(receiver_email, subject, body, pdf_data, filename):
    """Professional Emailer with PDF Attachment"""
    message = MIMEMultipart()
    message["From"] = SENDER_EMAIL
    message["To"] = receiver_email
    message["Subject"] = subject
    message.attach(MIMEText(body, "plain"))
    try:
        attachment = MIMEApplication(pdf_data, _subtype="pdf")
        attachment.add_header('Content-Disposition', 'attachment', filename=f"{filename}.pdf")
        message.attach(attachment)
    except Exception: return False, "Attachment Error"

    context = ssl.create_default_context()
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
            server.login(SENDER_EMAIL, SENDER_APP_PASSWORD)
            server.sendmail(SENDER_EMAIL, receiver_email, message.as_string())
        return True, "Success"
    except Exception as e: return False, str(e)

# --- 4. GLOBAL STYLING (PRESERVED) ---
BG_URL = "https://images.unsplash.com/photo-1589829545856-d10d557cf95f?q=80&w=1920"
st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700&family=Montserrat:wght@400;700&display=swap');
    .stApp {{ background: linear-gradient(rgba(0,0,0,0.9), rgba(0,0,0,0.9)), url('{BG_URL}'); background-size: cover; background-attachment: fixed; }}
    .title-text {{ color: #D4AF37; font-family: 'Playfair Display', serif; font-size: 55px; font-weight: bold; text-align: center; margin-bottom: 0px; }}
    .glass-card {{ background: rgba(255, 255, 255, 0.05); backdrop-filter: blur(15px); border: 1px solid #D4AF37; padding: 25px; border-radius: 15px; color: white; margin-bottom: 20px; }}
    .section-header {{ color: #D4AF37 !important; font-family: 'Playfair Display', serif; font-size: 24px; font-weight: bold; border-bottom: 1px solid #D4AF37; margin-bottom: 15px; }}
    .ai-answer {{ color: #BB86FC !important; background-color: rgba(187, 134, 252, 0.1); border-left: 4px solid #BB86FC; padding: 15px; border-radius: 5px; font-family: 'Montserrat', sans-serif; }}
    label {{ color: #D4AF37 !important; font-family: 'Montserrat'; font-weight: bold; }}
    </style>
    """, unsafe_allow_html=True)

st.markdown('<p class="title-text">COOL FINDS</p>', unsafe_allow_html=True)
st.markdown("<p style='text-align:center; color:#D4AF37; font-family:Montserrat; font-size:0.9rem; letter-spacing: 4px;'>LEGAL INTELLIGENCE HUB</p><hr>", unsafe_allow_html=True)

# --- 5. NAVIGATION LOGIC ---
if 'auth' not in st.session_state: st.session_state.auth = False

if not st.session_state.auth:
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        tab_l, tab_r = st.tabs(["🔒 Login", "📝 Register"])
        with tab_l:
            with st.form("l"):
                u = st.text_input("Username")
                p = st.text_input("Password", type="password")
                if st.form_submit_button("Access Portal", use_container_width=True):
                    conn = sqlite3.connect('advocate_elite.db'); c = conn.cursor()
                    c.execute('SELECT password, enroll_id FROM users WHERE username=?', (u,))
                    res = c.fetchone(); conn.close()
                    if res and check_hashes(p, res[0]):
                        st.session_state.auth, st.session_state.user, st.session_state.enroll = True, u, res[1]
                        st.rerun()
                    else: st.error("Invalid Credentials")
        with tab_r:
            with st.form("r"):
                nu = st.text_input("New Username")
                ne = st.text_input("Bar ID")
                np = st.text_input("New Password", type="password")
                if st.form_submit_button("Sign Up"):
                    conn = sqlite3.connect('advocate_elite.db'); c = conn.cursor()
                    try: 
                        c.execute('INSERT INTO users VALUES (?,?,?)', (nu, make_hashes(np), ne))
                        conn.commit(); st.success("Created! Please Login.")
                    except: st.error("Username taken.")
                    conn.close()
        st.markdown('</div>', unsafe_allow_html=True)

else:
    # --- PAGE 2: DASHBOARD ---
    with st.sidebar:
        st.markdown(f'<p style="color:#D4AF37; font-size:20px;">👤 Adv. {st.session_state.user}</p>', unsafe_allow_html=True)
        st.write("---")
        st.markdown('<p style="color:#D4AF37;">📅 Add Hearing</p>', unsafe_allow_html=True)
        case_in = st.text_input("Case Name")
        date_in = st.date_input("Date")
        if st.button("Save to Docket"):
            conn = sqlite3.connect('advocate_elite.db'); c = conn.cursor()
            c.execute('INSERT INTO hearings (username, case_name, hearing_date) VALUES (?,?,?)', (st.session_state.user, case_in, str(date_in)))
            conn.commit(); conn.close(); st.toast("Saved!")

        st.markdown('<p style="color:#00FFCC; margin-top:20px;">📌 Your Docket</p>', unsafe_allow_html=True)
        conn = sqlite3.connect('advocate_elite.db'); c = conn.cursor()
        c.execute('SELECT case_name, hearing_date FROM hearings WHERE username=? ORDER BY hearing_date ASC LIMIT 5', (st.session_state.user,))
        docket_data = c.fetchall(); conn.close()
        for h in docket_data: st.caption(f"📅 {h[1]} | {h[0]}")
        
        if st.button("🚪 Logout"): st.session_state.auth = False; st.rerun()

    tab1, tab2, tab3, tab4 = st.tabs(["🖋️ Drafting", "🔍 Scanner", "📚 AI Researcher", "💰 Billing"])

    with tab1:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.markdown('<p class="section-header">🖋️ Professional Drafting Room</p>', unsafe_allow_html=True)
        c1, c2 = st.columns([2, 1])
        with c1:
            dtype = st.selectbox("Doc Type", ["Bail Application", "Legal Notice", "Rent Agreement"])
            text = st.text_area("Live Editor", height=300, key="editor")
            if st.button("💾 Save Draft to DB"):
                conn = sqlite3.connect('advocate_elite.db'); c = conn.cursor()
                c.execute('INSERT INTO drafts (username, doc_type, content, date) VALUES (?,?,?,?)', 
                          (st.session_state.user, dtype, text, str(datetime.date.today())))
                conn.commit(); conn.close(); st.success("Draft Saved Permanently!")
        with c2:
            st.markdown('<p style="color:#00FFCC;">Actions</p>', unsafe_allow_html=True)
            pdf = generate_pdf(text, dtype)
            st.download_button("📥 Download PDF", pdf, f"{dtype}.pdf", mime="application/pdf")
            dest = st.text_input("Send to Client (Email)")
            if st.button("📧 Send Mail"):
                ok, msg = send_real_email_with_attachment(dest, f"Legal Doc: {dtype}", "Please find the attached document.", pdf, dtype)
                if ok: st.success("Sent Successfully!")
                else: st.error(msg)
        st.markdown('</div>', unsafe_allow_html=True)

    with tab2:
        st.markdown('<div class="glass-card">🔍 AI Document OCR</div>', unsafe_allow_html=True)
        up = st.file_uploader("Upload Image", type=['jpg','png','jpeg'])
        if up and st.button("Extract"):
            res = model.generate_content(["Extract text from this legal image:", Image.open(up)])
            st.info(res.text)

    with tab3:
        st.markdown('<div class="glass-card">📚 Case Law Research</div>', unsafe_allow_html=True)
        q = st.text_input("Query")
        if st.button("Find Precedents"):
            res = model.generate_content(f"List 3 SC citations for: {q}")
            st.markdown(f'<div class="ai-answer">{res.text}</div>', unsafe_allow_html=True)

    with tab4:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.markdown('<p class="section-header">💰 Professional Invoicing</p>', unsafe_allow_html=True)
        clin = st.text_input("Client Name")
        amt = st.number_input("Amount (Rs.)", min_value=0.0)
        if st.button("Generate & Save Invoice"):
            conn = sqlite3.connect('advocate_elite.db'); c = conn.cursor()
            c.execute('INSERT INTO invoices (username, client_name, amount, date) VALUES (?,?,?,?)', (st.session_state.user, clin, amt, str(datetime.date.today())))
            conn.commit(); conn.close()
            st.success("Invoice Saved to Record!")
            inv_p = generate_pdf(f"INVOICE\nClient: {clin}\nAmount: Rs.{amt}", "Invoice")
            st.download_button("Download PDF", inv_p, "invoice.pdf")
        
        st.markdown('<p style="color:#D4AF37; margin-top:20px;">📜 Billing History</p>', unsafe_allow_html=True)
        conn = sqlite3.connect('advocate_elite.db'); c = conn.cursor()
        c.execute('SELECT client_name, amount, date FROM invoices WHERE username=?', (st.session_state.user,))
        inv_data = c.fetchall(); conn.close()
        for i in inv_data: st.caption(f"👤 {i[0]} | Rs.{i[1]} | 📅 {i[2]}")
        st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<p style="text-align:center; color:#555; font-size:12px;">DISCLAIMER: This is an AI assistant. Verify all citations.</p>', unsafe_allow_html=True)