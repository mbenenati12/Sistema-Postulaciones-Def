# test_upload_and_insert.py
import os
from supabase import create_client, Client
from dotenv import load_dotenv

# === Cargar y limpiar credenciales ===
load_dotenv()
url = (os.getenv("SUPABASE_URL") or "").strip().rstrip("/")
key = (os.getenv("SUPABASE_KEY") or "").strip()

assert url.startswith("https://") and url.endswith(".supabase.co"), f"SUPABASE_URL inválida: {repr(url)}"
assert len(key) > 20, "SUPABASE_KEY parece vacía o corta"

supabase: Client = create_client(url, key)
BUCKET = "cvs"

def subir_cv_y_obtener_url(dni: str, pdf_local_path: str) -> str:
    object_path = f"{dni}.pdf"

    # Subida
    with open(pdf_local_path, "rb") as f:
        supabase.storage.from_(BUCKET).upload(
            path=object_path,
            file=f,
            file_options={
                "contentType": "application/pdf",
                "upsert": "true"  # string, no boolean
            }
        )

    # URL pública (según versión puede ser str o dict)
    public = supabase.storage.from_(BUCKET).get_public_url(object_path)
    if isinstance(public, dict) and "data" in public and "publicUrl" in public["data"]:
        return public["data"]["publicUrl"]
    if isinstance(public, str):
        return public
    raise RuntimeError(f"No se pudo obtener URL pública: {public}")

def insertar_candidato_si_no_existe(candidato: dict):
    existing = supabase.table("candidatos").select("id").eq("dni", candidato["dni"]).execute()
    if existing.data:
        print(f"[INFO] Ya existe postulación con DNI {candidato['dni']}. No se inserta.")
        return existing.data[0]["id"]

    ins = supabase.table("candidatos").insert(candidato).execute()
    if ins.data:
        print(f"[OK] Candidato insertado. ID: {ins.data[0]['id']}")
        return ins.data[0]["id"]
    raise RuntimeError(f"Error al insertar candidato: {ins}")

if __name__ == "__main__":
    # Ping a la DB para aislar errores de red/dns
    try:
        ping = supabase.table("candidatos").select("id").limit(1).execute()
        print("[PING DB] OK")
    except Exception as e:
        print("[PING DB] ERROR:", e)

    pdf_local_path = "CV_prueba.pdf"
    dni_prueba = "30111222"

    candidato = {
        "nombre_apellido": "Juan Pérez",
        "dni": dni_prueba,
        "edad": 28,
        "area_preferencia": "Recepción",
        "licencia_conducir": True,
        "movilidad_propia": False,
        "disponibilidad": "Full time",
        "celular": "+54 9 261 555 5555",
        "mail": "juan.perez@example.com",
        "localidad": "Godoy Cruz",
        "cv_url": "",
    }

    # Subir y guardar
    cv_public_url = subir_cv_y_obtener_url(dni_prueba, pdf_local_path)
    print("[OK] CV subido. URL pública:", cv_public_url)

    candidato["cv_url"] = cv_public_url
    insertar_candidato_si_no_existe(candidato)

    print("\nListo ✅ Revisá en Supabase → Table Editor → candidatos. Abrí la URL del CV.")
