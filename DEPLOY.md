# 🚀 Guía de Despliegue - Sistema de Postulaciones RRHH

> **Versión**: 1.0 | **Última actualización**: 19-11-2025
> **Repositorio SSH**: git@github.com:mbenenati12/Sistema-Postulaciones-Def.git
> **Repositorio HTTPS**: https://github.com/mbenenati12/Sistema-Postulaciones-Def.git

Esta guía documenta el proceso completo para configurar y desplegar el Sistema de Postulaciones en el servidor AWS EC2 compartido.

---

## 📋 Información del Ambiente

### Ambiente PRODUCCIÓN

| Componente              | Detalle                                                 |
| ----------------------- | ------------------------------------------------------- |
| **Propósito**           | Sistema de postulaciones de RRHH - Clínica de Cuyo     |
| **Rama Git**            | `main`                                                  |
| **URL Dominio**         | `https://postulaciones.clinicadecuyo.com.ar/`          |
| **Dir. Código**         | `/srv/postulaciones-app`                                |
| **Puerto Local**        | `5001`                                                  |
| **Archivo Config**      | `.env` (en servidor)                                    |
| **Servicio Systemd**    | `postulaciones.service`                                 |
| **Logs Aplicación**     | `/var/log/postulaciones/app.log`                        |
| **Logs Nginx**          | `/var/log/nginx/postulaciones_access.log`               |
| **Python**              | Python 3.10+                                            |
| **WSGI Server**         | Gunicorn                                                |

### Servidor

| Componente       | Detalle                                 |
| ---------------- | --------------------------------------- |
| **Servidor**     | AWS EC2 - Ubuntu 22.04                  |
| **IP Privada**   | `172.31.89.113`                         |
| **IP Pública**   | `34.202.40.63`                          |
| **Web Server**   | Nginx (configuración unificada)         |
| **Config Nginx** | `/etc/nginx/sites-enabled/00-apps-main` |

---

## 🎯 Stack Tecnológico

- **Backend**: Flask 3.1.1 (Python)
- **Database**: Supabase (PostgreSQL)
- **File Storage**: Supabase Storage + fallback local
- **Bot Protection**: Cloudflare Turnstile
- **WSGI Server**: Gunicorn
- **Web Server**: Nginx (reverse proxy)
- **Process Manager**: systemd

---

## 🔧 CONFIGURACIÓN INICIAL (Primera vez solamente)

> **⚠️ NOTA**: Esta sección solo se ejecuta UNA VEZ durante la primera instalación. Para actualizaciones posteriores, ir a la sección "DESPLIEGUE DE ACTUALIZACIONES".

### **PASO 1: Preparación del Servidor**

#### 1.1 Conectar al Servidor

```bash
# Conectar al servidor EC2
ssh ubuntu@172.31.89.113
```

#### 1.2 Instalar Dependencias del Sistema

```bash
# Actualizar sistema
sudo apt update && sudo apt upgrade -y

# Instalar Python y herramientas (funciona con Python 3.8+)
sudo apt install -y python3 python3-venv python3-pip git

# Verificar versión de Python
python3 --version  # Debe ser 3.8 o superior
pip3 --version
git --version
```

#### 1.3 Crear Directorios

```bash
# Crear directorio para la aplicación
sudo mkdir -p /srv/postulaciones-app
sudo chown ubuntu:ubuntu /srv/postulaciones-app

# Crear directorio para logs
sudo mkdir -p /var/log/postulaciones
sudo chown ubuntu:ubuntu /var/log/postulaciones

# Crear directorio para uploads (fallback)
sudo mkdir -p /srv/postulaciones-app/uploads
sudo chown ubuntu:ubuntu /srv/postulaciones-app/uploads
```

---

### **PASO 2: Clonar Repositorio**

```bash
# Navegar al directorio
cd /srv/postulaciones-app

# Clonar repositorio con SSH (recomendado)
git clone git@github.com:mbenenati12/Sistema-Postulaciones-Def.git .

# O si usas HTTPS:
# git clone https://github.com/mbenenati12/Sistema-Postulaciones-Def.git .

# Verificar
ls -la
git branch
```

---

### **PASO 3: Configurar Entorno Python**

#### 3.1 Crear Virtual Environment

