import streamlit as st
import sqlite3
import bcrypt
import os
import fitz  # PyMuPDF to convert PDF pages to images
from database import init_db, get_connection

init_db()

st.set_page_config(page_title="Training LMS Portal", layout="wide", page_icon="🎓")

# --- Content Protection CSS (Deterrent) ---
PROTECTION_CSS = """
<style>
    /* Disable text selection */
    body, [class*="st-"] {
        -webkit-user-select: none !important;
        -moz-user-select: none !important;
        -ms-user-select: none !important;
        user-select: none !important;
    }
    /* Hide Streamlit default hamburger menu & footer */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
</style>
<script>
    // Disable right-click
    document.addEventListener('contextmenu', event => event.preventDefault());
</script>
"""
st.markdown(PROTECTION_CSS, unsafe_allow_html=True)

# --- Authentication Helpers ---
def verify_password(plain, hashed):
    return bcrypt.checkpw(plain.encode('utf-8'), hashed.encode('utf-8'))

def hash_password(plain):
    return bcrypt.hashpw(plain.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

if "user" not in st.session_state:
    st.session_state.user = None

# --- Login View ---
if not st.session_state.user:
    st.title("🎓 Student Learning Portal")
    st.subheader("Login to Access Course Materials")
    
    with st.form("login_form"):
        username = st.text_input("Username").strip()
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Login")
        
        if submit:
            conn = get_connection()
            c = conn.cursor()
            c.execute("SELECT id, username, password_hash, full_name, role FROM users WHERE username = ?", (username,))
            user_record = c.fetchone()
            conn.close()
            
            if user_record and verify_password(password, user_record[2]):
                st.session_state.user = {
                    "id": user_record[0],
                    "username": user_record[1],
                    "name": user_record[3],
                    "role": user_record[4]
                }
                st.rerun()
            else:
                st.error("Invalid credentials. Please contact your instructor/admin.")
    st.stop()

# --- Authenticated App ---
user = st.session_state.user

# Top navigation bar
col_nav, col_logout = st.columns([8, 2])
with col_nav:
    st.markdown(f"### Welcome, **{user['name']}** ({user['role'].capitalize()})")
with col_logout:
    if st.button("Logout", use_container_width=True):
        st.session_state.user = None
        st.rerun()

# Convert PDF page to watermarked image
def render_pdf_page_as_image(pdf_path, page_num, watermark_text):
    doc = fitz.open(pdf_path)
    if page_num >= len(doc):
        return None, len(doc)
    page = doc.load_page(page_num)
    
    # Add dynamic user watermark across the slide
    rect = page.rect
    page.insert_text(
        fitz.Point(rect.width * 0.15, rect.height * 0.5),
        watermark_text,
        fontsize=24,
        rotate=0,
        color=(0.7, 0.7, 0.7),
        fill_opacity=0.3
    )
    
    pix = page.get_pixmap(dpi=150)
    img_bytes = pix.tobytes("png")
    return img_bytes, len(doc)

# ----------------- ADMIN PANEL -----------------
if user["role"] == "admin":
    with st.expander("⚙️ Admin Management Panel"):
        admin_tab1, admin_tab2 = st.tabs(["👤 Add Student", "📤 Upload Material"])
        
        with admin_tab1:
            with st.form("create_user_form"):
                new_user = st.text_input("New Student Username")
                new_name = st.text_input("Student Full Name")
                new_pass = st.text_input("Temporary Password", type="password")
                create_submit = st.form_submit_button("Add Student")
                
                if create_submit and new_user and new_pass:
                    try:
                        conn = get_connection()
                        c = conn.cursor()
                        c.execute("INSERT INTO users (username, password_hash, full_name, role) VALUES (?, ?, ?, 'student')",
                                  (new_user, hash_password(new_pass), new_name))
                        conn.commit()
                        conn.close()
                        st.success(f"Student account created for {new_user}!")
                    except sqlite3.IntegrityError:
                        st.error("Username already exists.")

        with admin_tab2:
            with st.form("upload_content_form"):
                cat = st.selectbox("Category", ["Python", "OOPs", "DBMS", "MySQL", "DSA", "Web Development"])
                title = st.text_input("Lesson / Chapter Title")
                uploaded_pdf = st.file_uploader("Upload PDF / Presentation", type=["pdf"])
                upload_submit = st.form_submit_button("Upload Material")

                if upload_submit and uploaded_pdf and title:
                    os.makedirs(f"uploads/{cat}", exist_ok=True)
                    save_path = os.path.join(f"uploads/{cat}", uploaded_pdf.name)
                    with open(save_path, "wb") as f:
                        f.write(uploaded_pdf.getbuffer())

                    conn = get_connection()
                    c = conn.cursor()
                    c.execute("INSERT INTO content (title, category, file_path) VALUES (?, ?, ?)",
                              (title, cat, save_path))
                    conn.commit()
                    conn.close()
                    st.success(f"Uploaded '{title}' under {cat}!")

st.divider()

# ----------------- STUDENT CONTENT VIEW -----------------
categories = ["Python", "OOPs", "DBMS", "MySQL", "DSA", "Web Development"]
tabs = st.tabs(categories)

for idx, cat_name in enumerate(categories):
    with tabs[idx]:
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT id, title, file_path FROM content WHERE category = ?", (cat_name,))
        items = c.fetchall()
        conn.close()
        
        if not items:
            st.info(f"No materials uploaded yet for {cat_name}.")
            continue

        selected_item = st.selectbox(
            f"Select Topic ({cat_name})", 
            items, 
            format_func=lambda x: x[1], 
            key=f"select_{cat_name}"
        )

        if selected_item:
            item_id, item_title, file_path = selected_item
            
            # Slide Viewer controls
            if os.path.exists(file_path):
                # Page pagination state
                page_key = f"page_{item_id}"
                if page_key not in st.session_state:
                    st.session_state[page_key] = 0

                watermark = f"{user['name']} | {user['username']}"
                img_data, total_pages = render_pdf_page_as_image(file_path, st.session_state[page_key], watermark)

                col_prev, col_info, col_next = st.columns([1, 2, 1])
                with col_prev:
                    if st.button("⬅️ Previous", key=f"prev_{item_id}") and st.session_state[page_key] > 0:
                        st.session_state[page_key] -= 1
                        st.rerun()
                with col_info:
                    st.write(f"Page **{st.session_state[page_key] + 1}** of **{total_pages}**")
                with col_next:
                    if st.button("Next ➡️", key=f"next_{item_id}") and st.session_state[page_key] < total_pages - 1:
                        st.session_state[page_key] += 1
                        st.rerun()

                # Display the slide as an image (prevents PDF toolbar download)
                st.image(img_data, use_container_width=True)

            # --- Likes & Comments Section ---
            st.divider()
            c_like, c_comment = st.columns([1, 2])
            
            conn = get_connection()
            c = conn.cursor()

            # Likes
            with c_like:
                c.execute("SELECT COUNT(*) FROM likes WHERE content_id = ?", (item_id,))
                total_likes = c.fetchone()[0]
                
                c.execute("SELECT 1 FROM likes WHERE content_id = ? AND username = ?", (item_id, user['username']))
                has_liked = c.fetchone() is not None

                btn_label = f"❤️ Liked ({total_likes})" if has_liked else f"🤍 Like ({total_likes})"
                if st.button(btn_label, key=f"like_{item_id}"):
                    if has_liked:
                        c.execute("DELETE FROM likes WHERE content_id = ? AND username = ?", (item_id, user['username']))
                    else:
                        c.execute("INSERT INTO likes (content_id, username) VALUES (?, ?)", (item_id, user['username']))
                    conn.commit()
                    st.rerun()

            # Comments
            with c_comment:
                st.write("##### Discussion & Doubts")
                with st.form(f"comment_form_{item_id}"):
                    cmt_text = st.text_input("Leave a comment or question...")
                    cmt_submit = st.form_submit_button("Post Comment")
                    if cmt_submit and cmt_text.strip():
                        c.execute("INSERT INTO comments (content_id, username, comment) VALUES (?, ?, ?)",
                                  (item_id, user['username'], cmt_text.strip()))
                        conn.commit()
                        st.rerun()

                # Display comments
                c.execute("SELECT username, comment, created_at FROM comments WHERE content_id = ? ORDER BY id DESC", (item_id,))
                all_comments = c.fetchall()
                for c_user, c_body, c_time in all_comments:
                    st.markdown(f"**{c_user}** ({c_time}):")
                    st.info(c_body)

            conn.close()
