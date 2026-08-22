# -*- coding: utf-8 -*-
import sqlite3
import os
import hashlib
import secrets

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "opioides.db")

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

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_db()
    cursor = conn.cursor()

    # Tabla Usuarios
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

    # Tabla Medicamentos / Diluciones
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS medicamentos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT UNIQUE NOT NULL,
        stock_actual INTEGER DEFAULT 100
    )
    """)

    # Tabla Registros de Cuaderno
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS registros_cuaderno (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha_hora TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        paciente_nombre TEXT NOT NULL,
        paciente_hc TEXT DEFAULT '',
        quirofano TEXT DEFAULT '',
        medicamento_id INTEGER NOT NULL,
        cantidad_usada INTEGER NOT NULL,
        tipo TEXT DEFAULT 'uso', -- 'uso' o 'devolucion'
        receta_nro TEXT DEFAULT '',
        tecnico_id INTEGER,
        tecnico_nombre TEXT NOT NULL,
        control_farmacia INTEGER DEFAULT 0, -- 0: Pendiente, 1: Aprobado, 2: Rechazado
        farmaceutico_nombre TEXT DEFAULT '',
        motivo_rechazo TEXT DEFAULT '',
        observaciones TEXT DEFAULT '',
        FOREIGN KEY (medicamento_id) REFERENCES medicamentos(id)
    )
    """)

    # Tabla Despacho Diario Manual de Farmacia
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

    # Asegurar columnas si la base de datos ya existia
    cursor.execute("PRAGMA table_info(registros_cuaderno)")
    cols = [r[1] for r in cursor.fetchall()]
    if "tipo" not in cols:
        cursor.execute("ALTER TABLE registros_cuaderno ADD COLUMN tipo TEXT DEFAULT 'uso'")
    if "motivo_rechazo" not in cols:
        cursor.execute("ALTER TABLE registros_cuaderno ADD COLUMN motivo_rechazo TEXT DEFAULT ''")

    # Medicamentos base
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
        cursor.execute("INSERT OR IGNORE INTO medicamentos (nombre, stock_actual) VALUES (?, ?)", med)

    # Usuarios base
    usuarios_base = [
        ("admin", "Super Administrador HCM", hash_password("admin123"), "admin"),
        ("tecnico", "Tecnico Anestesia HCM", hash_password("tecnico123"), "tecnico"),
        ("farmacia", "Farmacia Central HCM", hash_password("farmacia123"), "farmacia"),
    ]
    for u in usuarios_base:
        cursor.execute("INSERT OR IGNORE INTO usuarios (username, nombre_completo, password_hash, rol) VALUES (?, ?, ?, ?)", u)

    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Base de datos inicializada correctamente.")