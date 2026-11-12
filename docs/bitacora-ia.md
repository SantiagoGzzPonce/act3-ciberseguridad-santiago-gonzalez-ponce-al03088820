# Bitácora técnica — Auditoría de una configuración generada por IA

**Fecha:** 2026-11-11
**Herramienta de IA:** DeepSeek (chat web, sin contexto previo)
**Alumno:** Santiago Gonzalez Ponce — AL03088820

## 1. Prompt

> Genera una configuración en Docker Compose y una política de acceso IAM para
> desplegar una aplicación web en una máquina virtual de nube pública

## 2. Respuesta de la IA

Completa y sin editar en [`auditoria-ia/respuesta-deepseek.md`](auditoria-ia/respuesta-deepseek.md).

Resumen: un `docker-compose.yml` con dos servicios (proxy `nginx:1.27-alpine` publicado en
`80:80` y una `app` en el puerto interno 3000), un `default.conf` de Nginx solo HTTP y una
política IAM para el rol de la instancia EC2 con `s3:PutObject/GetObject/ListBucket` sobre un
bucket y `ssm:GetParameter(s)` sobre una ruta de parámetros.

## 3. Lo que la IA hizo bien

- **IAM sin comodines:** no usó `"Action": "*"`, `s3:*` ni `AdministratorAccess`; acotó los
  recursos a un bucket y a una ruta de SSM.
- **Rol de instancia en vez de llaves estáticas:** no hay Access Key / Secret Key en el código.
- **La app no se publica en el host:** usa `expose: 3000` y solo el proxy recibe tráfico.
- **Límites de CPU y memoria** y sin `docker.sock` ni `privileged: true`.

## 4. Omisiones y errores encontrados

| # | Control | ¿Omitido? | Hallazgo en la respuesta | Corrección |
|---|---|---|---|---|
| 1 | Usuario no root | **Sí** | Ningún servicio declara `user:`. `nginx:1.27-alpine` arranca como root y la imagen de la app no se sabe. | `nginxinc/nginx-unprivileged` y `user: "10001:10001"` en la app |
| 2 | FS solo lectura, `cap_drop`, `no-new-privileges` | **Sí** | Ninguno de los tres aparece. | `read_only: true` + `tmpfs`, `cap_drop: [ALL]`, `no-new-privileges:true` |
| 3 | Cifrado en tránsito (TLS) | **Sí** | Solo `listen 80`: todo el tráfico, incluidas las cookies de sesión, viaja en claro; el comentario dice "expone el puerto 80 de la VM al mundo". | Puerto 443 con TLS 1.2/1.3, HSTS y redirección 80 → 443 |
| 4 | Firewall / grupo de seguridad | **Sí** | No define reglas de red. Sin ellas, un SG creado a mano con "todo el tráfico" o SSH abierto a `0.0.0.0/0` (lo más común) queda sin control. | SG con 443/80 públicos y 22 solo desde `admin_cidr` /32 |
| 5 | IMDSv2 | **Sí** | Afirma que "si la VM es comprometida, el atacante solo tendrá acceso a ese bucket", pero sin IMDSv2 una SSRF en la app puede leer `169.254.169.254` y robar las credenciales temporales del rol. | `http_tokens = "required"`, `hop_limit = 1` |
| 6 | Divulgación de versión | **Sí** | Nginx envía `Server: nginx/1.27.x` por defecto y faltan cabeceras de seguridad. | `server_tokens off`, `X-Content-Type-Options`, `X-Frame-Options` |
| 7 | Política IAM precisa | Parcial | Mezcla `ListBucket` (aplica al bucket) con `Get/PutObject` (aplican a objetos) en un mismo bloque con ambos ARN; funciona, pero concede combinaciones sin sentido y dificulta auditar. No exige cifrado al subir. | Separar en dos statements y añadir `Deny` de `PutObject` sin cifrado |
| 8 | Secretos en texto plano | No | Usa rol IAM y SSM Parameter Store. | — |
| 9 | `docker.sock` / `privileged` | No | No los usa. | — |
| 10 | Límites de recursos | No (detalle menor) | Usa `deploy.resources` y `version: "3.8"`, que Compose v2 marca como obsoleto. | `mem_limit`, `cpus`, `pids_limit`; sin `version:` |
| 11 | Healthcheck | Sí (menor) | `depends_on` sin `condition`: el proxy arranca aunque la app no esté lista. | `healthcheck` + `condition: service_healthy` |

**Las tres omisiones típicas que pedía revisar la actividad:**
- Usuario no root: **omitido**.
- Puertos administrativos abiertos a `0.0.0.0/0`: **no lo abrió explícitamente, pero tampoco lo
  impidió**; no definió ningún firewall y publicó HTTP sin cifrar a todo el mundo.
- Permisos de administrador general: **no cometió este error**; el IAM está razonablemente acotado.

## 5. Versión corregida

Archivos en [`auditoria-ia/`](auditoria-ia/) (cada cambio marcado con `# [FIX n]`):

- [`docker-compose.corregido.yml`](auditoria-ia/docker-compose.corregido.yml)
- [`nginx-default.corregido.conf`](auditoria-ia/nginx-default.corregido.conf)
- [`politica-iam.corregida.json`](auditoria-ia/politica-iam.corregida.json)
- [`grupo-seguridad-e-imds.corregido.tf`](auditoria-ia/grupo-seguridad-e-imds.corregido.tf)

La implementación completa y validada con `terraform plan` está en
[`remediacion-iac/`](../remediacion-iac).

## 6. Justificación de las correcciones

- **Menor privilegio en el contenedor.** El rol IAM limitado protege la cuenta de nube, pero si el
  proceso corre como root dentro del contenedor, una RCE en la app da control total del contenedor
  y deja más cerca un escape al host. Usuario sin privilegios, sin capacidades y con
  `no-new-privileges` cierran esa vía.
- **Inmutabilidad.** Con `read_only: true` un intruso no puede dejar *web shells* ni modificar
  binarios; solo `/tmp` es escribible y está montado con `noexec`.
- **Cifrado en tránsito.** En nube pública el tráfico pasa por redes que el cliente no controla; sin
  TLS, credenciales y cookies de sesión se pueden interceptar.
- **El firewall es responsabilidad del cliente.** En IaaS el proveedor no decide qué puertos abrir.
  Si el código no lo declara, queda a criterio manual de quien cree la VM, que es justo el error
  humano que la IaC busca eliminar.
- **IMDSv2.** La afirmación de la IA sobre el radio de impacto solo es cierta si las credenciales
  del rol no pueden robarse; IMDSv2 con `hop_limit = 1` es lo que lo garantiza.

## 7. Conclusión

La respuesta de DeepSeek es funcional y mejor que el promedio en IAM: aplicó menor privilegio
y evitó llaves estáticas. Sin embargo, se quedó en la capa de identidad y dejó sin endurecer la de
ejecución y la de red: contenedores como root, sistema de archivos escribible, HTTP sin TLS,
ningún firewall e IMDSv1. Además afirmó un nivel de protección que su propia configuración no
garantiza. Por eso una configuración generada por IA debe tratarse como un borrador: hay que
auditarla contra una lista de control antes de desplegarla.
