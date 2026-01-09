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

# Initialize Session State Variables
if 'auth' not in st.session_state: st.session_state.auth = False
if 'user_name' not in st.session_state: st.session_state.user_name = ""
if 'enroll_id' not in st.session_state: st.session_state.enroll_id = ""
# Initializing the editor key is crucial
if 'editor' not in st.session_state: st.session_state.editor = "" 

try:
    API_KEY = st.secrets["GEMINI_API_KEY"]
    SENDER_EMAIL = st.secrets["SENDER_EMAIL"]
    SENDER_APP_PASSWORD = st.secrets["SENDER_APP_PASSWORD"]
    
    genai.configure(api_key=API_KEY)
    model = genai.GenerativeModel('gemini-2.5-flash')
except Exception as e:
    st.error("Missing credentials in .streamlit/secrets.toml.")
    st.stop()

# --- 2. DATABASE ARCHITECTURE ---
def init_db():
    conn = sqlite3.connect('advocate_elite.db')
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT, enroll_id TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS hearings (id INTEGER PRIMARY KEY, username TEXT, case_name TEXT, category TEXT, hearing_date TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS invoices (id INTEGER PRIMARY KEY, username TEXT, client_name TEXT, amount REAL, date TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS drafts (id INTEGER PRIMARY KEY, username TEXT, category TEXT, doc_type TEXT, content TEXT, date TEXT)')
    conn.commit()
    conn.close()

def make_hashes(password): return hashlib.sha256(str.encode(password)).hexdigest()
def check_hashes(password, hashed_text): return make_hashes(password) == hashed_text
init_db()

# --- 3. HELPER FUNCTIONS ---
def safe_unicode(text):
    replacements = {"₹": "Rs.", "—": "-", "‘": "'", "’": "'", "“": '"', "”": '"', "…": "...", "–": "-"}
    for k, v in replacements.items(): text = text.replace(k, v)
    return text.encode('latin-1', 'replace').decode('latin-1')

def generate_pdf(content, title="Legal_Document"):
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

# --- 4. GLOBAL STYLING ---
BG_URL = "https://images.unsplash.com/photo-1589829545856-d10d557cf95f?q=80&w=1920"
st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700&family=Montserrat:wght@400;700&display=swap');
    .stApp {{ background: linear-gradient(rgba(0,0,0,0.9), rgba(0,0,0,0.9)), url('{BG_URL}'); background-size: cover; background-attachment: fixed; }}
    .title-text {{ color: #D4AF37; font-family: 'Playfair Display', serif; font-size: 55px; font-weight: bold; text-align: center; margin-bottom: 0px; }}
    .glass-card {{ background: rgba(255, 255, 255, 0.05); backdrop-filter: blur(15px); border: 1px solid #D4AF37; padding: 25px; border-radius: 15px; color: white; margin-bottom: 20px; }}
    .section-header {{ color: #D4AF37 !important; font-family: 'Playfair Display', serif; font-size: 24px; font-weight: bold; border-bottom: 1px solid #D4AF37; margin-bottom: 15px; }}
    .ai-analysis-text {{ color: #00FFCC !important; font-family: 'Montserrat', sans-serif; font-size: 20px; font-weight: bold; margin-bottom: 10px; }}
    .citation-answer {{ color: #BB86FC !important; background-color: rgba(187, 134, 252, 0.1); border-left: 4px solid #BB86FC; padding: 15px; border-radius: 5px; font-family: 'Montserrat', sans-serif; line-height: 1.6; }}
    label {{ color: #D4AF37 !important; font-family: 'Montserrat'; font-weight: bold; }}
    div[data-testid="stRadio"] div[role="radiogroup"] > label:nth-of-type(1) p {{ color: #00BFFF !important; font-weight: bold; }}
    div[data-testid="stRadio"] div[role="radiogroup"] > label:nth-of-type(2) p {{ color: #FF4B4B !important; font-weight: bold; }}
    </style>
    """, unsafe_allow_html=True)

st.markdown('<p class="title-text">COOL FINDS</p>', unsafe_allow_html=True)
st.markdown("<p style='text-align:center; color:#D4AF37; font-family:Montserrat; font-size:0.9rem; letter-spacing: 4px;'>LEGAL INTELLIGENCE HUB</p><hr>", unsafe_allow_html=True)

# --- 5. AUTHENTICATION ---
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
                        st.session_state.auth = True
                        st.session_state.user_name = u
                        st.session_state.enroll_id = res[1]
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
    # --- DASHBOARD SIDEBAR ---
    with st.sidebar:
        st.markdown(f'<p style="color:#D4AF37; font-size:20px;">👤 Adv. {st.session_state.user_name}</p>', unsafe_allow_html=True)
        st.write("---")
        st.markdown('<p style="color:#D4AF37;">📅 Docket Entry</p>', unsafe_allow_html=True)
        case_in = st.text_input("Case Name")
        date_in = st.date_input("Hearing Date")
        if st.button("Save to Docket", use_container_width=True):
            conn = sqlite3.connect('advocate_elite.db'); c = conn.cursor()
            c.execute('INSERT INTO hearings (username, case_name, category, hearing_date) VALUES (?,?,?,?)', 
                      (st.session_state.user_name, case_in, "General", str(date_in)))
            conn.commit(); conn.close(); st.toast("Saved!")

        st.markdown('<p style="color:#00FFCC; margin-top:20px;">📌 Upcoming Matters</p>', unsafe_allow_html=True)
        conn = sqlite3.connect('advocate_elite.db'); c = conn.cursor()
        c.execute('SELECT case_name, hearing_date FROM hearings WHERE username=? ORDER BY hearing_date ASC LIMIT 5', (st.session_state.user_name,))
        docket_data = c.fetchall(); conn.close()
        for h in docket_data:
            st.markdown(f"<span style='color:white;'>📅 {h[1]} | {h[0]}</span>", unsafe_allow_html=True)
        
        st.write("---")
        if st.button("🚪 Logout", use_container_width=True): 
            st.session_state.auth = False
            st.rerun()

    tab1, tab2, tab3, tab4 = st.tabs(["🖋️ Drafting Room", "🔍 Evidence Scanner", "📚 AI Researcher", "💰 Billing"])

    # --- TAB 1: DRAFTING ROOM ---
    with tab1:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.markdown('<p class="section-header">🖋️ Classified Drafting Room</p>', unsafe_allow_html=True)
        c1, c2 = st.columns([2, 1])
        with c1:
            draft_cat = st.radio("Matter Category", ["Civil", "Criminal"], horizontal=True, key="draft_cat")
            
            if draft_cat == "Civil":
                dtype = st.selectbox("Document Type", ["Property Notice", "Rent Agreement", "Divorce Petition", "Civil Suit"])
                court_header = "IN THE COURT OF THE CIVIL JUDGE, SENIOR DIVISION"
            else:
                dtype = st.selectbox("Document Type", ["Regular Bail Application", "Anticipatory Bail", "Criminal FIR", "Section 138 Notice"])
                court_header = "IN THE COURT OF THE HON'BLE SESSIONS JUDGE"
            
            # --- FIX: Updated Load Template Logic ---
            if st.button("✨ Load Template"):
                new_template = f"""{court_header}
Date: {datetime.date.today()}
Advocate: {st.session_state.user_name}
Enrollment: {st.session_state.enroll_id}

SUBJECT: {dtype.upper()} IN THE MATTER OF {draft_cat.upper()} LITIGATION

TO,
[RECIPIENT NAME/OFFICE]
[ADDRESS LINE 1]

Sir/Madam,
Under the instructions from my client, I hereby serve you with the following {dtype}:

1. That my client is...
2. That the cause of action arose on...
3. Therefore, you are hereby requested to...

Regards,
Adv. {st.session_state.user_name}
({st.session_state.enroll_id})"""
                # This directly updates the widget state
                st.session_state.editor = new_template
                st.rerun()
            
            # Use the key as the direct source of truth
            text = st.text_area("Live Editor", height=400, key="editor")
            
            if st.button("💾 Save Draft to DB"):
                conn = sqlite3.connect('advocate_elite.db'); c = conn.cursor()
                c.execute('INSERT INTO drafts (username, category, doc_type, content, date) VALUES (?,?,?,?,?)', 
                          (st.session_state.user_name, draft_cat, dtype, text, str(datetime.date.today())))
                conn.commit(); conn.close(); st.success("Draft Saved!")

        with c2:
            st.markdown('<p class="ai-analysis-text">📋 AI Analysis</p>', unsafe_allow_html=True)
            if st.button("Predict Probability", use_container_width=True):
                with st.spinner("Analyzing..."):
                    res = model.generate_content(f"Predict legal success probability for this Indian {draft_cat} draft: {text}")
                    st.warning(res.text)
            st.write("---")
            pdf = generate_pdf(text, dtype)
            st.download_button("📥 Download PDF", pdf, f"{dtype}.pdf", mime="application/pdf", use_container_width=True)
            dest = st.text_input("Recipient Email")
            if st.button("📧 Send Mail", type="primary", use_container_width=True):
                if dest:
                    ok, msg = send_real_email_with_attachment(dest, f"Legal Doc: {dtype}", "Attached is your document.", pdf, dtype)
                    if ok: st.success("Sent Successfully!")
                    else: st.error(msg)
        st.markdown('</div>', unsafe_allow_html=True)

    # --- TAB 2, 3, 4 ---
    with tab2:
        st.markdown('<div class="glass-card">🔍 AI Document OCR</div>', unsafe_allow_html=True)
        up = st.file_uploader("Upload Image", type=['jpg','png','jpeg'])
        if up and st.button("Scan"):
            res = model.generate_content(["Extract text and summarize:", Image.open(up)])
            st.info(res.text)

    with tab3:
        st.markdown('<div class="glass-card">📚 Legal Research</div>', unsafe_allow_html=True)
        res_cat = st.radio("Search Scope", ["Civil", "Criminal"], horizontal=True, key="res_cat")
        q = st.text_input(f"Enter {res_cat} Query")
        if st.button("Find Citations"):
            with st.spinner("Searching..."):
                res = model.generate_content(f"Provide 3 SC citations for: {q} in {res_cat} law.")
                st.markdown(f'<div class="citation-answer">{res.text}</div>', unsafe_allow_html=True)

    with tab4:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.markdown('<p class="section-header">💰 Billing Records</p>', unsafe_allow_html=True)
        clin = st.text_input("Client Name")
        amt = st.number_input("Amount (Rs.)", min_value=0.0)
        if st.button("Save Invoice"):
            conn = sqlite3.connect('advocate_elite.db'); c = conn.cursor()
            c.execute('INSERT INTO invoices (username, client_name, amount, date) VALUES (?,?,?,?)', (st.session_state.user_name, clin, amt, str(datetime.date.today())))
            conn.commit(); conn.close(); st.success("Invoice Saved!")
            
            invoice_body = f"OFFICIAL INVOICE\nAdvocate: {st.session_state.user_name}\nEnrollment: {st.session_state.enroll_id}\nClient: {clin}\nAmount: Rs. {amt}\nDate: {datetime.date.today()}"
            inv_p = generate_pdf(invoice_body, "Invoice")
            st.download_button("Download PDF", inv_p, "invoice.pdf")
        st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<p style="text-align:center; color:#555; font-size:12px;">DISCLAIMER: AI Assistant. Verify citations manually.</p>', unsafe_allow_html=True)