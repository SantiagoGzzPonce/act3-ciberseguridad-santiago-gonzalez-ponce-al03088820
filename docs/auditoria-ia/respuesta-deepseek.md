# Respuesta original de DeepSeek (sin editar)

**Prompt:** Genera una configuración en Docker Compose y una política de acceso IAM para desplegar una aplicación web en una máquina virtual de nube pública

---

Aquí tienes una configuración funcional de Docker Compose y una política de acceso IAM diseñadas para desplegar una aplicación web en una máquina virtual (VM) de una nube pública, asumiendo un proveedor como AWS por ser el más extendido en el uso de IAM. El enfoque es de mínimo privilegio, separando la identidad de la aplicación (rol de la instancia) de la identidad administrativa.

## 1. Configuración de Docker Compose

Este archivo `docker-compose.yml` define una arquitectura típica de dos capas: un proxy inverso Nginx que recibe el tráfico público y una aplicación web (ej. Node.js o Python) que corre internamente.

Puntos clave de la configuración:

* Aislamiento de red: La aplicación (`app`) no expone puertos al host; solo Nginx (`proxy`) lo hace. La comunicación ocurre en la red interna `webnet`.
* Persistencia y reinicio: Se usa `restart: unless-stopped` para que los contenedores se levanten si la VM se reinicia por mantenimiento.
* Límites de recursos: Se definen límites de CPU y memoria para evitar que un pico de tráfico consuma todos los recursos de la VM.

```yaml
version: "3.8"

services:
  # Capa de entrada: Proxy inverso Nginx
  proxy:
    image: nginx:1.27-alpine
    container_name: web-proxy
    restart: unless-stopped
    ports:
      - "80:80"   # Expone el puerto 80 de la VM al mundo
    volumes:
      - ./nginx/default.conf:/etc/nginx/conf.d/default.conf:ro
    depends_on:
      - app
    networks:
      - webnet
    deploy:
      resources:
        limits:
          cpus: '0.50'
          memory: 128M

  # Capa de aplicación: Tu servicio web
  app:
    image: mi-registro/mi-app-web:v1.0.0  # Reemplaza con tu imagen real
    container_name: web-app
    restart: unless-stopped
    expose:
      - "3000"  # Solo expuesto a la red interna, NO al host
    environment:
      - NODE_ENV=production
      - PORT=3000
    networks:
      - webnet
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 512M

networks:
  webnet:
    driver: bridge
```

Archivo de configuración de Nginx (`./nginx/default.conf`):

```nginx
server {
    listen 80;
    server_name _; # O tu dominio

    location / {
        proxy_pass http://app:3000; # Apunta al servicio 'app' en la red de Docker
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

## 2. Política de Acceso IAM (AWS)

Para una VM en AWS (instancia EC2), no debes usar claves de acceso estáticas (Access Key / Secret Key). En su lugar, debes crear un Rol IAM y adjuntarlo a la instancia EC2. La aplicación obtendrá credenciales temporales automáticamente.

La siguiente política de ejemplo asume que tu aplicación web necesita escribir logs o archivos en un bucket S3 específico (por ejemplo, para subir imágenes de usuario o backups). Se aplica el principio de mínimo privilegio: solo `PutObject` y `GetObject` sobre un bucket concreto, no `s3:*` sobre todos los recursos.

Política IAM (JSON) para el Rol de la instancia EC2:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "AccesoLimitadoAlBucketDeLaApp",
            "Effect": "Allow",
            "Action": [
                "s3:PutObject",
                "s3:GetObject",
                "s3:ListBucket"
            ],
            "Resource": [
                "arn:aws:s3:::mi-bucket-web-app-produccion",
                "arn:aws:s3:::mi-bucket-web-app-produccion/*"
            ]
        },
        {
            "Sid": "PermitirSoloLecturaDeParametrosEspecificos",
            "Effect": "Allow",
            "Action": [
                "ssm:GetParameter",
                "ssm:GetParameters"
            ],
            "Resource": "arn:aws:ssm:us-east-1:123456789012:parameter/mi-app/produccion/*"
        }
    ]
}
```

Instrucciones de aplicación:

1. En la consola de AWS IAM, crea una política nueva y pega el JSON anterior (ajustando el nombre del bucket y los IDs de cuenta/región).
2. Crea un Rol para EC2 (Trusted entity: EC2).
3. Adjunta la política que acabas de crear al Rol.
4. En la consola de EC2, selecciona tu instancia, ve a Acciones > Seguridad > Modificar rol de IAM y asigna el rol creado.

De esta forma, el código de tu aplicación (dentro del contenedor `app`) puede usar el SDK de AWS sin configurar credenciales, y si la VM es comprometida, el atacante solo tendrá acceso a ese bucket específico, no a toda tu infraestructura.

## Resumen de buenas prácticas implementadas

* Separación de responsabilidades: Nginx maneja el tráfico público; la app no está expuesta directamente.
* Mínimo privilegio en IAM: La VM no es administrador; solo puede tocar los recursos que necesita (S3 y SSM).
* Sin secretos en el código: Al usar un Rol IAM, no hay contraseñas de AWS en el `docker-compose.yml` ni en la imagen.

Si tu nube pública no es AWS, el concepto es idéntico: busca el servicio equivalente de "Roles" o "Service Accounts" para instancias (ej. GCP Service Account, Azure Managed Identity) y aplica la misma política restrictiva.