```bash
cd /srv/postulaciones-app

# Crear virtualenv
python3 -m venv venv

# Activar virtualenv
source venv/bin/activate

# Verificar que estamos en el venv
which python  # Debe mostrar /srv/postulaciones-app/venv/bin/python
```

#### 3.2 Instalar Dependencias Python

```bash
# Con el venv activado
pip install --upgrade pip

# Instalar dependencias principales
pip install Flask==3.1.1 python-dotenv==1.0.1 Werkzeug==3.1.3
pip install supabase==2.3.4
pip install gunicorn==21.2.0

# Verificar instalación
pip list

# Guardar requirements para futuras instalaciones
pip freeze > requirements.txt
```

---

### **PASO 4: Configurar Variables de Entorno**

```bash
cd /srv/postulaciones-app

# Crear archivo .env (copiar desde local o crear manualmente)
nano .env
```

**Contenido del archivo .env:**

```bash
# ========================================
# Sistema de Postulaciones - Configuración
# ========================================

# Flask Configuration
SECRET_KEY=julitocarolumati
PORT=5001

# Supabase Database
SUPABASE_URL=https://lmexoahyxobbycwyhrac.supabase.co
SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxtZXhvYWh5eG9iYnljd3locmFjIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1NjkyMzAxNCwiZXhwIjoyMDcyNDk5MDE0fQ.hhBQ4MKujuKSLvNppZRHii4_32cjA55CI7qa6aOW2ls

# Admin Credentials
ADMIN_USER=rrhh
ADMIN_PASSWORD=Clinica2021

# Cloudflare Turnstile (Bot Protection)
TURNSTILE_SITE_KEY=0x4AAAAAAB221Y9KYrQW9eWq
TURNSTILE_SECRET_KEY=0x4AAAAAAB221aquY905tbs0JkvHeMWFDe8
TURNSTILE_ENABLED=true

# Environment
FLASK_ENV=production
```

```bash
# Guardar con Ctrl+O, Enter, Ctrl+X

# Proteger el archivo (permisos restrictivos)
chmod 600 .env

# Verificar
cat .env
```

---

### **PASO 5: Probar la Aplicación**

```bash
cd /srv/postulaciones-app
source venv/bin/activate

# Probar con Flask development server
python app.py

# Debe mostrar:
# * Running on http://0.0.0.0:5001

# En otra terminal SSH, probar:
curl http://localhost:5001/

# Debe devolver HTML de la página principal

# Detener con Ctrl+C
```

---

### **PASO 6: Configurar Gunicorn**

#### 6.1 Crear archivo de configuración

```bash
nano /srv/postulaciones-app/gunicorn_config.py
```

**Contenido:**

```python
# Gunicorn configuration file
import multiprocessing
import os

# Server socket
bind = f"127.0.0.1:{os.getenv('PORT', '5001')}"
backlog = 2048

# Worker processes
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = 'sync'
worker_connections = 1000
timeout = 120
keepalive = 5

# Logging
accesslog = '/var/log/postulaciones/access.log'
errorlog = '/var/log/postulaciones/error.log'
loglevel = 'info'
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'

# Process naming
proc_name = 'postulaciones-app'

# Server mechanics
daemon = False
pidfile = '/tmp/postulaciones.pid'
umask = 0
user = None
group = None
tmp_upload_dir = None

# Security
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190
```

```bash
# Guardar y cerrar
chmod 644 /srv/postulaciones-app/gunicorn_config.py
```

#### 6.2 Probar Gunicorn

```bash
cd /srv/postulaciones-app
source venv/bin/activate

# Ejecutar gunicorn manualmente
gunicorn --config gunicorn_config.py app:app

# En otra terminal, probar:
curl http://localhost:5001/

# Si funciona, detener con Ctrl+C
```

---

### **PASO 7: Configurar Servicio Systemd**

```bash
sudo nano /etc/systemd/system/postulaciones.service
```

**Contenido:**

