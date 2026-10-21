import sqlite3
import bcrypt

DB_NAME = "portal.db"

def get_connection():
    return sqlite3.connect(DB_NAME, check_same_thread=False)

def init_db():
    conn = get_connection()
    c = conn.cursor()
    
    # Users table
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT NOT NULL,
            role TEXT DEFAULT 'student'
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

    # Default Admin account (admin / admin123)
    c.execute("SELECT * FROM users WHERE username = 'admin'")
    if not c.fetchone():
        hashed = bcrypt.hashpw("admin123".encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        c.execute("INSERT INTO users (username, password_hash, full_name, role) VALUES (?, ?, ?, ?)",
                  ("admin", hashed, "Portal Admin", "admin"))

    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully.")