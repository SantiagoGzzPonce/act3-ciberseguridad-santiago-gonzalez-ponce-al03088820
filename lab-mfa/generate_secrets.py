"""Genera el archivo .env con secretos aleatorios (no se sube a Git).

Usa el módulo `secrets` (CSPRNG del sistema operativo), apropiado para
claves de sesión y semillas TOTP, a diferencia de `random`.
"""
import secrets
import sys
from pathlib import Path

import pyotp

env = Path(__file__).resolve().parent / ".env"
if env.exists() and "--force" not in sys.argv:
    sys.exit(".env ya existe; usa --force para regenerarlo (invalida el autenticador).")

env.write_text(
    "DEMO_USER=estudiante\n"
    f"DEMO_PASSWORD={secrets.token_urlsafe(12)}\n"
    f"FLASK_SECRET_KEY={secrets.token_hex(32)}\n"
    f"TOTP_SECRET={pyotp.random_base32()}\n"
    "HARDENED=false\n",
    encoding="utf-8",
)
env.chmod(0o600)
print(f"Secretos escritos en {env} (permisos 600). La contraseña demo está ahí.")
