# Dockerfile fortificado para la app MFA (paso 6.2)
# Contexto de build: ../lab-mfa   (ver docker-compose.yml)
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Usuario y grupo sin privilegios, sin shell de login ni home escribible
RUN groupadd --system --gid 10001 appuser \
 && useradd --system --uid 10001 --gid appuser --no-create-home \
            --shell /usr/sbin/nologin appuser

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Código propiedad de root y solo lectura para appuser
COPY --chown=root:root app.py ./
COPY --chown=root:root templates ./templates
COPY --chown=root:root static ./static

# Nunca ejecutar como root
USER appuser

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/')" || exit 1

# Gunicorn en lugar del servidor de desarrollo de Flask (sin debugger)
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "1", "--worker-tmp-dir", "/tmp", "app:app"]