```ini
[Unit]
Description=Sistema de Postulaciones RRHH - Clínica de Cuyo
After=network.target

[Service]
Type=notify
User=ubuntu
Group=ubuntu
WorkingDirectory=/srv/postulaciones-app
Environment="PATH=/srv/postulaciones-app/venv/bin"
EnvironmentFile=/srv/postulaciones-app/.env
ExecStart=/srv/postulaciones-app/venv/bin/gunicorn --config gunicorn_config.py app:app
ExecReload=/bin/kill -s HUP $MAINPID
KillMode=mixed
TimeoutStopSec=5
PrivateTmp=true
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# Guardar y cerrar

# Recargar systemd
sudo systemctl daemon-reload

# Habilitar el servicio (auto-start en boot)
sudo systemctl enable postulaciones.service

# Iniciar el servicio
sudo systemctl start postulaciones.service

# Verificar estado
sudo systemctl status postulaciones.service

# Debe mostrar "active (running)"
```

#### 7.1 Comandos útiles del servicio

```bash
# Ver estado
sudo systemctl status postulaciones

# Iniciar
sudo systemctl start postulaciones

# Detener
sudo systemctl stop postulaciones

# Reiniciar
sudo systemctl restart postulaciones

# Ver logs en tiempo real
sudo journalctl -u postulaciones -f

# Ver últimas 50 líneas de logs
sudo journalctl -u postulaciones -n 50
```

---

### **PASO 8: Configurar Nginx**

#### 8.1 Editar configuración de Nginx

```bash
sudo nano /etc/nginx/sites-enabled/00-apps-main
```

**Agregar el siguiente bloque AL FINAL del archivo (antes de cerrar):**

```nginx
# Sistema de Postulaciones RRHH
server {
    listen 80;
    server_name postulaciones.clinicadecuyo.com.ar www.postulaciones.clinicadecuyo.com.ar;

    # Logs específicos
    access_log /var/log/nginx/postulaciones_access.log;
    error_log /var/log/nginx/postulaciones_error.log;

    # Client max body size (para uploads de CVs)
    client_max_body_size 10M;

    # Timeout configuration
    proxy_connect_timeout 120s;
    proxy_send_timeout 120s;
    proxy_read_timeout 120s;

    # Proxy hacia la aplicación Flask
    location / {
        proxy_pass http://127.0.0.1:5001;
        proxy_http_version 1.1;

        # Headers necesarios
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket support (por si acaso)
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        # No cache para la app principal
        proxy_cache_bypass $http_upgrade;
    }

    # Servir archivos estáticos directamente (si existen)
    location /static/ {
        alias /srv/postulaciones-app/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # Headers de seguridad
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
}
```

#### 8.2 Verificar y aplicar configuración

```bash
# Verificar sintaxis de Nginx
sudo nginx -t

# Debe devolver:
# nginx: configuration file /etc/nginx/nginx.conf test is successful

# Si hay errores, revisar la configuración

# Recargar Nginx
sudo systemctl reload nginx

# Verificar estado
sudo systemctl status nginx
```

---

### **PASO 9: Configurar DNS**

> **⚠️ IMPORTANTE**: Este paso debe realizarse en el panel de control del proveedor de DNS (Route 53, Cloudflare, etc.)

**Crear registro A:**

- **Host/Name**: `postulaciones.clinicadecuyo.com.ar`
- **Type**: `A`
- **Value**: `34.202.40.63` (IP pública del servidor)
- **TTL**: `300` (5 minutos)

**Esperar propagación del DNS (5-30 minutos):**

```bash
# Verificar desde tu máquina local
nslookup postulaciones.clinicadecuyo.com.ar

# Debe devolver la IP 34.202.40.63
```

---

### **PASO 10: Verificación Final**

#### 10.1 Desde el servidor

```bash
# Verificar que el servicio está corriendo
sudo systemctl status postulaciones

# Verificar puerto local
curl http://localhost:5001/

# Debe devolver HTML

# Verificar nginx
curl -H "Host: postulaciones.clinicadecuyo.com.ar" http://localhost/

# Debe devolver HTML
```

#### 10.2 Desde tu máquina local

```bash
# Probar conectividad
curl -I http://postulaciones.clinicadecuyo.com.ar/

# Debe devolver: HTTP/1.1 200 OK
```

#### 10.3 En el navegador

1. Abrir: `http://postulaciones.clinicadecuyo.com.ar/`
2. Debe cargar la página principal con las vacantes
3. Probar formulario de postulación
4. Probar login admin: `http://postulaciones.clinicadecuyo.com.ar/admin/login`
   - Usuario: `rrhh`
   - Password: `Clinica2021`

