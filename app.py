import os
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
from werkzeug.utils import secure_filename
import urllib.request
import urllib.parse
import json

try:
    # Cargar .env si existe
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass

try:
    from supabase import create_client, Client  # type: ignore
except Exception:  # pragma: no cover - si no está instalado, seguimos
    create_client = None  # type: ignore
    Client = Any  # type: ignore


# ==========================
# App y configuración básica
# ==========================
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret-key")

SUPABASE_URL = (os.getenv("SUPABASE_URL") or "").strip().rstrip("/")
SUPABASE_KEY = (os.getenv("SUPABASE_KEY") or "").strip()
SUPABASE_ENABLED = bool(SUPABASE_URL and SUPABASE_KEY and create_client)
BUCKET = "cvs"

# Turnstile (Cloudflare)
TURNSTILE_SITE_KEY = os.getenv("TURNSTILE_SITE_KEY", "0x4AAAAAAB221Y9KYrQW9eWq")
TURNSTILE_SECRET_KEY = os.getenv("TURNSTILE_SECRET_KEY", "0x4AAAAAAB221aquY905tbs0JkvHeMWFDe8")
TURNSTILE_ENABLED = (os.getenv("TURNSTILE_ENABLED", "true").strip().lower() not in {"0", "false", "no"})

supabase: Optional[Client]
if SUPABASE_ENABLED:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)  # type: ignore
    except Exception:
        supabase = None
else:
    supabase = None


