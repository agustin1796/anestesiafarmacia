# -*- coding: utf-8 -*-
import os
import sqlite3
from typing import Optional, List
from fastapi import FastAPI, Depends, HTTPException, status, Header
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from jose import JWTError, jwt
from datetime import datetime, timezone, timedelta

from database import get_db, init_db, verify_password, hash_password, DB_PATH

SECRET_KEY = "hcm_opioides_fast_secret_key_secure_2026"
ALGORITHM = "HS256"

app = FastAPI(title="Control Opioides HCM - Trazabilidad y Seguridad", version="3.6.0")

@app.get("/health")
@app.get("/api/health")
def health_check():
    db_status = "ok"
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        conn.close()
    except Exception as e:
        db_status = f"error: {str(e)}"
    return {
        "status": "ok",
        "service": "Control Opioides HCM",
        "db": db_status,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


class LoginRequest(BaseModel):
    username: str
    password: str

class RegistroCreate(BaseModel):
    paciente_nombre: str
    medicamento_id: int
    cantidad_usada: int
    tipo: Optional[str] = "uso" # 'uso' o 'devolucion'

class ControlFarmaciaAprobarRequest(BaseModel):
    observaciones: Optional[str] = ""

class ControlFarmaciaRechazarRequest(BaseModel):
    motivo_rechazo: str

class DespachoFarmaciaItem(BaseModel):
    fecha: str
    medicamento_id: int
    cantidad_despachada: int
    observaciones: Optional[str] = ""

class DespachoFarmaciaBatch(BaseModel):
    fecha: str
    items: List[DespachoFarmaciaItem]

class MedicamentoCreate(BaseModel):
    nombre: str
    stock_actual: int

class MedicamentoUpdate(BaseModel):
    stock_actual: int

class UsuarioCreate(BaseModel):
    username: str
    nombre_completo: str
    password: str
    rol: str

class UsuarioUpdatePassword(BaseModel):
    password_nueva: str

class PasswordChangeRequest(BaseModel):
    password_actual: str
    password_nueva: str

def create_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=7)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="No autenticado")
    token = authorization.split(" ")[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if not username:
            raise HTTPException(status_code=401, detail="Token invalido")
    except JWTError:
        raise HTTPException(status_code=401, detail="Token invalido o expirado")
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, nombre_completo, rol FROM usuarios WHERE username = ?", (username,))
    user = cursor.fetchone()
    conn.close()
    if not user:
        raise HTTPException(status_code=401, detail="Usuario no encontrado")
    return dict(user)

def require_admin(user: dict = Depends(get_current_user)):
    if user["rol"] != "admin":
        raise HTTPException(status_code=403, detail="Acceso exclusivo para Super Administrador")
    return user

def require_farmacia_or_admin(user: dict = Depends(get_current_user)):
    if user["rol"] not in ["farmacia", "admin"]:
        raise HTTPException(status_code=403, detail="Acceso exclusivo para personal de Farmacia o Administrador")
    return user

@app.on_event("startup")
def on_startup():
    init_db()

# --- AUTENTICACION Y PERFIL ---
@app.post("/api/login")
def login(req: LoginRequest):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM usuarios WHERE username = ?", (req.username.strip().lower(),))
    user = cursor.fetchone()
    conn.close()

    if not user or not verify_password(user["password_hash"], req.password):
        raise HTTPException(status_code=400, detail="Usuario o contrasena incorrectos")

    token = create_token({"sub": user["username"], "rol": user["rol"]})
    return {
        "access_token": token,
        "user": {
            "id": user["id"],
            "username": user["username"],
            "nombre_completo": user["nombre_completo"],
            "rol": user["rol"]
        }
    }

@app.get("/api/me")
def me(user: dict = Depends(get_current_user)):
    return user

@app.post("/api/perfil/cambiar-password")
def cambiar_password(req: PasswordChangeRequest, user: dict = Depends(get_current_user)):
    if len(req.password_nueva) < 4:
        raise HTTPException(status_code=400, detail="La nueva contrasena debe tener al menos 4 caracteres")
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT password_hash FROM usuarios WHERE id = ?", (user["id"],))
    row = cursor.fetchone()
    if not row or not verify_password(row["password_hash"], req.password_actual):
        conn.close()
        raise HTTPException(status_code=400, detail="La contrasena actual es incorrecta")
    
    nueva_hash = hash_password(req.password_nueva)
    cursor.execute("UPDATE usuarios SET password_hash = ? WHERE id = ?", (nueva_hash, user["id"]))
    conn.commit()
    conn.close()
    return {"message": "Contrasena actualizada exitosamente"}

# --- MEDICAMENTOS Y STOCK (EXCLUSIVO SUPERADMIN) ---
@app.get("/api/medicamentos")
def get_medicamentos(user: dict = Depends(get_current_user)):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM medicamentos ORDER BY id ASC")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

@app.post("/api/medicamentos")
def crear_medicamento(m: MedicamentoCreate, user: dict = Depends(require_farmacia_or_admin)):
    nombre_limpio = m.nombre.strip()
    if not nombre_limpio:
        raise HTTPException(status_code=400, detail="El nombre del medicamento es requerido")
    
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO medicamentos (nombre, stock_actual) VALUES (?, ?)", (nombre_limpio, max(0, m.stock_actual)))
        conn.commit()
    except Exception:
        conn.close()
        raise HTTPException(status_code=400, detail="El medicamento o dilucion ya esta registrado o hubo un error")
    conn.close()
    return {"message": "Medicamento / Dilucion guardado correctamente en deposito"}

@app.put("/api/medicamentos/{med_id}")
def actualizar_stock(med_id: int, m: MedicamentoUpdate, user: dict = Depends(require_farmacia_or_admin)):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE medicamentos SET stock_actual = ? WHERE id = ?", (max(0, m.stock_actual), med_id))
    conn.commit()
    conn.close()
    return {"message": "Stock actualizado correctamente"}

# --- REGISTROS (CUADERNO DE MOVIMIENTOS) ---
@app.get("/api/registros")
def get_registros(busqueda: Optional[str] = None, fecha: Optional[str] = None, user: dict = Depends(get_current_user)):
    conn = get_db()
    cursor = conn.cursor()
    query = """
        SELECT r.id, r.fecha_hora, r.paciente_nombre, r.medicamento_id, r.cantidad_usada, r.tipo,
               r.tecnico_id, r.tecnico_nombre, r.control_farmacia, r.farmaceutico_nombre, r.motivo_rechazo, r.observaciones,
               m.nombre as medicamento_nombre
        FROM registros_cuaderno r
        JOIN medicamentos m ON r.medicamento_id = m.id
        WHERE 1=1
    """
    params = []
    if fecha:
        query += " AND DATE(r.fecha_hora) = DATE(?)"
        params.append(fecha.strip())
    if busqueda:
        query += " AND (r.paciente_nombre LIKE ? OR r.tecnico_nombre LIKE ? OR m.nombre LIKE ? OR r.farmaceutico_nombre LIKE ?)"
        term = f"%{busqueda.strip()}%"
        params.extend([term, term, term, term])
    query += " ORDER BY r.id DESC"
    cursor.execute(query, params)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

@app.post("/api/registros")
def anotar_paciente(reg: RegistroCreate, user: dict = Depends(get_current_user)):
    # Restriccion: El rol Farmacia solo controla, no anota pacientes ni devoluciones
    if user["rol"] == "farmacia":
        raise HTTPException(
            status_code=403, 
            detail="El rol Farmacia solo tiene permisos para controlar y validar registros, no para asentar pacientes ni devoluciones"
        )

    paciente_limpio = reg.paciente_nombre.strip()
    if not paciente_limpio:
        raise HTTPException(status_code=400, detail="El nombre del paciente o detalle es obligatorio")
    if reg.cantidad_usada <= 0:
        raise HTTPException(status_code=400, detail="La cantidad debe ser mayor a 0")

    tipo_reg = "devolucion" if reg.tipo == "devolucion" else "uso"

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM medicamentos WHERE id = ?", (reg.medicamento_id,))
    med = cursor.fetchone()
    if not med:
        conn.close()
        raise HTTPException(status_code=404, detail="Medicamento no encontrado")

    if tipo_reg == "uso":
        if med["stock_actual"] < reg.cantidad_usada:
            conn.close()
            raise HTTPException(status_code=400, detail=f"Stock insuficiente en deposito. Disponible: {med['stock_actual']}")
        cursor.execute("UPDATE medicamentos SET stock_actual = stock_actual - ? WHERE id = ?", (reg.cantidad_usada, reg.medicamento_id))
    else:
        cursor.execute("UPDATE medicamentos SET stock_actual = stock_actual + ? WHERE id = ?", (reg.cantidad_usada, reg.medicamento_id))

    cursor.execute("""
        INSERT INTO registros_cuaderno (
            paciente_nombre, medicamento_id, cantidad_usada, tipo,
            tecnico_id, tecnico_nombre
        ) VALUES (?, ?, ?, ?, ?, ?)
    """, (
        paciente_limpio,
        reg.medicamento_id,
        reg.cantidad_usada,
        tipo_reg,
        user["id"],
        user["nombre_completo"]
    ))
    conn.commit()
    conn.close()

    msg = "Devolucion registrada y stock reintegrado al deposito" if tipo_reg == "devolucion" else "Anotacion guardada y stock descontado exitosamente"
    return {"message": msg}

@app.put("/api/registros/{reg_id}/aprobar")
def aprobar_registro(reg_id: int, ctrl: ControlFarmaciaAprobarRequest, user: dict = Depends(get_current_user)):
    if user["rol"] not in ["farmacia", "admin"]:
        raise HTTPException(status_code=403, detail="Solo personal de Farmacia o Administrador pueden conformar y aprobar")

    conn = get_db()
    cursor = conn.cursor()

    # Si estaba previamente rechazado y ahora se aprueba, se reajusta el stock segun corresponda
    cursor.execute("SELECT * FROM registros_cuaderno WHERE id = ?", (reg_id,))
    reg = cursor.fetchone()
    if not reg:
        conn.close()
        raise HTTPException(status_code=404, detail="Registro no encontrado")

    if reg["control_farmacia"] == 2:
        if reg["tipo"] == "uso":
            cursor.execute("UPDATE medicamentos SET stock_actual = stock_actual - ? WHERE id = ?", (reg["cantidad_usada"], reg["medicamento_id"]))
        else:
            cursor.execute("UPDATE medicamentos SET stock_actual = stock_actual + ? WHERE id = ?", (reg["cantidad_usada"], reg["medicamento_id"]))

    cursor.execute("""
        UPDATE registros_cuaderno
        SET control_farmacia = 1,
            farmaceutico_nombre = ?,
            motivo_rechazo = '',
            observaciones = ?
        WHERE id = ?
    """, (user["nombre_completo"], ctrl.observaciones.strip() if ctrl.observaciones else "Conforme", reg_id))
    conn.commit()
    conn.close()
    return {"message": "Registro aprobado y verificado por Farmacia"}

@app.put("/api/registros/{reg_id}/rechazar")
def rechazar_registro(reg_id: int, ctrl: ControlFarmaciaRechazarRequest, user: dict = Depends(get_current_user)):
    if user["rol"] not in ["farmacia", "admin"]:
        raise HTTPException(status_code=403, detail="Solo personal de Farmacia o Administrador pueden rechazar registros")

    motivo = ctrl.motivo_rechazo.strip()
    if not motivo:
        raise HTTPException(status_code=400, detail="Debe indicar el motivo del rechazo")

    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM registros_cuaderno WHERE id = ?", (reg_id,))
    reg = cursor.fetchone()
    if not reg:
        conn.close()
        raise HTTPException(status_code=404, detail="Registro no encontrado")

    # Si no estaba rechazado antes, se anula el impacto de stock
    if reg["control_farmacia"] != 2:
        if reg["tipo"] == "uso":
            cursor.execute("UPDATE medicamentos SET stock_actual = stock_actual + ? WHERE id = ?", (reg["cantidad_usada"], reg["medicamento_id"]))
        else: # tipo devolucion rechazada -> no se acepta el reintegro
            cursor.execute("UPDATE medicamentos SET stock_actual = stock_actual - ? WHERE id = ?", (reg["cantidad_usada"], reg["medicamento_id"]))

    cursor.execute("""
        UPDATE registros_cuaderno
        SET control_farmacia = 2,
            farmaceutico_nombre = ?,
            motivo_rechazo = ?,
            observaciones = 'Rechazado por Farmacia'
        WHERE id = ?
    """, (user["nombre_completo"], motivo, reg_id))
    conn.commit()
    conn.close()
    return {"message": "Registro marcado como RECHAZADO y stock corregido"}

@app.put("/api/registros/{reg_id}/controlar")
def controlar_registro_legacy(reg_id: int, ctrl: ControlFarmaciaAprobarRequest, user: dict = Depends(get_current_user)):
    return aprobar_registro(reg_id, ctrl, user)

# --- RECUENTO DIARIO Y CARGA MANUAL DE DESPACHO FARMACIA ---
@app.get("/api/recuento-diario")
def get_recuento_diario(fecha: Optional[str] = None, user: dict = Depends(get_current_user)):
    fecha_filtro = fecha.strip() if fecha else datetime.now().strftime("%Y-%m-%d")
    
    conn = get_db()
    cursor = conn.cursor()
    
    # 1. Obtener todos los medicamentos
    cursor.execute("SELECT id, nombre, stock_actual FROM medicamentos ORDER BY id ASC")
    todos_meds = [dict(m) for m in cursor.fetchall()]

    # 2. Movimientos de cuaderno de tecnicos en esa fecha (excluyendo registros rechazados para el consumo real neto)
    cursor.execute("""
        SELECT r.medicamento_id, r.tipo, r.cantidad_usada, r.control_farmacia
        FROM registros_cuaderno r
        WHERE DATE(r.fecha_hora) = DATE(?)
    """, (fecha_filtro,))
    movimientos = cursor.fetchall()

    # 3. Despacho manual cargado por Farmacia para esa fecha
    cursor.execute("""
        SELECT medicamento_id, cantidad_despachada, farmaceutico_nombre, observaciones, actualizado_en
        FROM despacho_farmacia_diario
        WHERE fecha = DATE(?)
    """, (fecha_filtro,))
    despachos_rows = cursor.fetchall()
    despachos_map = {d["medicamento_id"]: dict(d) for d in despachos_rows}
    
    conn.close()

    # Consolidar por medicamento
    resumen = []
    for med in todos_meds:
        mid = med["id"]
        
        # Conteo tecnicos
        total_pedido = 0
        total_devuelto = 0
        
        for m in movimientos:
            if m["medicamento_id"] == mid:
                # Si no esta rechazado, computa en el balance real
                if m["control_farmacia"] != 2:
                    if m["tipo"] == "devolucion":
                        total_devuelto += m["cantidad_usada"]
                    else:
                        total_pedido += m["cantidad_usada"]
        
        neto_tecnicos = total_pedido - total_devuelto

        # Despacho manual farmacia
        despacho_info = despachos_map.get(mid, {})
        cant_despachada_farmacia = despacho_info.get("cantidad_despachada", 0)
        farm_nombre = despacho_info.get("farmaceutico_nombre", "")
        farm_obs = despacho_info.get("observaciones", "")

        # Balance: Cantidad Despachada por Farmacia vs Consumo Neto de Tecnicos
        diferencia = cant_despachada_farmacia - neto_tecnicos

        resumen.append({
            "medicamento_id": mid,
            "medicamento_nombre": med["nombre"],
            "stock_deposito": med["stock_actual"],
            "total_pedido_tecnico": total_pedido,
            "total_devuelto_tecnico": total_devuelto,
            "recuento_neto_tecnicos": neto_tecnicos,
            "cantidad_despachada_farmacia": cant_despachada_farmacia,
            "farmaceutico_nombre": farm_nombre,
            "observaciones_farmacia": farm_obs,
            "diferencia_balance": diferencia
        })

    return {
        "fecha": fecha_filtro,
        "medicamentos": resumen
    }

@app.post("/api/farmacia/despacho-diario")
def guardar_despacho_farmacia(item: DespachoFarmaciaItem, user: dict = Depends(require_farmacia_or_admin)):
    fecha_filtro = item.fecha.strip()
    if not fecha_filtro:
        raise HTTPException(status_code=400, detail="Debe indicar la fecha del despacho")
    if item.cantidad_despachada < 0:
        raise HTTPException(status_code=400, detail="La cantidad despachada no puede ser negativa")

    conn = get_db()
    cursor = conn.cursor()
    
    # Insertar o actualizar registro unico por (fecha, medicamento_id)
    cursor.execute("""
        INSERT INTO despacho_farmacia_diario (
            fecha, medicamento_id, cantidad_despachada,
            farmaceutico_id, farmaceutico_nombre, observaciones, actualizado_en
        ) VALUES (DATE(?), ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(fecha, medicamento_id) DO UPDATE SET
            cantidad_despachada = excluded.cantidad_despachada,
            farmaceutico_id = excluded.farmaceutico_id,
            farmaceutico_nombre = excluded.farmaceutico_nombre,
            observaciones = excluded.observaciones,
            actualizado_en = CURRENT_TIMESTAMP
    """, (
        fecha_filtro,
        item.medicamento_id,
        item.cantidad_despachada,
        user["id"],
        user["nombre_completo"],
        item.observaciones.strip() if item.observaciones else ""
    ))
    conn.commit()
    conn.close()
    return {"message": "Despacho manual de Farmacia guardado exitosamente"}

# --- CONTROL Y ADMINISTRACION DE USUARIOS (SUPERADMIN) ---
@app.delete("/api/admin/registros/{reg_id}")
def admin_borrar_registro(reg_id: int, reponer_stock: bool = True, admin: dict = Depends(require_admin)):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM registros_cuaderno WHERE id = ?", (reg_id,))
    reg = cursor.fetchone()
    if not reg:
        conn.close()
        raise HTTPException(status_code=404, detail="Registro no encontrado")
    
    if reponer_stock and reg["control_farmacia"] != 2:
        if reg["tipo"] == "uso":
            cursor.execute("UPDATE medicamentos SET stock_actual = stock_actual + ? WHERE id = ?", (reg["cantidad_usada"], reg["medicamento_id"]))
        else:
            cursor.execute("UPDATE medicamentos SET stock_actual = stock_actual - ? WHERE id = ?", (reg["cantidad_usada"], reg["medicamento_id"]))
    
    cursor.execute("DELETE FROM registros_cuaderno WHERE id = ?", (reg_id,))
    conn.commit()
    conn.close()
    return {"message": f"Registro #{reg_id} eliminado de la base de datos"}

@app.delete("/api/admin/medicamentos/{med_id}")
def admin_borrar_medicamento(med_id: int, admin: dict = Depends(require_admin)):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM despacho_farmacia_diario WHERE medicamento_id = ?", (med_id,))
    cursor.execute("DELETE FROM registros_cuaderno WHERE medicamento_id = ?", (med_id,))
    cursor.execute("DELETE FROM medicamentos WHERE id = ?", (med_id,))
    conn.commit()
    conn.close()
    return {"message": f"Medicamento #{med_id} y sus registros fueron eliminados"}

@app.get("/api/admin/usuarios")
def admin_get_usuarios(admin: dict = Depends(require_admin)):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, nombre_completo, rol, creado_en FROM usuarios ORDER BY id ASC")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

@app.post("/api/admin/usuarios")
def admin_crear_usuario(u: UsuarioCreate, admin: dict = Depends(require_admin)):
    username_limpio = u.username.strip().lower()
    if not username_limpio:
        raise HTTPException(status_code=400, detail="El nombre de usuario es requerido")
    if not u.nombre_completo.strip():
        raise HTTPException(status_code=400, detail="El nombre completo es requerido")
    if len(u.password) < 4:
        raise HTTPException(status_code=400, detail="La contrasena debe tener al menos 4 caracteres")
    if u.rol not in ["tecnico", "farmacia", "admin"]:
        raise HTTPException(status_code=400, detail="Rol no valido")
    
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO usuarios (username, nombre_completo, password_hash, rol)
            VALUES (?, ?, ?, ?)
        """, (username_limpio, u.nombre_completo.strip(), hash_password(u.password), u.rol))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(status_code=400, detail="El nombre de usuario ya existe en el sistema")
    conn.close()
    return {"message": f"Usuario {username_limpio} creado exitosamente con su contrasena"}

@app.put("/api/admin/usuarios/{user_id}/password")
def admin_reset_password(user_id: int, p: UsuarioUpdatePassword, admin: dict = Depends(require_admin)):
    if len(p.password_nueva) < 4:
        raise HTTPException(status_code=400, detail="La nueva contrasena debe tener al menos 4 caracteres")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, username FROM usuarios WHERE id = ?", (user_id,))
    u = cursor.fetchone()
    if not u:
        conn.close()
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    nueva_hash = hash_password(p.password_nueva)
    cursor.execute("UPDATE usuarios SET password_hash = ? WHERE id = ?", (nueva_hash, user_id))
    conn.commit()
    conn.close()
    return {"message": f"Contrasena de {u['username']} actualizada exitosamente por el Administrador"}

@app.delete("/api/admin/usuarios/{user_id}")
def admin_borrar_usuario(user_id: int, admin: dict = Depends(require_admin)):
    if user_id == admin["id"]:
        raise HTTPException(status_code=400, detail="No puedes eliminar tu propia cuenta de Administrador en uso")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM usuarios WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    return {"message": f"Usuario #{user_id} eliminado de la base de datos"}

@app.post("/api/admin/vaciar-cuaderno")
def admin_vaciar_cuaderno(admin: dict = Depends(require_admin)):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM registros_cuaderno")
    cursor.execute("DELETE FROM despacho_farmacia_diario")
    conn.commit()
    conn.close()
    return {"message": "Todos los registros del cuaderno y despachos diarios fueron eliminados"}

# --- ARCHIVOS ESTATICOS Y COMPATIBILIDAD ---
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/")
def index():
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"status": "Control Opioides HCM - Sistema Activo"}

@app.post("/api/auth/login")
def login_auth(req: LoginRequest):
    return login(req)

@app.get("/api/auth/me")
def me_auth(user: dict = Depends(get_current_user)):
    return user

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)