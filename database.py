# -*- coding: utf-8 -*-
import os
import sqlite3
import hashlib
import secrets
import re

DATABASE_URL = os.environ.get("DATABASE_URL")
DB_PATH = os.path.join(os.path.dirname(__file__), "data", "opioides.db")

def is_postgres():
    return bool(DATABASE_URL and (DATABASE_URL.startswith("postgres://") or DATABASE_URL.startswith("postgresql://")))

def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    hashed = hashlib.sha256((salt + password).encode('utf-8')).hexdigest()
    return salt + "$" + hashed

def verify_password(stored_password: str, provided_password: str) -> bool:
    try:
        if "$" not in stored_password:
            return False
        parts = stored_password.split("$")
        salt, hashed = parts[0], parts[1]
        check_hash = hashlib.sha256((salt + provided_password).encode('utf-8')).hexdigest()
        return secrets.compare_digest(hashed, check_hash)
    except Exception:
        return False

class PgCursorWrapper:
    def __init__(self, pg_cursor):
        self.cursor = pg_cursor

    def execute(self, query, params=None):
        # Convertir placeholders SQLite ? a PostgreSQL %s
        pg_query = query.replace("?", "%s")
        
        # Compatibilidad de funciones de fecha SQLite DATE(col) -> col::date
        pg_query = re.sub(r'DATE\(([^)]+)\)', r'(\1)::date', pg_query, flags=re.IGNORECASE)
        
        if params is not None:
            if isinstance(params, (list, tuple)):
                self.cursor.execute(pg_query, params)
            else:
                self.cursor.execute(pg_query, (params,))
        else:
            self.cursor.execute(pg_query)
        return self

    def fetchone(self):
        row = self.cursor.fetchone()
        return dict(row) if row is not None else None

    def fetchall(self):
        rows = self.cursor.fetchall()
        return [dict(r) for r in rows]

    def close(self):
        self.cursor.close()

class PgConnWrapper:
    def __init__(self, pg_conn):
        self.conn = pg_conn

    def cursor(self):
        import psycopg2.extras
        return PgCursorWrapper(self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor))

    def commit(self):
        self.conn.commit()

    def close(self):
        self.conn.close()

def get_db():
    if is_postgres():
        import psycopg2
        url = DATABASE_URL
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        conn = psycopg2.connect(url, sslmode="require" if any(x in url for x in ["render.com", "neon.tech", "supabase", "railway"]) else "prefer")
        return PgConnWrapper(conn)
    else:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

def init_db():
    if is_postgres():
        init_postgres_db()
    else:
        init_sqlite_db()

