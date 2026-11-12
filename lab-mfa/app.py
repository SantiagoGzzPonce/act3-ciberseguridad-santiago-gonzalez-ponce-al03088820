"""Laboratorio MFA - Flask + PyOTP.

Factor 1: usuario + contraseña.  Factor 2: código TOTP de 6 dígitos.
Rutas: /  ->  /verify  ->  /dashboard   (+ /setup y /logout)

Modo LAB (por defecto): implementación didáctica de la guía, con las fallas
que se auditan en el reporte.
Modo HARDENED (HARDENED=true): activa los controles de remediación
(límite de intentos, anti-reutilización de códigos y /setup bloqueado tras
el enrolamiento).
"""

import hmac
import os
import re
import time
from functools import wraps
from pathlib import Path

import pyotp
from flask import (Flask, flash, redirect, render_template, request, session,
                   url_for)

# --------------------------------------------------------------------------
# Configuración y credenciales de demostración
# --------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent


def load_env_file(path: Path) -> None:
    """Carga KEY=VALUE desde .env sin sobrescribir variables ya definidas."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


load_env_file(BASE_DIR / ".env")

DEMO_USER = os.environ.get("DEMO_USER", "estudiante")
DEMO_PASSWORD = os.environ.get("DEMO_PASSWORD")
TOTP_SECRET = os.environ.get("TOTP_SECRET")
SECRET_KEY = os.environ.get("FLASK_SECRET_KEY")
HARDENED = os.environ.get("HARDENED", "false").lower() == "true"
ISSUER = "FGRLabs MFA"

if not (DEMO_PASSWORD and TOTP_SECRET and SECRET_KEY):
    raise SystemExit(
        "Faltan secretos. Ejecuta: python generate_secrets.py  (crea .env)"
    )

app = Flask(__name__)
app.config.update(
    SECRET_KEY=SECRET_KEY,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE", "false") == "true",
)
totp = pyotp.TOTP(TOTP_SECRET)

# Estado de los controles HARDENED (en memoria: suficiente para el lab)
MAX_ATTEMPTS = 5
LOCKOUT_SECONDS = 300
_failed = {"count": 0, "locked_until": 0.0}
_last_used_step = {"value": -1}
_enrolled_flag = BASE_DIR / ".enrolled"


# --------------------------------------------------------------------------
# Decorador
# --------------------------------------------------------------------------
def requires_mfa(view):
    """Solo deja pasar si la sesión completó los dos factores."""

    @wraps(view)  # conserva __name__, __doc__ (Flask usa __name__ como endpoint)
    def wrapper(*args, **kwargs):
        if not session.get("mfa_ok"):
            flash("Inicia sesión y completa el segundo factor.")
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapper


def requires_first_factor(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not session.get("pwd_ok"):
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapper


# --------------------------------------------------------------------------
# Rutas
# --------------------------------------------------------------------------
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method != "POST":
        return render_template("login.html")

    username = request.form.get("username", "")
    password = request.form.get("password", "")
    user_ok = hmac.compare_digest(username, DEMO_USER)
    pass_ok = hmac.compare_digest(password, DEMO_PASSWORD)

    if user_ok and pass_ok:
        session.clear()  # evita fijación de sesión
        session["pwd_ok"] = True
        session["user"] = username
        return redirect(url_for("verify"))

    flash("Usuario o contraseña incorrectos.")  # no revela cuál falló
    return render_template("login.html"), 401


@app.route("/verify", methods=["GET", "POST"])
@requires_first_factor
def verify():
    if request.method != "POST":
        return render_template("verify.html", hardened=HARDENED)

    if HARDENED and time.time() < _failed["locked_until"]:
        flash("Demasiados intentos. Espera unos minutos.")
        return render_template("verify.html", hardened=HARDENED), 429

    code = re.sub(r"\s+", "", request.form.get("code", ""))
    if not re.fullmatch(r"\d{6}", code):
        flash("El código debe tener 6 dígitos.")
        return render_template("verify.html", hardened=HARDENED), 400

    valid = totp.verify(code, valid_window=1)

    if valid and HARDENED:
        # Anti-replay: un código (ventana de 30 s) se acepta una sola vez
        step = _matching_step(code)
        if step is None or step <= _last_used_step["value"]:
            valid = False
        else:
            _last_used_step["value"] = step

    if valid:
        session["mfa_ok"] = True
        _failed["count"] = 0
        if HARDENED:
            _enrolled_flag.touch()
        return redirect(url_for("dashboard"))

    if HARDENED:
        _failed["count"] += 1
        if _failed["count"] >= MAX_ATTEMPTS:
            _failed["locked_until"] = time.time() + LOCKOUT_SECONDS
            _failed["count"] = 0
    flash("Código inválido o expirado.")
    return render_template("verify.html", hardened=HARDENED), 401


def _matching_step(code: str):
    now = int(time.time()) // totp.interval
    for step in (now - 1, now, now + 1):
        if hmac.compare_digest(totp.at(step * totp.interval), code):
            return step
    return None


@app.route("/setup")
@requires_first_factor
def setup():
    if HARDENED and _enrolled_flag.exists() and not session.get("mfa_ok"):
        flash("El autenticador ya fue registrado. Contacta al administrador.")
        return redirect(url_for("verify"))
    uri = totp.provisioning_uri(name=session.get("user"), issuer_name=ISSUER)
    return render_template("setup.html", uri=uri, secret=TOTP_SECRET)


@app.route("/dashboard")
@requires_mfa
def dashboard():
    return render_template("dashboard.html", user=session.get("user"))


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("Sesión cerrada.")
    return redirect(url_for("login"))


@app.after_request
def security_headers(resp):
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Cache-Control"] = "no-store"
    return resp


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5001"))
    # Solo localhost y sin debug: el depurador de Werkzeug permite ejecutar código
    app.run(host=os.environ.get("HOST", "127.0.0.1"), port=port, debug=False)

