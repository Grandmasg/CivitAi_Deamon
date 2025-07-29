

# --- Standaard imports altijd eerst ---
import os
import sys
import sqlite3
from datetime import datetime, timezone
from loguru import logger

# --- Loguru file logging setup (ook als database direct wordt geladen) ---
log_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'logs'))
os.makedirs(log_dir, exist_ok=True)
# Verwijder alle bestaande handlers om dubbele logging en filterproblemen te voorkomen
logger.remove()
logger.add(os.path.join(log_dir, "database.log"), rotation="2 MB", retention=5, encoding="utf-8", filter=lambda record: record["extra"].get("name", "") == "civitai.database")

# Bind logger for DB logging
db_logger = logger.bind(name="civitai.database")

# --- DB Path Setup ---
data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
os.makedirs(data_dir, exist_ok=True)
if "pytest" in sys.modules or os.environ.get("CIVITAI_TEST_AUTH") == "1":
    DB_PATH = os.path.join(data_dir, 'test_completed.db')
else:
    DB_PATH = os.environ.get('CIVITAI_DAEMON_DB_PATH', os.path.join(data_dir, 'completed.db'))


# --- Database initialization ---
def clear_test_db():
    """Delete all rows from downloads and errors if using test_completed.db. Ignores if tables do not exist."""
    if DB_PATH.endswith('test_completed.db'):
        try:
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
            db_logger.info("Cleared test database tables downloads and errors.")
        except Exception as e:
            db_logger.error(f"Failed to clear test db: {e}")
        finally:
            conn.close()

def init_db():
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        # Add model_type column if not exists
        # Check of downloads-table al bestaat
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='downloads'")
        table_exists = c.fetchone()
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
            base_model TEXT,
            UNIQUE(model_id, model_version_id, filename, status)
        )''')
        # Log alleen als de tabel net is aangemaakt
        if not table_exists:
            db_logger.info("Database initialized and migrations checked.")
            logger.complete()
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
        # db_logger.info("Database initialized and migrations checked.")  # Dubbele logging verwijderd
    except Exception as e:
        db_logger.error(f"Failed to initialize database: {e}")
    finally:
        conn.close()
    # Now clear if in test mode
    if DB_PATH.endswith('test_completed.db'):
        clear_test_db()


# --- Logging functions ---
def log_download(model_id, model_version_id, filename, status, message=None, model_type=None, file_size=None, download_time=None, base_model=None):
    # Only log real downloads, not metrics/system/queue calls
    is_system = (model_id == 'system' and filename == '-')
    allowed_system_status = {'started', 'stopped'}
    if is_system and status not in allowed_system_status:
        # Don't log system/metrics/queue events
        return

    for attempt in range(2):
        try:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute('INSERT INTO downloads (timestamp, model_id, model_version_id, filename, model_type, status, message, file_size, download_time, base_model) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                      (datetime.now(timezone.utc).isoformat(), model_id, model_version_id, filename, model_type, status, message, file_size, download_time, base_model))
            conn.commit()
            # Log alleen als de insert daadwerkelijk succesvol was
            db_logger.info(f"Logged download: {filename} (status={status}, model_id={model_id})")
            print(f"[DEBUG] Logged download: {filename} (status={status}, model_id={model_id})")
            break
        except sqlite3.IntegrityError:
            # Duplicate entry, ignore, geen log
            break
        except sqlite3.OperationalError as e:
            if 'no such table' in str(e) and attempt == 0:
                init_db()
                continue
            db_logger.error(f"Failed to log download for {filename}: {e}")
        except Exception as e:
            db_logger.error(f"Failed to log download for {filename}: {e}")
        finally:
            try:
                conn.close()
            except:
                pass

def download_time_stats_per_type():
    """
    Returns: list of (model_type, avg_time, min_time, max_time, unique_count)
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        SELECT model_type,
               AVG(download_time),
               MIN(download_time),
               MAX(download_time),
               COUNT(*) as unique_count
        FROM (
            SELECT model_type, download_time
            FROM downloads
            WHERE status IN ('success', 'failed', 'skipped') AND download_time IS NOT NULL
            GROUP BY substr(timestamp, 1, 10), model_type, model_id, model_version_id, filename
        )
        GROUP BY model_type
    ''')
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
    c.execute("""
        SELECT substr(timestamp, 1, 10) as day, model_type, status, COUNT(*)
        FROM downloads
        WHERE status IN ('success', 'failed', 'skipped')
        GROUP BY day, model_type, status
        ORDER BY day DESC
    """)
    result = c.fetchall()
    conn.close()
    return result

