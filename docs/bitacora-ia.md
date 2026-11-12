# Bitácora técnica — Auditoría de una configuración generada por IA

**Fecha:** 2026-11-11
**Herramienta de IA:** _(anotar: ChatGPT / Gemini / Copilot / Claude, versión)_

## 1. Prompt

> Genera una configuración en Docker Compose y una política de acceso IAM para
> desplegar una aplicación web en una máquina virtual de nube pública

## 2. Respuesta de la IA

_(Pegar aquí la respuesta completa, sin editar.)_

## 3. Lista de verificación de omisiones comunes

| # | Control a verificar | ¿La IA lo omitió? | Corrección aplicada (archivo) |
|---|---|---|---|
| 1 | Directiva de usuario no root (`USER` / `user:`) | ☐ Sí ☐ No | `USER appuser` en `remediacion-iac/Dockerfile`; `user: "10001:10001"` en compose |
| 2 | Puertos publicados en `0.0.0.0` (p. ej. `"80:80"`, `"5432:5432"`) | ☐ Sí ☐ No | `127.0.0.1:8000:8000`; solo 443 vía proxy |
| 3 | SSH/administración abierto a `0.0.0.0/0` | ☐ Sí ☐ No | Regla 22 solo `var.admin_cidr` (/32) con `validation` que rechaza 0.0.0.0/0 |
| 4 | Política IAM con `"Action": "*"`, `"Resource": "*"` o `AdministratorAccess` | ☐ Sí ☐ No | `act3-app-s3-minimo`: solo `s3:ListBucket/GetObject/PutObject` sobre un bucket |
| 5 | Sistema de archivos de solo lectura | ☐ Sí ☐ No | `read_only: true` + `tmpfs /tmp` (noexec) |
| 6 | Capacidades y escalada (`cap_drop`, `no-new-privileges`) | ☐ Sí ☐ No | `cap_drop: [ALL]`, `no-new-privileges:true` |
| 7 | Secretos en texto plano dentro del compose | ☐ Sí ☐ No | `env_file` fuera de Git; `.env.example` sin valores reales |
| 8 | Montaje de `/var/run/docker.sock` o `privileged: true` | ☐ Sí ☐ No | No se monta; documentado en el compose |
| 9 | IMDSv2 / credenciales de la VM | ☐ Sí ☐ No | `metadata_options { http_tokens = "required", hop_limit = 1 }` |
| 10 | Límites de recursos (memoria, CPU, PIDs) | ☐ Sí ☐ No | `mem_limit`, `cpus`, `pids_limit` |

## 4. Justificación de las correcciones

- **Menor privilegio (IAM y contenedor).** Si la aplicación se compromete, el atacante
  hereda exactamente los permisos del proceso y del rol. Con `root` en el contenedor y
  `AdministratorAccess` en el rol, una RCE en la web se convierte en control de la
  cuenta de nube; con `appuser` y una política limitada a un bucket, el daño queda
  confinado.
- **Superficie de red mínima.** Los grupos de seguridad son la primera barrera que
  controla el cliente en IaaS (el proveedor no los configura por él). Un puerto de
  base de datos o SSH abierto a `0.0.0.0/0` es escaneado en minutos por bots.
- **Inmutabilidad.** `read_only: true` impide que un intruso deje *web shells*,
  modifique binarios o persista malware dentro del contenedor.
- **Secretos fuera del código.** Una clave en un compose versionado queda en el
  historial de Git aun si se borra después.
- **Validación en el propio código.** La regla `validation` de Terraform convierte la
  política "SSH nunca al mundo" en un error de compilación, no en una revisión manual.

## 5. Conclusión

_(2–3 líneas: qué tan segura fue la respuesta "por defecto" de la IA y por qué una
configuración generada por IA debe auditarse antes de desplegarse.)_