def init_sqlite_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        nombre_completo TEXT NOT NULL,
        password_hash TEXT NOT NULL,
        rol TEXT NOT NULL,
        creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS medicamentos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT UNIQUE NOT NULL,
        stock_actual INTEGER DEFAULT 100
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS registros_cuaderno (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha_hora TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        paciente_nombre TEXT NOT NULL,
        paciente_hc TEXT DEFAULT '',
        quirofano TEXT DEFAULT '',
        medicamento_id INTEGER NOT NULL,
        cantidad_usada INTEGER NOT NULL,
        tipo TEXT DEFAULT 'uso',
        receta_nro TEXT DEFAULT '',
        tecnico_id INTEGER,
        tecnico_nombre TEXT NOT NULL,
        control_farmacia INTEGER DEFAULT 0,
        farmaceutico_nombre TEXT DEFAULT '',
        motivo_rechazo TEXT DEFAULT '',
        observaciones TEXT DEFAULT '',
        FOREIGN KEY (medicamento_id) REFERENCES medicamentos(id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS despacho_farmacia_diario (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha DATE NOT NULL,
        medicamento_id INTEGER NOT NULL,
        cantidad_despachada INTEGER NOT NULL DEFAULT 0,
        farmaceutico_id INTEGER,
        farmaceutico_nombre TEXT DEFAULT '',
        observaciones TEXT DEFAULT '',
        actualizado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(fecha, medicamento_id),
        FOREIGN KEY (medicamento_id) REFERENCES medicamentos(id)
    )
    """)

    cursor.execute("PRAGMA table_info(registros_cuaderno)")
    cols = [r[1] for r in cursor.fetchall()]
    if "tipo" not in cols:
        cursor.execute("ALTER TABLE registros_cuaderno ADD COLUMN tipo TEXT DEFAULT 'uso'")
    if "motivo_rechazo" not in cols:
        cursor.execute("ALTER TABLE registros_cuaderno ADD COLUMN motivo_rechazo TEXT DEFAULT ''")

    insert_default_data(conn, cursor, is_pg=False)
    conn.commit()
    conn.close()

def init_postgres_db():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id SERIAL PRIMARY KEY,
        username VARCHAR(100) UNIQUE NOT NULL,
        nombre_completo VARCHAR(255) NOT NULL,
        password_hash VARCHAR(255) NOT NULL,
        rol VARCHAR(50) NOT NULL,
        creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS medicamentos (
        id SERIAL PRIMARY KEY,
        nombre VARCHAR(255) UNIQUE NOT NULL,
        stock_actual INTEGER DEFAULT 100
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS registros_cuaderno (
        id SERIAL PRIMARY KEY,
        fecha_hora TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        paciente_nombre VARCHAR(255) NOT NULL,
        paciente_hc VARCHAR(100) DEFAULT '',
        quirofano VARCHAR(100) DEFAULT '',
        medicamento_id INTEGER NOT NULL REFERENCES medicamentos(id),
        cantidad_usada INTEGER NOT NULL,
        tipo VARCHAR(50) DEFAULT 'uso',
        receta_nro VARCHAR(100) DEFAULT '',
        tecnico_id INTEGER,
        tecnico_nombre VARCHAR(255) NOT NULL,
        control_farmacia INTEGER DEFAULT 0,
        farmaceutico_nombre VARCHAR(255) DEFAULT '',
        motivo_rechazo TEXT DEFAULT '',
        observaciones TEXT DEFAULT ''
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS despacho_farmacia_diario (
        id SERIAL PRIMARY KEY,
        fecha DATE NOT NULL,
        medicamento_id INTEGER NOT NULL REFERENCES medicamentos(id),
        cantidad_despachada INTEGER NOT NULL DEFAULT 0,
        farmaceutico_id INTEGER,
        farmaceutico_nombre VARCHAR(255) DEFAULT '',
        observaciones TEXT DEFAULT '',
        actualizado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(fecha, medicamento_id)
    );
    """)

    insert_default_data(conn, cursor, is_pg=True)
    conn.commit()
    conn.close()

def insert_default_data(conn, cursor, is_pg=False):
    meds = [
        ("Fentanilo (ampollas 0.5mg / 10ml)", 150),
        ("Remifentanilo (frascos 2mg)", 120),
        ("Remifentanilo (frascos 5mg)", 60),
        ("Morfina 1% (ampollas 10mg / 1ml)", 100),
        ("Ketamina 50mg/ml (frasco 10ml)", 80),
        ("Sufentanilo (ampollas 50mcg / 5ml)", 50),
        ("Dilucion Fentanilo (100mcg en 100ml Sol. Fisiologica)", 40),
        ("Dilucion Remifentanilo (2mg en 100ml Sol. Fisiologica)", 40),
        ("Solucion Fisiologica 0.9% 100ml (Vehiculo)", 200)
    ]
    for med in meds:
        if is_pg:
            cursor.execute("INSERT INTO medicamentos (nombre, stock_actual) VALUES (?, ?) ON CONFLICT (nombre) DO NOTHING", med)
        else:
            cursor.execute("INSERT OR IGNORE INTO medicamentos (nombre, stock_actual) VALUES (?, ?)", med)

    usuarios_base = [
        ("admin", "Super Administrador HCM", hash_password("admin123"), "admin"),
        ("tecnico", "Tecnico Anestesia HCM", hash_password("tecnico123"), "tecnico"),
        ("farmacia", "Farmacia Central HCM", hash_password("farmacia123"), "farmacia"),
    ]
    for u in usuarios_base:
        if is_pg:
            cursor.execute("INSERT INTO usuarios (username, nombre_completo, password_hash, rol) VALUES (?, ?, ?, ?) ON CONFLICT (username) DO NOTHING", u)
        else:
            cursor.execute("INSERT OR IGNORE INTO usuarios (username, nombre_completo, password_hash, rol) VALUES (?, ?, ?, ?)", u)

if __name__ == "__main__":
    init_db()
    print("Base de datos inicializada correctamente.")