def file_size_stats_per_type():
    """
    Returns: list of (model_type, avg_size, min_size, max_size, unique_count)
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        SELECT model_type,
               AVG(file_size),
               MIN(file_size),
               MAX(file_size),
               COUNT(*) as unique_count
        FROM (
            SELECT model_type, file_size
            FROM downloads
            WHERE status IN ('success', 'failed', 'skipped') AND file_size IS NOT NULL
            GROUP BY substr(timestamp, 1, 10), model_type, model_id, model_version_id, filename
        )
        GROUP BY model_type
    ''')
    result = c.fetchall()
    conn.close()
    return result

def get_all_metrics():
    """
    Returns a dict with all metrics for API use
    """
    return {
        'downloads_per_day': downloads_per_day(),
        'downloads_per_day_type_status': downloads_per_day_type_status(),
        'file_size_stats_per_type': file_size_stats_per_type(),
        'download_time_stats_per_type': download_time_stats_per_type(),
        'file_size_stats_per_type_unique': file_size_stats_per_type_unique(),
        'download_time_stats_per_type_unique': download_time_stats_per_type_unique(),
        'downloads_per_day_base_model_status': downloads_per_day_base_model_status(),
        'file_size_stats_per_base_model': file_size_stats_per_base_model(),
        'download_time_stats_per_base_model': download_time_stats_per_base_model(),
        'total_downloads': get_total_downloads(),
        'unique_successful_downloads': get_unique_successful_downloads(),
        'unique_failed_downloads': get_unique_failed_downloads(),
    }

# Unieke file size stats per type (alleen success)
def file_size_stats_per_type_unique():
    """
    Returns: list of (model_type, avg_size, min_size, max_size, unique_count)
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        SELECT model_type,
               AVG(file_size),
               MIN(file_size),
               MAX(file_size),
               COUNT(*) as unique_count
        FROM (
            SELECT model_type, file_size
            FROM downloads
            WHERE status IN ('success', 'failed', 'skipped') AND file_size IS NOT NULL
            GROUP BY substr(timestamp, 1, 10), model_type, model_id, model_version_id, filename
        )
        GROUP BY model_type
    ''')
    result = c.fetchall()
    conn.close()
    return result

# Unieke download time stats per type (alleen success)
def download_time_stats_per_type_unique():
    """
    Returns: list of (model_type, avg_time, min_time, max_time, unique_count)
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        SELECT model_type,
               AVG(download_time),
               MIN(download_time),
               MAX(download_time),
               COUNT(*) as unique_count
        FROM (
            SELECT model_type, download_time
            FROM downloads
            WHERE status IN ('success', 'failed', 'skipped') AND download_time IS NOT NULL
            GROUP BY substr(timestamp, 1, 10), model_type, model_id, model_version_id, filename
        )
        GROUP BY model_type
    ''')
    result = c.fetchall()
    conn.close()
    return result

# Unieke downloads/fails per dag, type, model_id, model_version_id, filename
def get_unique_successful_downloads():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Uniek per dag, type, model_id, model_version_id, filename
    c.execute('''
        SELECT COUNT(*) FROM (
            SELECT substr(timestamp, 1, 10) as day, model_type, model_id, model_version_id, filename
            FROM downloads
            WHERE status IN ('success', 'failed', 'skipped')
            GROUP BY day, model_type, model_id, model_version_id, filename
        )
    ''')
    result = c.fetchall()
    conn.close()
    return result

def get_total_downloads():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM downloads WHERE status IN ('success', 'failed', 'skipped')")
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

# --- Extra functions from top (restored) ---
def get_unique_failed_downloads():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Uniek per dag, type, model_id, model_version_id, filename
    c.execute('''
        SELECT COUNT(*) FROM (
            SELECT substr(timestamp, 1, 10) as day, model_type, model_id, model_version_id, filename
            FROM downloads
            WHERE status = 'failed'
            GROUP BY day, model_type, model_id, model_version_id, filename
        )
    ''')
    result = c.fetchall()
    conn.close()
    return result

def log_error(model_id, filename, error):
    for attempt in range(2):
        try:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute('INSERT INTO errors (timestamp, model_id, filename, error) VALUES (?, ?, ?, ?)',
                      (datetime.now(timezone.utc).isoformat(), model_id, filename, error))
            conn.commit()
            db_logger.warning(f"Logged error for {filename}: {error}")
            break
        except sqlite3.OperationalError as e:
            if 'no such table' in str(e) and attempt == 0:
                init_db()
                continue
            db_logger.error(f"Failed to log error for {filename}: {e}")
        except Exception as e:
            db_logger.error(f"Failed to log error for {filename}: {e}")
        finally:
            try:
                conn.close()
            except:
                pass

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

def downloads_per_day():
    """
    Returns: list of (day, count)
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT substr(timestamp, 1, 10) as day, COUNT(*) FROM downloads GROUP BY day ORDER BY day DESC')
    result = c.fetchall()
    conn.close()
    return result

# Auto-init db on import
init_db()
