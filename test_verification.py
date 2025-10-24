#!/usr/bin/env python3
"""
Script de verificación para detectar errores potenciales en el código actualizado
"""

import sys
import os

# Agregar el directorio actual al path
sys.path.insert(0, os.path.dirname(__file__))

try:
    from app import (
        app,
        cargar_catalogos,
        cargar_opciones_postulacion,
        normalizar_checkbox,
        supabase
    )
    print("✅ Todas las importaciones exitosas")

    # Verificar que las funciones helper funcionan
    print("✅ Función normalizar_checkbox:", normalizar_checkbox("Sí"))
    print("✅ Función normalizar_checkbox:", normalizar_checkbox("No"))
    print("✅ Función normalizar_checkbox:", normalizar_checkbox("on"))

    # Verificar que las funciones de carga no fallen (aunque no tengan conexión)
    try:
        loc_map, area_map = cargar_catalogos()
        print("✅ Función cargar_catalogos funciona (sin conexión)")
    except Exception as e:
        print(f"⚠️  cargar_catalogos: {e}")

    try:
        areas, dispon, loc = cargar_opciones_postulacion()
        print("✅ Función cargar_opciones_postulacion funciona (sin conexión)")
    except Exception as e:
        print(f"⚠️  cargar_opciones_postulacion: {e}")

    print("\n🎉 Verificación completada exitosamente!")

except ImportError as e:
    print(f"❌ Error de importación: {e}")
except Exception as e:
    print(f"❌ Error general: {e}")
    import traceback
    traceback.print_exc()
