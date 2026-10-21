import sqlite3
import bcrypt

DB_NAME = "portal.db"

def get_connection():
    return sqlite3.connect(DB_NAME, check_same_thread=False)

def init_db():
    conn = get_connection()
    c = conn.cursor()
    
    # Users table with unique constraints
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            enrollment_no TEXT UNIQUE,
            email TEXT UNIQUE,
            contact_no TEXT UNIQUE,
            password_hash TEXT NOT NULL,
            full_name TEXT NOT NULL,
            role TEXT DEFAULT 'student',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Activity Logs table
    c.execute('''
        CREATE TABLE IF NOT EXISTS activity_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            identifier TEXT,
            action TEXT,
            details TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Content table
    c.execute('''
        CREATE TABLE IF NOT EXISTS content (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            category TEXT NOT NULL,
            file_path TEXT NOT NULL
        )
    ''')

    # Comments table
    c.execute('''
        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content_id INTEGER,
            username TEXT,
            comment TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Likes table
    c.execute('''
        CREATE TABLE IF NOT EXISTS likes (
            content_id INTEGER,
            username TEXT,
            PRIMARY KEY (content_id, username)
        )
    ''')

    # Create default Admin if no admin exists
    c.execute("SELECT 1 FROM users WHERE role = 'admin'")
    if not c.fetchone():
        hashed = bcrypt.hashpw("admin123".encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        c.execute("""
            INSERT INTO users (username, enrollment_no, email, contact_no, password_hash, full_name, role)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, ("admin", "ADMIN001", "admin@portal.local", "0000000000", hashed, "Portal Admin", "admin"))

    conn.commit()
    conn.close()

def log_activity(user_id, identifier, action, details=""):
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT INTO activity_logs (user_id, identifier, action, details) VALUES (?, ?, ?, ?)",
              (user_id, identifier, action, details))
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Database updated and initialized successfully.")