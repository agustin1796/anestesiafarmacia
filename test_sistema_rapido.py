# -*- coding: utf-8 -*-
import os
import sys
import unittest
from fastapi.testclient import TestClient
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
from main import app
from database import get_db

class TestSistemaOpioidesHCM(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        # Limpiar registros para pruebas aisladas
        conn = get_db()
        c = conn.cursor()
        c.execute("DELETE FROM registros_cuaderno")
        c.execute("DELETE FROM despacho_farmacia_diario")
        conn.commit()
        conn.close()

    def test_despacho_manual_farmacia_y_balance_diario(self):
        # 1. Login Tecnico y Farmacia
        res_tec = self.client.post("/api/login", json={"username": "tecnico", "password": "tecnico123"})
        tok_tec = res_tec.json()["access_token"]
        h_tec = {"Authorization": f"Bearer {tok_tec}"}

        res_farm = self.client.post("/api/login", json={"username": "farmacia", "password": "farmacia123"})
        tok_farm = res_farm.json()["access_token"]
        h_farm = {"Authorization": f"Bearer {tok_farm}"}

        meds = self.client.get("/api/medicamentos", headers=h_tec).json()
        med_id = meds[0]["id"]

        # 2. Tecnico anota solicitudes: 10 ampollas pedidas y luego devuelve 2 no usadas
        self.client.post("/api/registros", headers=h_tec, json={
            "paciente_nombre": "Paciente Cirugia Mayor",
            "medicamento_id": med_id,
            "cantidad_usada": 10,
            "tipo": "uso"
        })
        self.client.post("/api/registros", headers=h_tec, json={
            "paciente_nombre": "Devolucion Sobrante",
            "medicamento_id": med_id,
            "cantidad_usada": 2,
            "tipo": "devolucion"
        })

        # 3. Farmacia carga manualmente su despacho del dia (10 ampollas enviadas)
        fecha_hoy = datetime.now().strftime("%Y-%m-%d")
        res_despacho = self.client.post("/api/farmacia/despacho-diario", headers=h_farm, json={
            "fecha": fecha_hoy,
            "medicamento_id": med_id,
            "cantidad_despachada": 10,
            "observaciones": "Entrega turno manana farmacia central"
        })
        self.assertEqual(res_despacho.status_code, 200)

        # 4. Consultar el Recuento Diario Consolidado
        res_rec = self.client.get(f"/api/recuento-diario?fecha={fecha_hoy}", headers=h_farm)
        self.assertEqual(res_rec.status_code, 200)
        datos = res_rec.json()
        
        item = next(m for m in datos["medicamentos"] if m["medicamento_id"] == med_id)
        
        # Tecnicos: 10 pedidas - 2 devueltas = 8 consumo neto
        self.assertEqual(item["total_pedido_tecnico"], 10)
        self.assertEqual(item["total_devuelto_tecnico"], 2)
        self.assertEqual(item["recuento_neto_tecnicos"], 8)
        
        # Farmacia manual: 10 despachadas
        self.assertEqual(item["cantidad_despachada_farmacia"], 10)
        
        # Diferencia Balance = Despachado (10) - Consumo Neto (8) = 2 (sobrante a favor)
        self.assertEqual(item["diferencia_balance"], 2)

if __name__ == "__main__":
    unittest.main()