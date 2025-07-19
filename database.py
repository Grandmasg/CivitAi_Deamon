import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), 'data', 'completed.db')

# --- Database initialization ---
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS downloads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        model_id TEXT,
        filename TEXT,
        status TEXT,
        message TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS errors (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        model_id TEXT,
        filename TEXT,
        error TEXT
    )''')
    conn.commit()
    conn.close()

# --- Logging functions ---
def log_download(model_id, filename, status, message=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    from datetime import datetime, timezone
    c.execute('INSERT INTO downloads (timestamp, model_id, filename, status, message) VALUES (?, ?, ?, ?, ?)',
              (datetime.now(timezone.utc).isoformat(), model_id, filename, status, message))
    conn.commit()
    conn.close()

def log_error(model_id, filename, error):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    from datetime import datetime, timezone
    c.execute('INSERT INTO errors (timestamp, model_id, filename, error) VALUES (?, ?, ?, ?)',
              (datetime.now(timezone.utc).isoformat(), model_id, filename, error))
    conn.commit()
    conn.close()

# --- Analysis example ---
def downloads_per_day():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT substr(timestamp, 1, 10) as day, COUNT(*) FROM downloads GROUP BY day ORDER BY day DESC')
    result = c.fetchall()
    conn.close()
    return result

# Auto-init db on import
init_db()

# Example usage:
# log_download('123', 'model.safetensors', 'success')
# log_error('123', 'model.safetensors', 'Download failed')
# print(downloads_per_day())
