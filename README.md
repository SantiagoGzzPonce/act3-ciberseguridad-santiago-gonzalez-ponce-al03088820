# Act3 Ciberseguridad — Santiago Gonzalez Ponce — AL03088820

Actividad 3: seguridad en la nube (modelo IaaS), autenticación multifactor e
Infraestructura como Código. Todo corre **localmente**; nada apunta a AWS real.

| Carpeta | Contenido |
|---|---|
| [`lab-mfa/`](lab-mfa) | App Flask con MFA (contraseña + TOTP / Google Authenticator), plantillas y pruebas. |
| [`lab-s3-localstack/`](lab-s3-localstack) | Bucket S3 seguro con Terraform + LocalStack (AES-256 y 4 bloqueos de acceso público). |
| [`remediacion-iac/`](remediacion-iac) | Dockerfile fortificado (`USER appuser`), Docker Compose `read_only`, Terraform con grupo de seguridad mínimo e IAM de menor privilegio. |
| [`docs/`](docs) | Reporte (.docx), bitácora de auditoría con IA y evidencias de terminal. |

## Requisitos

- Python 3.10+
- Docker Engine/Desktop + Docker Compose v2
- Terraform ≥ 1.6
- AWS CLI v2
- Cuenta gratuita LocalStack (plan **Hobby**) — el token va en `.env`, nunca en Git
- Google Authenticator u otra app TOTP

## 1. Laboratorio MFA

```bash
cd lab-mfa
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python generate_secrets.py          # crea .env con secretos aleatorios (permisos 600)
python -m unittest discover -s tests -v
python app.py                       # http://127.0.0.1:5001
```

Flujo: `/` (usuario+contraseña) → `/verify` (código TOTP) → `/dashboard`.
`/setup` muestra la clave para registrar el autenticador; `/logout` solo acepta POST.
Con `HARDENED=true` se activan: límite de 5 intentos, anti-reutilización de códigos
y bloqueo de `/setup` después del enrolamiento.

## 2. Bucket S3 con Terraform + LocalStack

```bash
cd lab-s3-localstack
cp .env.example .env                # pega tu LOCALSTACK_AUTH_TOKEN
docker compose up -d
curl -s http://localhost:4566/_localstack/health
terraform init && terraform validate && terraform plan   # 3 recursos
terraform apply
./verificar.sh                      # cifrado, bloqueos, carga y acceso anónimo
```

## 3. Remediación con IaC

```bash
cd remediacion-iac
docker compose up -d --build        # app MFA como appuser, FS de solo lectura
docker compose exec mfa-app id      # uid=10001(appuser)
cd terraform && terraform init && terraform plan   # SG 443 + SSH /32, IAM mínimo
```

`terraform plan -var admin_cidr=0.0.0.0/0` es rechazado por una validación: el
código impide abrir SSH al mundo.

## Seguridad

- Sin tokens, contraseñas ni `*.tfstate` en el repositorio (`.gitignore`).
- Credenciales de AWS ficticias (`test/test`) y endpoint `http://localhost:4566`.
- Las capturas de evidencia no deben mostrar el token de LocalStack ni la clave TOTP.