---

## 🔄 DESPLIEGUE DE ACTUALIZACIONES

> **⚠️ Usar esta sección para todas las actualizaciones después de la configuración inicial**

### **PASO 1: Preparación Local**

#### 1.1 Commit y Push de Cambios

```bash
# En tu máquina local
cd /Users/matiasgonzalez/Library/CloudStorage/OneDrive-CLINICADECUYOSA/Documentos/Desarrollos/RRHH/Sistema-Postulaciones-Def

# Verificar cambios
git status

# Agregar cambios
git add .

# Commit con mensaje descriptivo
git commit -m "feat: descripción de los cambios"

# Push a main
git push origin main

# Verificar que el push fue exitoso
git log --oneline -3
```

---

### **PASO 2: Actualizar en Servidor**

#### 2.1 Conectar al Servidor

```bash
ssh ubuntu@172.31.89.113
```

#### 2.2 Actualizar Código

```bash
# Navegar al directorio
cd /srv/postulaciones-app

# Verificar rama actual
git branch

# Obtener últimos cambios
git fetch origin
git pull origin main

# Verificar que se obtuvieron los cambios
git log --oneline -5
```

#### 2.3 Actualizar Dependencias (si cambiaron)

```bash
# Activar virtualenv
source venv/bin/activate

# Actualizar dependencias
pip install -r requirements.txt

# O instalar manualmente si agregaste nuevas
# pip install nueva-libreria==version
```

#### 2.4 Verificar Configuración

```bash
# Verificar que .env está correcto
cat .env | grep -E "SUPABASE_URL|ADMIN_USER|PORT"

# Verificar permisos de uploads
ls -la uploads/
```

#### 2.5 Reiniciar Servicio

```bash
# Reiniciar la aplicación
sudo systemctl restart postulaciones

# Verificar que arrancó correctamente
sudo systemctl status postulaciones

# Debe mostrar "active (running)"

# Ver logs en tiempo real (Ctrl+C para salir)
sudo journalctl -u postulaciones -f
```

#### 2.6 Verificación

```bash
# Probar desde el servidor
curl http://localhost:5001/

# Debe devolver HTML actualizado

# Verificar logs de errores
tail -50 /var/log/postulaciones/error.log
```

#### 2.7 Verificación Remota

```bash
# Desde tu máquina local
curl -I http://postulaciones.clinicadecuyo.com.ar/

# O abrir en navegador (limpiar cache con Ctrl+F5):
# http://postulaciones.clinicadecuyo.com.ar/
```

---

## 🐛 Troubleshooting

### Error: Servicio no arranca

```bash
# Ver logs del servicio
sudo journalctl -u postulaciones -n 100 --no-pager

# Ver logs de la aplicación
tail -100 /var/log/postulaciones/error.log

# Verificar que el virtualenv está correcto
ls -la /srv/postulaciones-app/venv/

# Verificar permisos
ls -la /srv/postulaciones-app/

# Probar manualmente
cd /srv/postulaciones-app
source venv/bin/activate
python app.py
```

### Error: 502 Bad Gateway

```bash
# Verificar que el servicio está corriendo
sudo systemctl status postulaciones

# Si no está corriendo, iniciar
sudo systemctl start postulaciones

# Verificar puerto
netstat -tlnp | grep 5001

# Verificar nginx
sudo nginx -t
sudo systemctl status nginx

# Ver logs de nginx
sudo tail -50 /var/log/nginx/postulaciones_error.log
```

### Error: 404 Not Found

```bash
# Verificar configuración de nginx
sudo cat /etc/nginx/sites-enabled/00-apps-main | grep -A 30 "postulaciones.clinicadecuyo"

# Verificar que nginx está escuchando
sudo netstat -tlnp | grep nginx

# Recargar nginx
sudo systemctl reload nginx
```

### Error: Variables de entorno no funcionan

```bash
# Verificar archivo .env
cat /srv/postulaciones-app/.env

# Verificar permisos
ls -la /srv/postulaciones-app/.env

# Reiniciar servicio para recargar variables
sudo systemctl restart postulaciones

# Verificar que el servicio lee el .env
sudo systemctl show postulaciones | grep Environment
```

