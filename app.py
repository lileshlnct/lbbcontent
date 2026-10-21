import streamlit as st
import sqlite3
import bcrypt
import os
import io
import pandas as pd
import fitz  # PyMuPDF
from database import init_db, get_connection, log_activity

init_db()

st.set_page_config(page_title="Training LMS Portal", layout="wide", page_icon="🎓")

# --- Content Protection CSS ---
PROTECTION_CSS = """
<style>
    body, [class*="st-"] {
        -webkit-user-select: none !important;
        -moz-user-select: none !important;
        -ms-user-select: none !important;
        user-select: none !important;
    }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
</style>
<script>
    document.addEventListener('contextmenu', event => event.preventDefault());
</script>
"""
st.markdown(PROTECTION_CSS, unsafe_allow_html=True)

# --- Password Helpers ---
def verify_password(plain, hashed):
    return bcrypt.checkpw(plain.encode('utf-8'), hashed.encode('utf-8'))

def hash_password(plain):
    return bcrypt.hashpw(plain.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

if "user" not in st.session_state:
    st.session_state.user = None

# ==========================================
# 1. LOGIN INTERFACE
# ==========================================
if not st.session_state.user:
    st.title("🎓 Student & Admin Learning Portal")
    st.subheader("Login to Access Course Materials")

    with st.form("login_form"):
        login_id = st.text_input("Enrollment Number (Students) or Admin Username").strip()
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Login", use_container_width=True)

        if submit:
            conn = get_connection()
            c = conn.cursor()
            # Match either enrollment_no OR username
            c.execute("""
                SELECT id, username, enrollment_no, password_hash, full_name, role 
                FROM users 
                WHERE enrollment_no = ? OR username = ?
            """, (login_id, login_id))
            user_record = c.fetchone()
            conn.close()

            if user_record and verify_password(password, user_record[3]):
                identifier = user_record[2] if user_record[2] else user_record[1]
                st.session_state.user = {
                    "id": user_record[0],
                    "username": user_record[1],
                    "enrollment_no": user_record[2],
                    "name": user_record[4],
                    "role": user_record[5],
                    "identifier": identifier
                }
                # Log login event
                log_activity(user_record[0], identifier, "LOGIN", "User logged in")
                st.rerun()
            else:
                st.error("Invalid Enrollment Number/Username or Password.")
    st.stop()

# ==========================================
# 2. LOGGED-IN PORTAL
# ==========================================
user = st.session_state.user

# Header & Logout
col_nav, col_logout = st.columns([8, 2])
with col_nav:
    st.markdown(f"### Welcome, **{user['name']}** ({user['identifier']} - {user['role'].capitalize()})")
with col_logout:
    if st.button("Logout", use_container_width=True):
        log_activity(user['id'], user['identifier'], "LOGOUT", "User logged out")
        st.session_state.user = None
        st.rerun()

# Watermarked PDF Renderer (fixed with morph=Matrix(45))
def render_pdf_page_as_image(pdf_path, page_num, watermark_text):
    doc = fitz.open(pdf_path)
    if page_num >= len(doc):
        return None, len(doc)
    page = doc.load_page(page_num)
    
    rect = page.rect
    point = fitz.Point(rect.width * 0.15, rect.height * 0.6)
    page.insert_text(
        point,
        watermark_text,
        fontsize=22,
        morph=(point, fitz.Matrix(45)),
        color=(0.7, 0.7, 0.7),
        fill_opacity=0.3
    )
    
    pix = page.get_pixmap(dpi=150)
    return pix.tobytes("png"), len(doc)

# ==========================================
# 3. ADMIN MANAGEMENT PANEL
# ==========================================
# ==========================================
# 3. ADMIN MANAGEMENT PANEL
# ==========================================
if user["role"] == "admin":
    with st.expander("⚙️ Admin Management & Analytics Panel", expanded=False):
        adm_tab1, adm_tab2, adm_tab3, adm_tab4, adm_tab5 = st.tabs([
            "👤 Add Single Student", 
            "📁 Bulk Upload (CSV)", 
            "📤 Upload Material",
            "📊 Student Activity Dashboard",
            "🔐 Admin Settings"
        ])

        # --- TAB 1: Single Student ---
        with adm_tab1:
            st.markdown("##### Register a New Student")
            with st.form("add_student_single"):
                f_name = st.text_input("Full Name*").strip()
                f_enroll = st.text_input("Enrollment Number* (Login ID)").strip()
                f_email = st.text_input("Email ID*").strip()
                f_contact = st.text_input("Contact Number*").strip()
                f_pass = st.text_input("Temporary Password*", type="password")
                add_sub = st.form_submit_button("Register Student")

                if add_sub:
                    if not (f_name and f_enroll and f_email and f_contact and f_pass):
                        st.error("All fields are mandatory.")
                    else:
                        try:
                            conn = get_connection()
                            c = conn.cursor()
                            c.execute("""
                                INSERT INTO users (username, enrollment_no, email, contact_no, password_hash, full_name, role)
                                VALUES (?, ?, ?, ?, ?, ?, 'student')
                            """, (f_enroll, f_enroll, f_email, f_contact, hash_password(f_pass), f_name))
                            conn.commit()
                            conn.close()
                            log_activity(user['id'], user['identifier'], "ADMIN_ADD_STUDENT", f"Added student: {f_enroll}")
                            st.success(f"Student '{f_name}' ({f_enroll}) added successfully!")
                        except sqlite3.IntegrityError as e:
                            err = str(e).lower()
                            if "enrollment_no" in err or "username" in err:
                                st.error("Error: Enrollment Number already exists!")
                            elif "email" in err:
                                st.error("Error: Email ID already registered!")
                            elif "contact_no" in err:
                                st.error("Error: Contact Number already registered!")
                            else:
                                st.error(f"Duplicate entry error: {e}")

        # --- TAB 2: Bulk CSV Upload ---
        with adm_tab2:
            st.markdown("##### Bulk Student Enrollment via CSV")
            st.caption("Upload a CSV file containing: `full_name`, `enrollment_no`, `email`, `contact_no`, `password`")

            sample_df = pd.DataFrame([
                {"full_name": "John Doe", "enrollment_no": "EN202601", "email": "john@example.com", "contact_no": "9876543210", "password": "tempPass123"},
                {"full_name": "Jane Smith", "enrollment_no": "EN202602", "email": "jane@example.com", "contact_no": "9876543211", "password": "tempPass456"}
            ])
            csv_buffer = io.StringIO()
            sample_df.to_csv(csv_buffer, index=False)
            st.download_button(
                label="📥 Download Sample CSV Template",
                data=csv_buffer.getvalue(),
                file_name="student_bulk_sample.csv",
                mime="text/csv"
            )

            bulk_file = st.file_uploader("Upload Students CSV", type=["csv"])
            if bulk_file and st.button("Process & Import CSV"):
                try:
                    df = pd.read_csv(bulk_file)
                    required_cols = {"full_name", "enrollment_no", "email", "contact_no", "password"}
                    if not required_cols.issubset(set(df.columns)):
                        st.error(f"CSV missing required columns. Must include: {', '.join(required_cols)}")
                    else:
                        conn = get_connection()
                        c = conn.cursor()
                        success_count = 0
                        errors = []

                        for index, row in df.iterrows():
                            e_no = str(row["enrollment_no"]).strip()
                            e_mail = str(row["email"]).strip()
                            e_phone = str(row["contact_no"]).strip()
                            e_name = str(row["full_name"]).strip()
                            e_pw = str(row["password"]).strip()

                            try:
                                c.execute("""
                                    INSERT INTO users (username, enrollment_no, email, contact_no, password_hash, full_name, role)
                                    VALUES (?, ?, ?, ?, ?, ?, 'student')
                                """, (e_no, e_no, e_mail, e_phone, hash_password(e_pw), e_name))
                                success_count += 1
                            except sqlite3.IntegrityError:
                                errors.append(f"Row {index + 1} ({e_no}): Duplicate enrollment, email, or contact number.")

                        conn.commit()
                        conn.close()

                        if success_count > 0:
                            st.success(f"Successfully registered {success_count} students!")
                            log_activity(user['id'], user['identifier'], "BULK_STUDENT_IMPORT", f"Imported {success_count} students")
                        if errors:
                            st.warning(f"Skipped {len(errors)} records due to conflicts:")
                            for err_msg in errors:
                                st.write(f"- {err_msg}")
                except Exception as ex:
                    st.error(f"Error parsing CSV: {ex}")

        # --- TAB 3: Material Upload ---
        with adm_tab3:
            st.markdown("##### Upload Class Materials")
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
                    log_activity(user['id'], user['identifier'], "UPLOAD_MATERIAL", f"Uploaded {title} in {cat}")
                    st.success(f"Uploaded '{title}' to {cat}!")

        # --- TAB 4: Student Activity Dashboard ---
        with adm_tab4:
            st.markdown("##### Real-Time Student Activity & Audit Logs")
            conn = get_connection()
            
            kpi_col1, kpi_col2, kpi_col3 = st.columns(3)
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM users WHERE role = 'student'")
            total_students = c.fetchone()[0]
            
            c.execute("SELECT COUNT(*) FROM activity_logs WHERE action = 'LOGIN'")
            total_logins = c.fetchone()[0]

            c.execute("SELECT COUNT(*) FROM comments")
            total_comments = c.fetchone()[0]

            kpi_col1.metric("Registered Students", total_students)
            kpi_col2.metric("Total Login Events", total_logins)
            kpi_col3.metric("Total Student Comments", total_comments)

            st.divider()

            logs_df = pd.read_sql_query("""
                SELECT 
                    a.id as Log_ID,
                    a.identifier as Enrollment_or_User,
                    u.full_name as Student_Name,
                    a.action as Action_Type,
                    a.details as Details,
                    a.timestamp as Time
                FROM activity_logs a
                LEFT JOIN users u ON a.user_id = u.id
                ORDER BY a.id DESC
                LIMIT 200
            """, conn)
            conn.close()

            filter_action = st.selectbox("Filter by Action", ["All"] + list(logs_df["Action_Type"].unique()))
            if filter_action != "All":
                logs_df = logs_df[logs_df["Action_Type"] == filter_action]

            st.dataframe(logs_df, use_container_width=True, hide_index=True)

        # --- TAB 5: Admin Settings & Profile ---
        with adm_tab5:
            st.markdown("##### Admin Profile & Security Settings")
            st.caption("Change your administrative username or password. Updating password will require re-login.")
            
            with st.form("admin_profile_update_form"):
                new_admin_name = st.text_input("Admin Display Name", value=user["name"]).strip()
                new_admin_user = st.text_input("Admin Username (Login ID)", value=user.get("username", "admin")).strip()
                new_admin_pass = st.text_input("New Password (leave empty to keep current)", type="password")
                confirm_pass = st.text_input("Confirm New Password", type="password")
                
                profile_submit = st.form_submit_button("Save Changes", use_container_width=True)

                if profile_submit:
                    if not new_admin_name or not new_admin_user:
                        st.error("Admin Name and Username cannot be empty.")
                    elif new_admin_pass and new_admin_pass != confirm_pass:
                        st.error("New passwords do not match.")
                    elif new_admin_pass and len(new_admin_pass) < 6:
                        st.warning("Password must be at least 6 characters long.")
                    else:
                        try:
                            conn = get_connection()
                            c = conn.cursor()
                            
                            # If password was provided, update credentials and force re-login
                            if new_admin_pass:
                                hashed_pw = hash_password(new_admin_pass)
                                c.execute("""
                                    UPDATE users 
                                    SET full_name = ?, username = ?, password_hash = ?
                                    WHERE id = ?
                                """, (new_admin_name, new_admin_user, hashed_pw, user["id"]))
                                conn.commit()
                                conn.close()
                                
                                log_activity(user['id'], new_admin_user, "ADMIN_CREDENTIALS_UPDATE", "Admin updated password/username")
                                st.success("Credentials updated successfully! Please re-login with your new credentials.")
                                st.session_state.user = None
                                st.rerun()
                            else:
                                # Just update name and username without forcing logout
                                c.execute("""
                                    UPDATE users 
                                    SET full_name = ?, username = ?
                                    WHERE id = ?
                                """, (new_admin_name, new_admin_user, user["id"]))
                                conn.commit()
                                conn.close()
                                
                                st.session_state.user["name"] = new_admin_name
                                st.session_state.user["username"] = new_admin_user
                                st.session_state.user["identifier"] = new_admin_user
                                log_activity(user['id'], new_admin_user, "ADMIN_PROFILE_UPDATE", "Admin updated display name/username")
                                st.success("Profile details updated successfully!")
                                st.rerun()
                                
                        except sqlite3.IntegrityError:
                            st.error("That username is already taken. Please choose another.")
st.divider()

# ==========================================
# 4. STUDENT CONTENT & SLIDE VIEWER
# ==========================================
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

            if os.path.exists(file_path):
                page_key = f"page_{item_id}"
                if page_key not in st.session_state:
                    st.session_state[page_key] = 0

                watermark = f"{user['name']} | {user['identifier']}"
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

                st.image(img_data, use_container_width=True)

            # Likes & Comments
            st.divider()
            c_like, c_comment = st.columns([1, 2])
            conn = get_connection()
            c = conn.cursor()

            # Likes
            with c_like:
                c.execute("SELECT COUNT(*) FROM likes WHERE content_id = ?", (item_id,))
                total_likes = c.fetchone()[0]

                c.execute("SELECT 1 FROM likes WHERE content_id = ? AND username = ?", (item_id, user['identifier']))
                has_liked = c.fetchone() is not None

                btn_label = f"❤️ Liked ({total_likes})" if has_liked else f"🤍 Like ({total_likes})"
                if st.button(btn_label, key=f"like_{item_id}"):
                    if has_liked:
                        c.execute("DELETE FROM likes WHERE content_id = ? AND username = ?", (item_id, user['identifier']))
                        log_activity(user['id'], user['identifier'], "UNLIKE", f"Unliked topic #{item_id}: {item_title}")
                    else:
                        c.execute("INSERT INTO likes (content_id, username) VALUES (?, ?)", (item_id, user['identifier']))
                        log_activity(user['id'], user['identifier'], "LIKE", f"Liked topic #{item_id}: {item_title}")
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
                                  (item_id, f"{user['name']} ({user['identifier']})", cmt_text.strip()))
                        conn.commit()
                        log_activity(user['id'], user['identifier'], "COMMENT", f"Commented on topic #{item_id}: '{cmt_text.strip()[:30]}...'")
                        st.rerun()

                c.execute("SELECT username, comment, created_at FROM comments WHERE content_id = ? ORDER BY id DESC", (item_id,))
                all_comments = c.fetchall()
                for c_user, c_body, c_time in all_comments:
                    st.markdown(f"**{c_user}** ({c_time}):")
                    st.info(c_body)

            conn.close()
