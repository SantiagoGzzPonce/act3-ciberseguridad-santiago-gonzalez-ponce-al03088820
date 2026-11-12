"""Pruebas funcionales (diapositiva 17) + pruebas de las fallas auditadas.

Ejecutar:  python -m unittest discover -s tests -v
"""
import importlib
import os
import sys
import time
import unittest
from pathlib import Path

import pyotp

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SECRET = pyotp.random_base32()
PASSWORD = "demo-pass-123"


def load_app(hardened: bool):
    os.environ.update(DEMO_USER="estudiante", DEMO_PASSWORD=PASSWORD,
                      FLASK_SECRET_KEY="test-key", TOTP_SECRET=SECRET,
                      HARDENED="true" if hardened else "false")
    (ROOT / ".enrolled").unlink(missing_ok=True)
    import app as module
    module = importlib.reload(module)
    module.app.config["TESTING"] = True
    return module


def login(c, pwd=PASSWORD):
    return c.post("/", data={"username": "estudiante", "password": pwd})


class FuncionalesLab(unittest.TestCase):
    def setUp(self):
        self.m = load_app(hardened=False)
        self.c = self.m.app.test_client()

    def test_1_credenciales_incorrectas(self):
        r = login(self.c, "mala")
        self.assertEqual(r.status_code, 401)
        self.assertIn("Usuario o contraseña incorrectos".encode(), r.data)

    def test_2_contrasena_correcta_pide_totp(self):
        r = login(self.c)
        self.assertEqual(r.headers["Location"], "/verify")

    def test_3_totp_invalido_bloquea(self):
        login(self.c)
        r = self.c.post("/verify", data={"code": "000000"})
        self.assertEqual(r.status_code, 401)
        self.assertEqual(self.c.get("/dashboard").status_code, 302)

    def test_4_codigo_vigente_entra(self):
        login(self.c)
        r = self.c.post("/verify", data={"code": pyotp.TOTP(SECRET).now()})
        self.assertEqual(r.headers["Location"], "/dashboard")
        self.assertEqual(self.c.get("/dashboard").status_code, 200)

    def test_5_dashboard_sin_sesion(self):
        r = self.c.get("/dashboard")
        self.assertEqual(r.headers["Location"], "/")

    def test_6_logout_impide_volver(self):
        login(self.c)
        self.c.post("/verify", data={"code": pyotp.TOTP(SECRET).now()})
        self.c.post("/logout")
        self.assertEqual(self.c.get("/dashboard").status_code, 302)

    def test_7_logout_por_get_no_permitido(self):
        self.assertEqual(self.c.get("/logout").status_code, 405)


class FallasModoLab(unittest.TestCase):
    """Demuestran las fallas que se reportan en la auditoría (modo LAB)."""

    def setUp(self):
        self.m = load_app(hardened=False)
        self.c = self.m.app.test_client()

    def test_falla_A_setup_expone_secreto_solo_con_contrasena(self):
        login(self.c)  # solo factor 1
        r = self.c.get("/setup")
        self.assertEqual(r.status_code, 200)
        self.assertIn(SECRET.encode(), r.data)  # bypass total del 2FA

    def test_falla_B_sin_limite_de_intentos(self):
        login(self.c)
        codes = [r.status_code for r in
                 (self.c.post("/verify", data={"code": f"{i:06d}"}) for i in range(50))]
        self.assertNotIn(429, codes)  # nunca se bloquea: fuerza bruta posible

    def test_falla_C_reutilizacion_de_codigo(self):
        code = pyotp.TOTP(SECRET).now()
        for _ in range(2):
            c = self.m.app.test_client()
            login(c)
            r = c.post("/verify", data={"code": code})
            self.assertEqual(r.headers.get("Location"), "/dashboard")


class ControlesHardened(unittest.TestCase):
    def setUp(self):
        self.m = load_app(hardened=True)
        self.c = self.m.app.test_client()

    def tearDown(self):
        (ROOT / ".enrolled").unlink(missing_ok=True)

    def test_limite_intentos(self):
        login(self.c)
        for i in range(5):
            self.c.post("/verify", data={"code": f"{i:06d}"})
        r = self.c.post("/verify", data={"code": pyotp.TOTP(SECRET).now()})
        self.assertEqual(r.status_code, 429)

    def test_codigo_no_reutilizable(self):
        code = pyotp.TOTP(SECRET).now()
        c1 = self.m.app.test_client(); login(c1)
        self.assertEqual(c1.post("/verify", data={"code": code}).status_code, 302)
        c2 = self.m.app.test_client(); login(c2)
        self.assertEqual(c2.post("/verify", data={"code": code}).status_code, 401)

    def test_setup_bloqueado_tras_enrolar(self):
        c1 = self.m.app.test_client(); login(c1)
        c1.post("/verify", data={"code": pyotp.TOTP(SECRET).now()})
        atacante = self.m.app.test_client(); login(atacante)
        r = atacante.get("/setup")
        self.assertEqual(r.status_code, 302)


if __name__ == "__main__":
    unittest.main()