# ==========================
# Helpers
# ==========================
def normalizar_checkbox(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    text = str(value).strip().lower()
    return text in {"si", "sí", "true", "1", "on", "yes"}


def is_pgrst204_error(exc: Exception) -> bool:
    msg = str(exc) if exc else ""
    return "PGRST204" in msg or "schema cache" in msg


def _fallback_localidades() -> List[Dict[str, Any]]:
    # Departamentos de Mendoza para modo sin conexión
    nombres = [
        "Capital",
        "Godoy Cruz",
        "Guaymallén",
        "Las Heras",
        "Maipú",
        "Luján de Cuyo",
        "Lavalle",
        "San Martín",
        "Rivadavia",
        "Junín",
        "Santa Rosa",
        "La Paz",
        "Tunuyán",
        "Tupungato",
        "San Carlos",
        "San Rafael",
        "General Alvear",
        "Malargüe",
    ]
    return [{"id": i + 1, "nombre": n} for i, n in enumerate(nombres)]


def _fallback_areas() -> List[Dict[str, Any]]:
    return [
        {"id": 1, "nombre": "Recepción"},
        {"id": 2, "nombre": "Administración"},
        {"id": 3, "nombre": "Cocina"},
        {"id": 4, "nombre": "Mecánica"},
    ]


def cargar_catalogos() -> Tuple[Dict[Any, str], Dict[Any, str]]:
    """Devuelve (map_localidades, map_areas).

    Intenta leer de Supabase; si falla, devuelve valores por defecto.
    """
    loc_map: Dict[Any, str] = {}
    area_map: Dict[Any, str] = {}

    if supabase is not None:
        try:
            loc_res = supabase.table("localidades").select("id,nombre").execute()
            for row in (loc_res.data or []):
                loc_map[row.get("id")] = row.get("nombre")
        except Exception:
            pass
        try:
            area_res = supabase.table("areas").select("id,nombre").execute()
            for row in (area_res.data or []):
                area_map[row.get("id")] = row.get("nombre")
        except Exception:
            pass

    if not loc_map:
        for loc in _fallback_localidades():
            loc_map[loc["id"]] = loc["nombre"]
    if not area_map:
        for a in _fallback_areas():
            area_map[a["id"]] = a["nombre"]

    return loc_map, area_map


def cargar_opciones_postulacion() -> Tuple[List[str], List[str], List[str]]:
    """Devuelve (areas, disponibilidades, localidades) como listas de strings.

    No depende de la conexión; usa catálogo si está disponible.
    """
    loc_map, area_map = cargar_catalogos()
    areas = list(area_map.values()) or ["Recepción", "Administración", "Cocina"]
    disponibilidades = ["Full time", "Part time", "Fines de semana"]
    localidades = list(loc_map.values()) or ["Mendoza", "Godoy Cruz", "Guaymallén"]
    return areas, disponibilidades, localidades


def get_areas_preferencia() -> List[str]:
    fallback = [
        "Administración",
        "Recepción",
        "Enfermería",
        "Mantenimiento",
        "Limpieza",
        "Recursos Humanos",
        "Farmacia",
    ]
    # Unificar catálogo: combinar tabla "areas" y "areas_preferencia" si existen
    if supabase is None:
        # Si no hay supabase, usar catálogo local + fallback
        _, area_map = cargar_catalogos()
        base = list(area_map.values())
        final = sorted({*(base or []), *fallback})
        return final
    try:
        nombres_set = set()
        # 1) Áreas operativas
        try:
            res_areas = supabase.table("areas").select("nombre").order("nombre", desc=False).execute()
            for row in (res_areas.data or []):
                nombre = row.get("nombre")
                if nombre:
                    nombres_set.add(nombre)
        except Exception:
            pass
        # 2) Áreas de preferencia
        try:
            res_pref = supabase.table("areas_preferencia").select("nombre").order("nombre", desc=False).execute()
            for row in (res_pref.data or []):
                nombre = row.get("nombre")
                if nombre:
                    nombres_set.add(nombre)
        except Exception:
            pass
        # 3) Fallback por si ambas vacían
        if not nombres_set:
            _, area_map = cargar_catalogos()
            for v in area_map.values():
                if v:
                    nombres_set.add(v)
        # 4) Unir con fallback estático y devolver ordenado
        if not nombres_set:
            nombres_set.update(fallback)
        return sorted(nombres_set)
    except Exception:
        return fallback


def get_areas_catalogo() -> List[Dict[str, Any]]:
    """Devuelve lista de áreas como [{id, nombre}] priorizando Supabase clásica.

    Orden de preferencia:
    1) Tabla areas_preferencia (esquema original)
    2) Tabla areas (si existe)
    3) Catálogo local / fallback
    """
    # 1) Preferir areas_preferencia
    if supabase is not None:
        try:
            pref = supabase.table("areas_preferencia").select("id,nombre").order("nombre", desc=False).execute()
            resultados = [
                {"id": row.get("id"), "nombre": row.get("nombre")}
                for row in (pref.data or [])
                if row.get("nombre")
            ]
            if resultados:
                return resultados
        except Exception:
            pass
        # 2) Fallback a areas
        try:
            res = supabase.table("areas").select("id,nombre").order("nombre", desc=False).execute()
            resultados = [
                {"id": row.get("id"), "nombre": row.get("nombre")}
                for row in (res.data or [])
                if row.get("nombre")
            ]
            if resultados:
                return resultados
        except Exception:
            pass
    # 3) Catálogo local / fallback
    _, area_map = cargar_catalogos()
    if area_map:
        out: List[Dict[str, Any]] = []
        for k, v in area_map.items():
            out.append({"id": k, "nombre": v})
        out.sort(key=lambda x: (str(x.get("nombre") or "").lower()))
        return out
    return [{"id": a.get("id"), "nombre": a.get("nombre")} for a in _fallback_areas()]


def resolver_area_desde_form(valor: str) -> Tuple[str, Optional[Any]]:
    """Convierte un valor de formulario (id numérico, UUID o nombre) a (nombre, id opcional)."""
    if not valor:
        return "", None
    val = valor.strip()
    # Si parece un ID numérico o UUID, buscar nombre en Supabase o catálogo
    def _looks_like_uuid(s: str) -> bool:
        s = s.strip().lower()
        return len(s) in {32, 36} and ("-" in s or s.isalnum())

    if val.isdigit() or _looks_like_uuid(val):
        area_id: Any = int(val) if val.isdigit() else val
        # Intentar Supabase: primero areas_preferencia (esquema original), luego areas
        if supabase is not None:
            try:
                rowp = supabase.table("areas_preferencia").select("id,nombre").eq("id", area_id).single().execute()
                data = getattr(rowp, "data", None) or None
                if data and data.get("nombre"):
                    return str(data.get("nombre")), data.get("id")
            except Exception:
                pass
            try:
                row = supabase.table("areas").select("id,nombre").eq("id", area_id).single().execute()
                data = getattr(row, "data", None) or None
                if data and data.get("nombre"):
                    return str(data.get("nombre")), data.get("id")
            except Exception:
                pass
        # Fallback catálogo local
        _, area_map = cargar_catalogos()
        nombre = area_map.get(area_id) if isinstance(area_id, int) else None
        if nombre:
            return str(nombre), area_id
        return val, area_id if isinstance(area_id, int) else None
    # Si vino nombre textual, devolver como nombre; opcionalmente intentar mapear id
    nombre_txt = val
    # Intentar obtener id por nombre en Supabase (preferencia -> areas)
    if supabase is not None:
        try:
            rp = supabase.table("areas_preferencia").select("id,nombre").eq("nombre", nombre_txt).single().execute()
            data = getattr(rp, "data", None) or None
            if data and data.get("id") is not None:
                return nombre_txt, data.get("id")
        except Exception:
            pass
        try:
            ra = supabase.table("areas").select("id,nombre").eq("nombre", nombre_txt).single().execute()
            data = getattr(ra, "data", None) or None
            if data and data.get("id") is not None:
                return nombre_txt, data.get("id")
        except Exception:
            pass
    # Fallback catálogo local
    _, area_map = cargar_catalogos()
    try:
        by_name_cs = next((k for k, v in area_map.items() if v == nombre_txt), None)
        if by_name_cs is not None:
            return nombre_txt, int(by_name_cs) if isinstance(by_name_cs, int) else None
        by_name_ci = next((k for k, v in area_map.items() if str(v).lower() == nombre_txt.lower()), None)
        if by_name_ci is not None:
            return nombre_txt, int(by_name_ci) if isinstance(by_name_ci, int) else None
    except Exception:
        pass
    return nombre_txt, None


def _ensure_upload_dir() -> str:
    upload_dir = os.path.join(os.path.dirname(__file__), "uploads")
    os.makedirs(upload_dir, exist_ok=True)
    return upload_dir


def _supabase_public_url(object_path: str) -> Optional[str]:
    if supabase is None:
        return None
    try:
        public = supabase.storage.from_(BUCKET).get_public_url(object_path)
        if isinstance(public, dict) and "data" in public and "publicUrl" in public["data"]:
            return public["data"]["publicUrl"]
        if isinstance(public, str):
            return public
    except Exception:
        return None
    return None


def subir_cv_y_obtener_url(dni: str, file_storage) -> str:
    """Sube el PDF a Supabase Storage (si está configurado) o a /uploads y devuelve URL pública."""
    filename = secure_filename(f"{dni}.pdf")

    if supabase is not None:
        # Intentar sin upsert; si ya existe, renombrar con timestamp y reintentar
        try:
            supabase.storage.from_(BUCKET).upload(
                path=filename,
                file=file_storage.stream,
                file_options={"contentType": "application/pdf", "upsert": "false"},
            )
            public_url = _supabase_public_url(filename)
            if public_url:
                return public_url
        except Exception:
            # conflicto o error: reintentar con timestamp
            try:
                ts = datetime.utcnow().strftime("%Y%m%d%H%M%S")
                alt_name = secure_filename(f"{dni}-{ts}.pdf")
                file_storage.stream.seek(0)
                supabase.storage.from_(BUCKET).upload(
                    path=alt_name,
                    file=file_storage.stream,
                    file_options={"contentType": "application/pdf", "upsert": "false"},
                )
                public_url = _supabase_public_url(alt_name)
                if public_url:
                    return public_url
            except Exception:
                pass

    # Fallback local
    upload_dir = _ensure_upload_dir()
    target_path = os.path.join(upload_dir, filename)
    file_storage.save(target_path)
    return url_for("uploaded_file", filename=filename, _external=True)


def _insertar_candidato_si_no_existe(data: Dict[str, Any]) -> Tuple[bool, Optional[str], Optional[str]]:
    """Inserta en Supabase. Si existe por DNI, elimina el previo y re-inserta.
    Devuelve (ok, error, candidato_id)."""
    if supabase is None:
        return True, None, None
    try:
        dni_value = data.get("dni")
        if dni_value:
            try:
                supabase.table("candidatos").delete().eq("dni", dni_value).execute()
            except Exception:
                pass
        # No enviar created_at; lo hace DEFAULT
        attempts = 0
        while attempts < 2:
            try:
                ins = supabase.table("candidatos").insert(data).execute()
                if ins.data:
                    return True, None, ins.data[0].get("id")
                return False, "No se pudo insertar el candidato", None
            except Exception as e:
                if is_pgrst204_error(e) and attempts == 0:
                    time.sleep(0.5)
                    attempts += 1
                    continue
                return False, str(e), None
        return False, "No se pudo insertar el candidato", None
    except Exception as e:
        return False, str(e), None


def _insertar_postulacion(candidato_id: Optional[str], vacante_id: Optional[str]) -> Tuple[bool, Optional[str]]:
    if supabase is None or not candidato_id:
        return True, None
    # Algunas instalaciones tienen columnas NOT NULL como 'tipo' y defaults distintos
    payload = {
        "candidato_id": candidato_id,
        "estado": "recibido",
        "tipo": "vacante" if vacante_id else "general",
    }
    if vacante_id:
        payload["vacante_id"] = int(vacante_id) if str(vacante_id).isdigit() else vacante_id
    attempts = 0
    while attempts < 2:
        try:
            ins = supabase.table("postulaciones").insert(payload).execute()
            if ins.data:
                return True, None
            return False, "No se pudo registrar la postulación"
        except Exception as e:
            if is_pgrst204_error(e) and attempts == 0:
                time.sleep(0.5)
                attempts += 1
                continue
            return False, str(e)
    return False, "No se pudo registrar la postulación"


def validar_campos_postulacion(form, files) -> Tuple[bool, List[str]]:
    errores: List[str] = []
    required_fields = [
        "nombre_apellido",
        "dni",
        "edad",
        "localidad",
        "disponibilidad",
        "area_preferencia",
        "celular",
        "mail",
        "licencia_conducir",
        "movilidad_propia",
        "familiar_en_clinica",
        "fuente_postulacion",
    ]
    for f in required_fields:
        if not (form.get(f) or str(form.get(f)) == "0"):
            errores.append(f)
    # Validar DNI: solo dígitos
    dni_val = (form.get("dni") or "").strip()
    if not dni_val.isdigit():
        if "dni" not in errores:
            errores.append("dni")
    file_cv = files.get("cv")
    if not file_cv or file_cv.filename == "":
        errores.append("cv")
    return (len(errores) == 0), errores


def verificar_turnstile(token: Optional[str], remote_ip: Optional[str]) -> bool:
    if not TURNSTILE_ENABLED:
        return True
    if not token:
        return False
    try:
        data = urllib.parse.urlencode({
            "secret": TURNSTILE_SECRET_KEY,
            "response": token,
            "remoteip": remote_ip or "",
        }).encode()
        req = urllib.request.Request(
            url="https://challenges.cloudflare.com/turnstile/v0/siteverify",
            data=data,
            method="POST",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
            return bool(payload.get("success"))
    except Exception:
        return False


# ==========================
# Rutas públicas
# ==========================
@app.route("/")
def home():
    vacantes: List[Dict[str, Any]] = []
    if supabase is not None:
        try:
            # Mostrar solo abiertas según el esquema confirmado
            res = supabase.table("vacantes").select("id,titulo,area,descripcion,estado").eq("estado", "abierta").execute()
            vacantes = res.data or []
            # Enriquecer con nombres de catálogos (área)
            _, area_map = cargar_catalogos()
            if area_map and vacantes:
                for v in vacantes:
                    area_val = v.get("area")
                    # Si el valor es un id (numérico o UUID), mapear a nombre
                    if area_val in area_map:
                        v["area_nombre"] = area_map[area_val]
                    else:
                        # Intento por comparación de string con claves
                        try:
                            match = next((nombre for k, nombre in area_map.items() if str(k) == str(area_val)), None)
                            if match:
                                v["area_nombre"] = match
                        except Exception:
                            pass
        except Exception:
            vacantes = []
    return render_template("landing.html", vacantes=vacantes)


# Nueva ruta: detalle de vacante
@app.route("/vacante/<int:vacante_id>")
def vacante_detalle(vacante_id: int):
    vacante: Optional[Dict[str, Any]] = None
    if supabase is not None:
        try:
            # Traer todos los campos para ser tolerantes a diferencias de esquema
            v = supabase.table("vacantes").select("*").eq("id", vacante_id).single().execute()
            vacante = getattr(v, "data", None) or None
            # Mapear nombre de área si viene como id
            if vacante and vacante.get("area") is not None:
                _, area_map = cargar_catalogos()
                area_val = vacante.get("area")
                if area_val in area_map:
                    vacante["area_nombre"] = area_map[area_val]
                else:
                    try:
                        match = next((nombre for k, nombre in area_map.items() if str(k) == str(area_val)), None)
                        if match:
                            vacante["area_nombre"] = match
                    except Exception:
                        pass
        except Exception:
            vacante = None
    if not vacante:
        flash("Vacante no encontrada", "warning")
        return redirect(url_for("home"))
    return render_template("vacante_detalle.html", vacante=vacante)


@app.route("/form")
def form_postulante():
    # Formulario alternativo (plantilla extendida de base)
    loc_map, _ = cargar_catalogos()
    localidades = [{"id": i, "nombre": n} for i, n in loc_map.items()]
    areas_cat = get_areas_catalogo()
    return render_template("form_postulante.html", localidades=localidades, areas=areas_cat, turnstile_site_key=TURNSTILE_SITE_KEY)


@app.route("/postular", methods=["GET", "POST"])
def postular():
    if request.method == "GET":
        areas, disponibilidades, localidades = cargar_opciones_postulacion()
        # Reemplazar areas con catálogo con id/nombre
        areas = get_areas_catalogo()
        vacante_id = request.args.get("vacante_id") or ""
        area_prefill = request.args.get("area") or request.args.get("area_prefill") or ""
        if supabase is not None and vacante_id and not area_prefill:
            try:
                v = supabase.table("vacantes").select("area").eq("id", vacante_id).single().execute()
                if getattr(v, "data", None) and v.data.get("area"):
                    area_prefill = v.data.get("area")
            except Exception:
                pass
        # Normalizar: si area_prefill es id, convertir a nombre usando catálogo
        if area_prefill:
            try:
                _, area_map = cargar_catalogos()
                if area_prefill in area_map:
                    area_prefill = area_map[area_prefill]
                else:
                    match = next((nombre for k, nombre in area_map.items() if str(k) == str(area_prefill)), None)
                    if match:
                        area_prefill = match
            except Exception:
                pass
        return render_template(
            "postular.html",
            mensaje=None,
            exito=None,
            areas=areas,
            disponibilidades=disponibilidades,
            localidades=localidades,
            area_prefill=area_prefill,
            vacante_id=vacante_id,
            turnstile_site_key=TURNSTILE_SITE_KEY,
        )

    # POST: procesar envío
    form = request.form
    files = request.files

    ok, errs = validar_campos_postulacion(form, files)
    if not ok:
        areas, disponibilidades, localidades = cargar_opciones_postulacion()
        areas = get_areas_catalogo()
        return (
            render_template(
                "postular.html",
                mensaje="Completá todos los campos.",
                exito=False,
                areas=areas,
                disponibilidades=disponibilidades,
                localidades=localidades,
                area_prefill=form.get("area_preferencia"),
                vacante_id=form.get("vacante_id"),
                turnstile_site_key=TURNSTILE_SITE_KEY,
            ),
            400,
        )

    # Verificar Turnstile antes de procesar
    ts_token = request.form.get("cf-turnstile-response")
    if not verificar_turnstile(ts_token, request.remote_addr):
        areas, disponibilidades, localidades = cargar_opciones_postulacion()
        areas = get_areas_catalogo()
        return (
            render_template(
                "postular.html",
                mensaje="Prueba fallida, intentá de nuevo.",
                exito=False,
                areas=areas,
                disponibilidades=disponibilidades,
                localidades=localidades,
                area_prefill=form.get("area_preferencia"),
                vacante_id=form.get("vacante_id"),
                turnstile_site_key=TURNSTILE_SITE_KEY,
            ),
            400,
        )

    try:
        file_cv = files.get("cv")
        cv_url = subir_cv_y_obtener_url(form.get("dni", "").strip(), file_cv)
    except Exception as e:
        return redirect(url_for("confirmacion", ok=0, error=f"Error subiendo CV: {e}"))

    # Resolver área de preferencia (aceptar id o nombre)
    area_nombre, area_id = resolver_area_desde_form(form.get("area_preferencia", ""))

    data = {
        "nombre_apellido": form.get("nombre_apellido", "").strip(),
        "dni": form.get("dni", "").strip(),
        "edad": int(form.get("edad", 0) or 0),
        "area_preferencia": area_nombre,
        "licencia_conducir": normalizar_checkbox(form.get("licencia_conducir")),
        "movilidad_propia": normalizar_checkbox(form.get("movilidad_propia")),
        "disponibilidad": form.get("disponibilidad", "").strip(),
        "celular": form.get("celular", "").strip(),
        "mail": form.get("mail", "").strip(),
        "localidad": form.get("localidad", "").strip(),
        "cv_url": cv_url,
        # Nuevos campos opcionales
        "familiar_en_clinica": normalizar_checkbox(form.get("familiar_en_clinica")),
        "fuente_postulacion": (form.get("fuente_postulacion", "") or "").strip() or None,
    }
    vacante_id = form.get("vacante_id") or None

    ok_ins, err_ins, cand_id = _insertar_candidato_si_no_existe(data)
    if not ok_ins:
        # Si hay error de red/DNS (p.ej. getaddrinfo failed), continuar en modo local
        msg_text = str(err_ins or "Error desconocido")
        if ("getaddrinfo failed" in msg_text) or ("Name or service not known" in msg_text) or ("Temporary failure in name resolution" in msg_text):
            cand_id = None  # modo local sin id
        else:
            msg = (
                "Se actualizó el esquema. Probá nuevamente." if (err_ins and "PGRST204" in msg_text) else msg_text
            )
            return redirect(url_for("confirmacion", ok=0, error=msg))

    ok_pos, err_pos = _insertar_postulacion(cand_id, vacante_id)
    if not ok_pos:
        msg_text = str(err_pos or "Error desconocido")
        if ("getaddrinfo failed" in msg_text) or ("Name or service not known" in msg_text) or ("Temporary failure in name resolution" in msg_text):
            # Continuar en modo local
            return redirect(url_for("confirmacion", ok=1, error=""))
        msg = (
            "Se actualizó el esquema. Probá nuevamente." if (err_pos and "PGRST204" in msg_text) else msg_text
        )
        return redirect(url_for("confirmacion", ok=0, error=msg))

    return redirect(url_for("confirmacion", ok=1, error=""))


@app.route("/confirmacion")
def confirmacion():
    ok = request.args.get("ok", "0") in {"1", "true", "True", "sí", "si"}
    error = request.args.get("error")
    return render_template("confirmacion.html", ok=ok, error=error)


@app.route("/uploads/<path:filename>")
def uploaded_file(filename: str):
    return send_from_directory(_ensure_upload_dir(), filename)


# ==========================
# Admin (mínimo viable)
# ==========================
def _is_admin() -> bool:
    return bool(session.get("is_admin"))


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = (request.form.get("username", "") or "").strip()
        password = (request.form.get("password", "") or "").strip()
        env_user = (
            os.getenv("ADMIN_USERNAME")
            or os.getenv("ADMIN_USER")
            or "admin"
        )
        env_pass = (
            os.getenv("ADMIN_PASSWORD")
            or os.getenv("ADMIN_PASS")
            or "admin"
        )
        if username == env_user.strip() and password == env_pass.strip():
            session["is_admin"] = True
            flash("Ingreso exitoso", "success")
            return redirect(url_for("admin_vacantes"))
        flash("Credenciales inválidas", "warning")
    return render_template("admin_login.html")


@app.route("/admin/logout")
def admin_logout():
    session.pop("is_admin", None)
    flash("Sesión cerrada", "success")
    return redirect(url_for("home"))


@app.route("/admin/candidatos")
def admin_candidatos():
    if not _is_admin():
        return redirect(url_for("admin_login"))

    disponibilidad_filtro = request.args.get("disponibilidad")
    candidatos: List[Dict[str, Any]] = []
    if supabase is not None:
        try:
            query = supabase.table("candidatos").select("*")
            if disponibilidad_filtro:
                query = query.eq("disponibilidad", disponibilidad_filtro)
            res = query.order("created_at", desc=True).execute()
            candidatos = res.data or []
        except Exception:
            candidatos = []
    return render_template("admin_candidatos.html", candidatos=candidatos)


@app.route("/admin/vacantes")
def admin_vacantes():
    if not _is_admin():
        return redirect(url_for("admin_login"))

    filtros = {
        "titulo": request.args.get("titulo", ""),
        "area": request.args.get("area", ""),
        # el template usa 'publicada' pero la DB tiene 'estado' (abierta/cerrada)
        "publicada": request.args.get("publicada", ""),
    }
    vacantes: List[Dict[str, Any]] = []
    page = int(request.args.get("page", "1") or 1)
    page = max(page, 1)
    per_page = 10
    from_row = (page - 1) * per_page
    to_row = from_row + per_page - 1
    if supabase is not None:
        try:
            query = supabase.table("vacantes").select("*")
            if filtros["titulo"]:
                query = query.ilike("titulo", f"%{filtros['titulo']}%")
            if filtros["area"]:
                query = query.ilike("area", f"%{filtros['area']}%")
            if filtros["publicada"] in {"true", "false"}:
                estado_val = "abierta" if filtros["publicada"] == "true" else "cerrada"
                query = query.eq("estado", estado_val)
            res = query.order("created_at", desc=True).range(from_row, to_row).execute()
            vacantes = res.data or []
            # Adaptación para el template viejo: derivar 'publicada' desde 'estado'
            for v in vacantes:
                v["publicada"] = (v.get("estado") == "abierta")
            # Enriquecer con nombre de área si aplica
            _, area_map = cargar_catalogos()
            if area_map and vacantes:
                for v in vacantes:
                    area_val = v.get("area")
                    if area_val in area_map:
                        v["area_nombre"] = area_map[area_val]
                    else:
                        try:
                            match = next((nombre for k, nombre in area_map.items() if str(k) == str(area_val)), None)
                            if match:
                                v["area_nombre"] = match
                        except Exception:
                            pass
        except Exception:
            vacantes = []

    # Render de la versión simple
    return render_template("vacantes.html", vacantes=vacantes, filtros=filtros, mensaje=None)


@app.route("/admin/vacantes/nueva", methods=["GET", "POST"])
def admin_vacante_nueva():
    if not _is_admin():
        return redirect(url_for("admin_login"))
    # Catálogo con id/nombre
    areas = get_areas_catalogo()
    if request.method == "POST":
        titulo = (request.form.get("titulo") or "").strip()
        area_val = (request.form.get("area") or "").strip()
        area_nombre, area_id = resolver_area_desde_form(area_val)
        descripcion = (request.form.get("descripcion") or "").strip()
        estado = (request.form.get("estado") or "abierta").strip()
        if not (titulo and area_nombre and descripcion and estado):
            flash("Completá todos los campos.", "warning")
            return render_template("admin_vacante_nueva.html", areas=areas), 400
        if supabase is not None:
            payload = {"titulo": titulo, "area": area_nombre, "descripcion": descripcion, "estado": estado}
            attempts = 0
            while attempts < 2:
                try:
                    supabase.table("vacantes").insert(payload).execute()
                    flash("Vacante creada", "success")
                    return redirect(url_for("admin_vacantes"))
                except Exception as e:
                    if is_pgrst204_error(e) and attempts == 0:
                        time.sleep(0.5)
                        attempts += 1
                        continue
                    flash("No se pudo crear la vacante", "warning")
                    break
        else:
            flash("Modo local: se omitió el guardado en DB.", "warning")
            return redirect(url_for("admin_vacantes"))
    return render_template("admin_vacante_nueva.html", areas=areas)


@app.route("/admin/vacantes/<int:vacante_id>/cerrar", methods=["POST"])
def admin_cerrar_vacante(vacante_id: int):
    if not _is_admin():
        return redirect(url_for("admin_login"))
    if supabase is not None:
        attempts = 0
        while attempts < 2:
            try:
                supabase.table("vacantes").update({"estado": "cerrada"}).eq("id", vacante_id).execute()
                flash("Vacante cerrada", "success")
                break
            except Exception as e:
                if is_pgrst204_error(e) and attempts == 0:
                    time.sleep(0.5)
                    attempts += 1
                    continue
                flash("No se pudo cerrar la vacante", "warning")
                break
    return redirect(url_for("admin_vacantes"))


@app.route("/admin/vacantes/<int:vacante_id>/eliminar", methods=["POST"])
def admin_eliminar_vacante(vacante_id: int):
    if not _is_admin():
        return redirect(url_for("admin_login"))
    if supabase is not None:
        try:
            supabase.table("vacantes").delete().eq("id", vacante_id).execute()
            flash("Vacante eliminada", "success")
        except Exception as e:
            flash(f"No se pudo eliminar: {e}", "warning")
    return redirect(url_for("admin_vacantes"))


@app.route("/admin/postulaciones", methods=["GET", "POST"])
def admin_postulaciones():
    if not _is_admin():
        return redirect(url_for("admin_login"))

    if request.method == "POST" and supabase is not None:
        try:
            pid = request.form.get("postulacion_id")
            estado = request.form.get("estado")
            entrevistado_por = request.form.get("entrevistado_por")
            observaciones = request.form.get("observaciones")
            if pid:
                supabase.table("postulaciones").update(
                    {
                        "estado": estado,
                        "entrevistado_por": entrevistado_por,
                        "observaciones": observaciones,
                    }
                ).eq("id", pid).execute()
                flash("Postulación actualizada", "success")
        except Exception as e:
            flash(f"Error al actualizar: {e}", "warning")

    # [CHANGE] Filtros via GET y opciones del formulario
    areas, dispon, loc = cargar_opciones_postulacion()
    # Estandarizar áreas desde catálogo
    areas = get_areas_preferencia()
    filtros = {
        "area": request.args.get("area", ""),
        "area_preferencia": request.args.get("area_preferencia", ""),
        "localidad": request.args.get("localidad", ""),
        "disponibilidad": request.args.get("disponibilidad", ""),
        "estado": request.args.get("estado", ""),
        "vacante_id": request.args.get("vacante_id", ""),
        "edad_min": request.args.get("edad_min", ""),
        "edad_max": request.args.get("edad_max", ""),
        "movilidad": request.args.get("movilidad", ""),
        "licencia": request.args.get("licencia", ""),
    }

    vacantes: List[Dict[str, Any]] = []
    candidatos: List[Dict[str, Any]] = []
    postulaciones: List[Dict[str, Any]] = []
    # Paginación
    page = int(request.args.get("page", "1") or 1)
    page = max(page, 1)
    per_page = 50
    from_row = (page - 1) * per_page
    # range es inclusivo, pedimos uno extra para detectar "siguiente"
    to_row = from_row + per_page  # per_page + 1 items
    has_prev = page > 1
    has_next = False

    if supabase is not None:
        try:
            # [CHANGE] Traer vacantes, opcionalmente filtrando por área (texto)
            vac_q = supabase.table("vacantes").select("id,titulo,area")
            if filtros["area"]:
                vac_q = vac_q.ilike("area", f"%{filtros['area']}%")
            vacantes = (vac_q.execute().data) or []
        except Exception:
            vacantes = []

        # [CHANGE] Aplicar filtros sobre candidatos en la DB cuando haya valores
        try:
            cand_q = supabase.table("candidatos").select("*")
            if filtros["area_preferencia"]:
                cand_q = cand_q.eq("area_preferencia", filtros["area_preferencia"])
            if filtros["localidad"]:
                cand_q = cand_q.eq("localidad", filtros["localidad"])
            if filtros["disponibilidad"]:
                cand_q = cand_q.eq("disponibilidad", filtros["disponibilidad"])
            if filtros["movilidad"] in {"Sí", "No"}:
                mov_bool = True if filtros["movilidad"] == "Sí" else False
                cand_q = cand_q.eq("movilidad_propia", mov_bool)
            if filtros["licencia"] in {"Sí", "No"}:
                lic_bool = True if filtros["licencia"] == "Sí" else False
                cand_q = cand_q.eq("licencia_conducir", lic_bool)
            if filtros["edad_min"]:
                try:
                    cand_q = cand_q.gte("edad", int(filtros["edad_min"]))
                except Exception:
                    pass
            if filtros["edad_max"]:
                try:
                    cand_q = cand_q.lte("edad", int(filtros["edad_max"]))
                except Exception:
                    pass
            # Búsqueda textual en área (campo preferencia del candidato)
            if filtros["area"]:
                cand_q = cand_q.ilike("area_preferencia", f"%{filtros['area']}%")
            candidatos = (cand_q.execute().data) or []
        except Exception:
            candidatos = []

        # [CHANGE] Aplicar filtros sobre postulaciones en la DB cuando haya valores
        try:
            # Pedimos count para potenciales usos futuros; range para paginar
            post_q = supabase.table("postulaciones").select("*", count="exact")
            if filtros["estado"]:
                # [CHANGE] Comparación case-insensitive para compatibilidad con datos antiguos
                post_q = post_q.ilike("estado", filtros["estado"])
            if filtros["vacante_id"]:
                vid = filtros["vacante_id"]
                post_q = post_q.eq("vacante_id", int(vid) if str(vid).isdigit() else vid)
            # Si filtramos por atributos de candidato, restringimos por sus IDs (AND)
            cand_ids = [c.get("id") for c in candidatos if c.get("id")]
            aplico_filtros_candidato = bool(
                filtros["area_preferencia"] or filtros["localidad"] or filtros["disponibilidad"] or filtros["movilidad"] or filtros["edad_min"] or filtros["edad_max"]
            )
            if aplico_filtros_candidato:
                if cand_ids:
                    post_q = post_q.in_("candidato_id", cand_ids)
                else:
                    postulaciones = []
                    candidatos = []
                    vacantes = vacantes or []
                    filas: List[Dict[str, Any]] = []
                    opciones = {"areas_pref": areas, "localidades": loc, "dispon": dispon}
                    return render_template(
                        "admin_postulaciones.html",
                        filtros=filtros,
                        opciones=opciones,
                        vacantes=vacantes,
                        filas=filas,
                        mensaje=None,
                        page=page,
                        has_prev=has_prev,
                        has_next=has_next,
                    )
            # Aplicar orden y rango (solicitamos uno extra para saber si hay siguiente)
            res_post = post_q.order("created_at", desc=True).range(from_row, to_row).execute()
            postulaciones = (getattr(res_post, "data", None) or [])
            if len(postulaciones) > per_page:
                has_next = True
                postulaciones = postulaciones[:per_page]

            # [CHANGE] Si hay filtro 'area' (texto), aplicar OR: candidato.area_preferencia o vacante.area
            if filtros["area"]:
                vac_ids = [v.get("id") for v in vacantes if v.get("id")]
                if cand_ids or vac_ids:
                    postulaciones = [
                        p for p in postulaciones
                        if (p.get("candidato_id") in cand_ids) or (p.get("vacante_id") in vac_ids)
                    ]
        except Exception:
            postulaciones = []

    # Unir por candidato_id (nuevo esquema). Fallback si no hay tabla postulaciones.
    by_id: Dict[str, Dict[str, Any]] = {c.get("id"): c for c in candidatos if c.get("id")}
    filas: List[Dict[str, Any]] = []
    if postulaciones:
        for p in postulaciones:
            c = by_id.get(p.get("candidato_id"), {})
            v = next((vv for vv in vacantes if vv.get("id") == p.get("vacante_id")), None)
            filas.append({"postulacion": p, "candidato": c, "vacante": v})
    else:
        # Si no hay tabla de postulaciones, emulamos una fila por candidato
        for c in candidatos:
            filas.append(
                {
                    "postulacion": {
                        "id": c.get("id"),
                        "estado": "recibido",
                        "created_at": c.get("created_at"),
                        "entrevistado_por": None,
                        "observaciones": None,
                    },
                    "candidato": c,
                    "vacante": None,
                }
            )

    opciones = {"areas_pref": areas, "localidades": loc, "dispon": dispon}
    return render_template(
        "admin_postulaciones.html",
        filtros=filtros,
        opciones=opciones,
        vacantes=vacantes,
        filas=filas,
        mensaje=None,
        page=page,
        has_prev=has_prev,
        has_next=has_next,
    )


# [CHANGE] Nueva ruta para calificar postulaciones (1..10)
@app.post("/admin/postulaciones/<int:postulacion_id>/calificar")
def calificar_postulacion(postulacion_id: int):
    if not _is_admin():
        return {"ok": False, "error": "No autorizado"}, 401
    try:
        cal_str = request.form.get("calificacion", "").strip()
        if not cal_str:
            return {"ok": False, "error": "Falta calificacion"}, 400
        cal = int(cal_str)
        if cal < 1 or cal > 10:
            return {"ok": False, "error": "Fuera de rango (1..10)"}, 400
        if supabase is not None:
            attempts = 0
            while attempts < 2:
                try:
                    supabase.table("postulaciones").update({"calificacion": cal}).eq("id", postulacion_id).execute()
                    break
                except Exception as e:
                    if is_pgrst204_error(e) and attempts == 0:
                        time.sleep(0.6)
                        attempts += 1
                        continue
                    raise
        return {"ok": True, "calificacion": cal}
    except Exception as e:
        return {"ok": False, "error": str(e)}, 400


# [CHANGE] Endpoint AJAX para actualizar estado validando catálogo
@app.post("/admin/postulaciones/<int:postulacion_id>/estado")
def actualizar_estado_postulacion(postulacion_id: int):
    if not _is_admin():
        return {"ok": False, "error": "No autorizado"}, 401
    allowed = {"Recibido", "Preseleccionado", "Entrevista", "Ingresado", "Rechazado"}
    try:
        estado = (request.form.get("estado") or "").strip()
        if estado not in allowed:
            return {"ok": False, "error": "Estado inválido"}, 400
        if supabase is not None:
            attempts = 0
            while attempts < 2:
                try:
                    supabase.table("postulaciones").update({"estado": estado}).eq("id", postulacion_id).execute()
                    break
                except Exception as e:
                    if is_pgrst204_error(e) and attempts == 0:
                        time.sleep(0.6)
                        attempts += 1
                        continue
                    raise
        return {"ok": True, "estado": estado}
    except Exception as e:
        return {"ok": False, "error": str(e)}, 400


@app.route("/admin/postulaciones/borrar", methods=["POST"])
def admin_borrar_postulado():
    if not _is_admin():
        return redirect(url_for("admin_login"))
    cand_id = request.form.get("candidato_id")
    if supabase is not None and cand_id:
        try:
            supabase.table("candidatos").delete().eq("id", cand_id).execute()
            flash("Postulado eliminado", "success")
        except Exception as e:
            flash(f"No se pudo eliminar: {e}", "warning")
    return redirect(url_for("admin_postulaciones"))


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=True)


