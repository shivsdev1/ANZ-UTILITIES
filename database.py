import sqlite3
from threading import Lock

# db locks - important for thread safety
booking_lock = Lock()
krispoints_lock = Lock()
announcements_lock = Lock()
flights_lock = Lock()
tickets_lock = Lock()

# db connections
bookings_db = None
krispoints_db = None
announcements_db = None
flights_db = None
tickets_db = None

bc = None
kc = None
ac = None
fc = None
tc = None

FLIGHTS = {}

def get_db_connection(db_name):
    return sqlite3.connect(
        db_name,
        check_same_thread=False,
        timeout=30.0,
        isolation_level='IMMEDIATE'
    )

def setup_databases():
    global bookings_db, krispoints_db, announcements_db, flights_db, tickets_db
    global bc, kc, ac, fc, tc
    
    # bookings db
    bookings_db = get_db_connection("bookings.db")
    bc = bookings_db.cursor()
    bc.execute("""
    CREATE TABLE IF NOT EXISTS bookings (
        code TEXT PRIMARY KEY,
        flight TEXT,
        route TEXT,
        aircraft TEXT,
        time TEXT,
        cabin TEXT,
        who TEXT,
        roblox TEXT,
        discord_id TEXT,
        booked_by INTEGER
    )
    """)
    bookings_db.commit()

    # krispoints db
    krispoints_db = get_db_connection("krispoints.db")
    kc = krispoints_db.cursor()
    kc.execute("""
    CREATE TABLE IF NOT EXISTS krispoints (
        user_id INTEGER PRIMARY KEY,
        balance INTEGER DEFAULT 0,
        flights INTEGER DEFAULT 0
    )
    """)
    krispoints_db.commit()

    # announcements db
    announcements_db = get_db_connection("announcements.db")
    ac = announcements_db.cursor()
    ac.execute("""
    CREATE TABLE IF NOT EXISTS announcements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        flight TEXT,
        departure_airport TEXT,
        departure_time TEXT,
        departure_gate TEXT,
        departure_terminal TEXT,
        arrival_airport TEXT,
        arrival_time TEXT,
        arrival_gate TEXT,
        date TEXT,
        meal_service TEXT,
        host TEXT,
        alerts TEXT,
        server_link TEXT,
        status TEXT,
        message_id INTEGER
    )
    """)
    announcements_db.commit()

    # flights db
    flights_db = get_db_connection("flights.db")
    fc = flights_db.cursor()
    fc.execute("""
    CREATE TABLE IF NOT EXISTS flights (
        flight_code TEXT PRIMARY KEY,
        route TEXT,
        aircraft TEXT,
        departure_time TEXT,
        departure_date TEXT
    )
    """)
    flights_db.commit()

    # tickets db
    tickets_db = get_db_connection("tickets.db")
    tc = tickets_db.cursor()
    tc.execute("""
    CREATE TABLE IF NOT EXISTS tickets (
        ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticket_number TEXT UNIQUE,
        channel_id INTEGER,
        user_id INTEGER,
        category TEXT,
        title TEXT,
        created_at TEXT,
        status TEXT DEFAULT 'open',
        transcript TEXT DEFAULT ''
    )
    """)
    tickets_db.commit()

    load_flights()
    print("[DB] All databases initialized")

def load_flights():
    try:
        fc.execute("SELECT flight_code, route, aircraft, departure_time FROM flights")
        rows = fc.fetchall()
        FLIGHTS.clear()
        for code, route, aircraft, time in rows:
            FLIGHTS[code] = (route, aircraft, time)
        print(f"[FLIGHTS] Loaded {len(FLIGHTS)} flights")
    except Exception as e:
        print(f"[FLIGHTS ERROR] {e}")