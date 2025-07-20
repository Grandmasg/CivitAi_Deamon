def download_time_stats_per_base_model():
    """
    Returns: list of (base_model, avg_time, min_time, max_time, count)
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT base_model, AVG(download_time), MIN(download_time), MAX(download_time), COUNT(*) FROM downloads WHERE download_time IS NOT NULL GROUP BY base_model')
    result = c.fetchall()
    conn.close()
    return result

def file_size_stats_per_base_model():
    """
    Returns: list of (base_model, avg_size, min_size, max_size, count)
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT base_model, AVG(file_size), MIN(file_size), MAX(file_size), COUNT(*) FROM downloads WHERE file_size IS NOT NULL GROUP BY base_model')
    result = c.fetchall()
    conn.close()
    return result

def downloads_per_day_base_model_status():
    """
    Returns: list of (day, base_model, status, count)
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT substr(timestamp, 1, 10) as day, base_model, status, COUNT(*) FROM downloads GROUP BY day, base_model, status ORDER BY day DESC')
    result = c.fetchall()
    conn.close()
    return result
# --- Duplicate check ---
def is_already_downloaded(model_id, model_version_id):
    """
    Returns True als deze combinatie al als 'success' in downloads staat.
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''SELECT 1 FROM downloads WHERE model_id=? AND model_version_id=? AND status='success' LIMIT 1''', (model_id, model_version_id))
    result = c.fetchone()
    conn.close()
    return bool(result)
import sqlite3
import os
from datetime import datetime

import sys
if "pytest" in sys.modules or os.environ.get("CIVITAI_TEST_AUTH") == "1":
    DB_PATH = os.path.join(os.path.dirname(__file__), 'data', 'test_completed.db')
else:
    DB_PATH = os.environ.get('CIVITAI_DAEMON_DB_PATH', os.path.join(os.path.dirname(__file__), 'data', 'completed.db'))

# --- Database initialization ---

def clear_test_db():
    """Delete all rows from downloads and errors if using test_completed.db. Ignores if tables do not exist."""
    if DB_PATH.endswith('test_completed.db'):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        try:
            c.execute('DELETE FROM downloads')
        except sqlite3.OperationalError:
            pass
        try:
            c.execute('DELETE FROM errors')
        except sqlite3.OperationalError:
            pass
        conn.commit()
        conn.close()

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Add model_type column if not exists
    c.execute('''CREATE TABLE IF NOT EXISTS downloads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        model_id TEXT,
        model_version_id TEXT,
        filename TEXT,
        model_type TEXT,
        status TEXT,
        message TEXT,
        file_size INTEGER,
        download_time REAL,
        base_model TEXT
    )''')
    # Migrate old tables (add columns if missing)
    for col, typ in [('file_size', 'INTEGER'), ('model_type', 'TEXT'), ('download_time', 'REAL'), ('base_model', 'TEXT')]:
        try:
            c.execute(f'ALTER TABLE downloads ADD COLUMN {col} {typ}')
        except sqlite3.OperationalError:
            pass  # Already exists
    c.execute('''CREATE TABLE IF NOT EXISTS errors (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        model_id TEXT,
        filename TEXT,
        error TEXT
    )''')
    conn.commit()
    conn.close()
    # Now clear if in test mode
    if DB_PATH.endswith('test_completed.db'):
        clear_test_db()

# --- Logging functions ---
def log_download(model_id, model_version_id, filename, status, message=None, model_type=None, file_size=None, download_time=None, base_model=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    from datetime import datetime, timezone
    c.execute('INSERT INTO downloads (timestamp, model_id, model_version_id, filename, model_type, status, message, file_size, download_time, base_model) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
              (datetime.now(timezone.utc).isoformat(), model_id, model_version_id, filename, model_type, status, message, file_size, download_time, base_model))
    conn.commit()
    conn.close()

def download_time_stats_per_type():
    """
    Returns: list of (model_type, avg_time, min_time, max_time, count)
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT model_type, AVG(download_time), MIN(download_time), MAX(download_time), COUNT(*) FROM downloads WHERE download_time IS NOT NULL GROUP BY model_type')
    result = c.fetchall()
    conn.close()
    return result

# --- Metrics ---
def downloads_per_day_type_status():
    """
    Returns: list of (day, model_type, status, count)
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT substr(timestamp, 1, 10) as day, model_type, status, COUNT(*) FROM downloads GROUP BY day, model_type, status ORDER BY day DESC')
    result = c.fetchall()
    conn.close()
    return result

def file_size_stats_per_type():
    """
    Returns: list of (model_type, avg_size, min_size, max_size, count)
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT model_type, AVG(file_size), MIN(file_size), MAX(file_size), COUNT(*) FROM downloads WHERE file_size IS NOT NULL GROUP BY model_type')
    result = c.fetchall()
    conn.close()
    return result

def get_all_metrics():
    """
    Returns a dict with all metrics for API use
    """
    try:
        return {
            'downloads_per_day': downloads_per_day(),
            'downloads_per_day_type_status': downloads_per_day_type_status(),
            'file_size_stats_per_type': file_size_stats_per_type(),
            'download_time_stats_per_type': download_time_stats_per_type(),
            'downloads_per_day_base_model_status': downloads_per_day_base_model_status(),
            'file_size_stats_per_base_model': file_size_stats_per_base_model(),
            'download_time_stats_per_base_model': download_time_stats_per_base_model(),
            'total_downloads': get_total_downloads(),
        }
    except Exception:
        # Bij een fout altijd alle keys met lege waarden teruggeven
        return {
            'downloads_per_day': [],
            'downloads_per_day_type_status': [],
            'file_size_stats_per_type': [],
            'download_time_stats_per_type': [],
            'downloads_per_day_base_model_status': [],
            'file_size_stats_per_base_model': [],
            'download_time_stats_per_base_model': [],
            'total_downloads': 0,
        }

def get_total_downloads():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM downloads')
    result = c.fetchone()[0]
    conn.close()
    return result

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

def downloads_per_day_per_type():
    """
    Returns a list of tuples: (day, model_type, count)
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Gebruik nu de model_type kolom
    c.execute('SELECT substr(timestamp, 1, 10) as day, model_type FROM downloads')
    rows = c.fetchall()
    stats = {}
    for day, model_type in rows:
        mtype = model_type or 'other'
        key = (day, mtype)
        stats[key] = stats.get(key, 0) + 1
    # Maak een lijst van (day, model_type, count)
    result = [(day, mtype, count) for (day, mtype), count in stats.items()]
    # Sorteer op dag aflopend, dan type
    result.sort(key=lambda x: (x[0], x[1]), reverse=True)
    conn.close()
    return result

# Auto-init db on import
init_db()

# Example usage:
# log_download('123', 'model.safetensors', 'success')
# log_error('123', 'model.safetensors', 'Download failed')
# print(downloads_per_day())