### Error: Uploads de CVs fallan

```bash
# Verificar directorio uploads
ls -la /srv/postulaciones-app/uploads/

# Verificar permisos
sudo chown -R ubuntu:ubuntu /srv/postulaciones-app/uploads/
sudo chmod -R 755 /srv/postulaciones-app/uploads/

# Verificar tamaño máximo en nginx
grep "client_max_body_size" /etc/nginx/sites-enabled/00-apps-main

# Debe ser al menos 10M
```

### Error: Supabase no conecta

```bash
# Verificar credenciales
grep SUPABASE /srv/postulaciones-app/.env

# Probar conexión manualmente
cd /srv/postulaciones-app
source venv/bin/activate
python test_upload_and_insert.py

# Ver logs de la aplicación
tail -100 /var/log/postulaciones/error.log
```

### Rollback Rápido

```bash
# Ver commits recientes
cd /srv/postulaciones-app
git log --oneline -10

# Volver a un commit anterior
git checkout [COMMIT_HASH]

# Reiniciar servicio
sudo systemctl restart postulaciones

# Verificar
sudo systemctl status postulaciones

# Volver a main cuando esté listo
git checkout main
sudo systemctl restart postulaciones
```

---

## 📊 Monitoreo y Logs

### Ver Logs en Tiempo Real

**Logs de la aplicación (Gunicorn):**

```bash
# Logs de acceso
tail -f /var/log/postulaciones/access.log

# Logs de errores
tail -f /var/log/postulaciones/error.log

# Logs del servicio systemd
sudo journalctl -u postulaciones -f
```

**Logs de Nginx:**

```bash
# Logs de acceso
sudo tail -f /var/log/nginx/postulaciones_access.log

# Logs de errores
sudo tail -f /var/log/nginx/postulaciones_error.log

# Nginx general
sudo journalctl -u nginx -f
```

### Comandos de Monitoreo

```bash
# Estado del servicio
sudo systemctl status postulaciones

# Recursos del servidor
htop

# Espacio en disco
df -h

# Verificar puerto
netstat -tlnp | grep 5001

# Procesos de Gunicorn
ps aux | grep gunicorn

# Cantidad de workers activos
ps aux | grep gunicorn | wc -l
```

### Analizar Logs

```bash
# Errores recientes
grep -i error /var/log/postulaciones/error.log | tail -50

# Requests con error 500
grep " 500 " /var/log/postulaciones/access.log | tail -20

# IPs más activas
awk '{print $1}' /var/log/nginx/postulaciones_access.log | sort | uniq -c | sort -rn | head -10

# Rutas más accedidas
awk '{print $7}' /var/log/nginx/postulaciones_access.log | sort | uniq -c | sort -rn | head -10
```

---

## 🚀 Script de Despliegue Rápido (Opcional)

```bash
# Crear script
nano /home/ubuntu/deploy-postulaciones.sh
```

**Contenido:**

```bash
#!/bin/bash
# Script de despliegue - Sistema de Postulaciones

set -e  # Detener en errores

echo "🚀 Iniciando despliegue de Sistema de Postulaciones..."

APP_DIR="/srv/postulaciones-app"

cd $APP_DIR

echo "📥 Obteniendo últimos cambios..."
git fetch origin && git pull origin main

echo "📦 Activando virtualenv..."
source venv/bin/activate

echo "📦 Actualizando dependencias..."
pip install -q -r requirements.txt 2>/dev/null || echo "⚠️  Sin requirements.txt o ya actualizadas"

echo "🔄 Reiniciando servicio..."
sudo systemctl restart postulaciones

echo "⏳ Esperando que el servicio arranque..."
sleep 3

echo "✅ Verificando estado..."
sudo systemctl status postulaciones --no-pager | head -10

echo ""
echo "✅ Despliegue completado!"
echo "🌐 URL: http://postulaciones.clinicadecuyo.com.ar/"
echo "📊 Ver logs: sudo journalctl -u postulaciones -f"
```

```bash
# Dar permisos de ejecución
chmod +x /home/ubuntu/deploy-postulaciones.sh

# Ejecutar cuando necesites desplegar
/home/ubuntu/deploy-postulaciones.sh
```

---

## ✅ Checklist de Despliegue

### Primera Instalación

- [ ] Servidor actualizado y dependencias instaladas
- [ ] Directorios creados (/srv/postulaciones-app, /var/log/postulaciones)
- [ ] Repositorio clonado
- [ ] Virtualenv creado y activado
- [ ] Dependencias Python instaladas
- [ ] Archivo `.env` configurado con credenciales correctas
- [ ] Aplicación probada manualmente con `python app.py`
- [ ] Gunicorn configurado y probado
- [ ] Servicio systemd creado y habilitado
- [ ] Nginx configurado con bloque server
- [ ] DNS configurado (registro A)
- [ ] Servicio arrancando correctamente
- [ ] URL accesible desde navegador
- [ ] Login admin funciona
- [ ] Formulario de postulación funciona
- [ ] Upload de CV funciona

### Actualizaciones

- [ ] Cambios commiteados y pusheados a `main`
- [ ] Git pull ejecutado en servidor
- [ ] Dependencias actualizadas (si aplica)
- [ ] Archivo `.env` verificado
- [ ] Servicio reiniciado
- [ ] Servicio arrancando sin errores
- [ ] URL accesible
- [ ] Funcionalidades clave probadas
- [ ] Logs sin errores críticos

---

## 📝 Notas Importantes

1. **🔒 Seguridad**:
   - El archivo `.env` NO debe commitarse a git (está en `.gitignore`)
   - Mantener permisos restrictivos: `chmod 600 .env`
   - Considerar implementar HTTPS con Let's Encrypt (ver sección SSL)

2. **📊 Performance**:
   - Gunicorn usa múltiples workers (CPU * 2 + 1)
   - Nginx hace buffering y sirve archivos estáticos
   - Considerar ajustar timeouts según uso real

3. **💾 Backups**:
   - La base de datos está en Supabase (hacer backups periódicos)
   - Los CVs se almacenan en Supabase Storage
   - Considerar backup del código: `/srv/postulaciones-app`

4. **🔄 Updates**:
   - Probar cambios localmente antes de desplegar
   - Revisar logs después de cada despliegue
   - Mantener versiones en git con tags

5. **🕐 Tiempo estimado**:
   - Primera instalación: 30-45 minutos
   - Actualizaciones: 5-10 minutos

---

## 🔐 Configuración SSL/HTTPS (Opcional pero Recomendado)

### Instalar Certbot

```bash
# Instalar certbot
sudo apt install -y certbot python3-certbot-nginx

# Obtener certificado SSL
sudo certbot --nginx -d postulaciones.clinicadecuyo.com.ar

# Seguir las instrucciones interactivas
# Elegir redirección automática HTTP -> HTTPS

# Verificar renovación automática
sudo certbot renew --dry-run

# El certificado se renovará automáticamente
```

### Verificar HTTPS

```bash
# Después de instalar SSL, verificar
curl -I https://postulaciones.clinicadecuyo.com.ar/

# Debe devolver: HTTP/2 200
```

---

## 📧 Contactos y Referencias

| Situación                     | Acción                                               |
| ----------------------------- | ---------------------------------------------------- |
| **Servidor inaccesible**      | Verificar estado EC2 en AWS Console                  |
| **Nginx caído**               | `sudo systemctl restart nginx`                       |
| **Servicio caído**            | `sudo systemctl restart postulaciones`               |
| **Error en logs**             | `sudo journalctl -u postulaciones -n 100`            |
| **Rollback necesario**        | `git checkout [COMMIT_HASH]` + restart               |
| **Problemas con Supabase**    | Verificar credenciales en `.env`                     |
| **Upload de CV falla**        | Verificar permisos en `/srv/postulaciones-app/uploads/` |
| **502 Bad Gateway**           | Verificar que servicio está corriendo en puerto 5001 |

---

## 📚 Documentación Adicional

- **Flask**: https://flask.palletsprojects.com/
- **Gunicorn**: https://docs.gunicorn.org/
- **Nginx**: https://nginx.org/en/docs/
- **Supabase**: https://supabase.com/docs
- **Systemd**: https://www.freedesktop.org/software/systemd/man/

---

> **Creado**: 19-11-2025
> **Versión**: 1.0
> **Mantenido por**: Equipo IT - Clínica de Cuyo
