# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Sistema de Postulaciones para Clínica de Cuyo - A Flask-based job application system that integrates with Supabase for data storage and Cloudflare Turnstile for bot protection.

## Development Commands

### Running the Application

```bash
python app.py
# Runs on http://0.0.0.0:5000 by default
# Port can be configured via PORT environment variable
```

### Running Tests

```bash
# Verification test (checks imports and basic functions)
python test_verification.py

# Upload and insert test (tests Supabase integration)
python test_upload_and_insert.py
```

## Architecture

### Core Application Structure

- **app.py** (1146 lines): Main Flask application containing all routes, business logic, and Supabase integration
- **templates/**: Jinja2 HTML templates for all pages (12 templates total)
  - Public routes: landing, vacantes, postular, confirmacion
  - Admin routes: admin_login, admin_vacantes, admin_candidatos, admin_postulaciones
- **static/**: Static assets (logos, images)
- **uploads/**: Local fallback directory for CV uploads when Supabase is unavailable

### Database Integration (Supabase)

The system uses the following Supabase tables:

- **candidatos**: Stores applicant information including CV URLs
- **postulaciones**: Links candidates to job openings with status tracking
- **vacantes**: Job postings (titulo, area, descripcion, estado)
- **areas**: Operational areas catalog
- **areas_preferencia**: Extended areas catalog for applicant preferences
- **localidades**: Geographic locations catalog

The app gracefully handles Supabase being unavailable by falling back to local catalogs and file storage.

### Key Architectural Patterns

**Dual Catalog System**: The app maintains fallback data for areas and localities to function without database connection:
- `cargar_catalogos()` returns (loc_map, area_map) from Supabase or fallback
- `_fallback_localidades()` and `_fallback_areas()` provide hardcoded defaults
- `get_areas_catalogo()` prioritizes areas_preferencia over areas table

**File Storage Strategy**: CVs are uploaded with automatic fallback:
- Primary: Supabase Storage bucket "cvs" with public URLs
- Fallback: Local uploads/ directory served via Flask
- Function: `subir_cv_y_obtener_url()` handles both paths

**Error Resilience**: All Supabase operations include:
- Try-catch blocks for connection failures
- PGRST204 cache error detection and retry logic (2 attempts with 0.5s delay)
- Graceful degradation to allow form submissions even when DB is down

**Admin Authentication**: Simple session-based auth using environment variables:
- `ADMIN_USERNAME` or `ADMIN_USER`
- `ADMIN_PASSWORD`
- Session flag `is_admin` checked via `_is_admin()` helper

### Environment Variables

Required for full functionality:

```bash
# Flask
SECRET_KEY=your-secret-key
PORT=5000  # optional, defaults to 5000

# Supabase (optional - app works without)
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_KEY=your-anon-key

# Admin credentials
ADMIN_USERNAME=admin  # or ADMIN_USER
ADMIN_PASSWORD=your-password

# Cloudflare Turnstile (optional - can be disabled)
TURNSTILE_SITE_KEY=your-site-key
TURNSTILE_SECRET_KEY=your-secret-key
TURNSTILE_ENABLED=true  # set to false/0/no to disable
```

### Route Structure

**Public Routes** (app.py:491-701):
- `/` - Landing page with open job listings
- `/vacante/<id>` - Job detail view
- `/form` - Standalone applicant form
- `/postular` - Application submission (GET shows form, POST processes)
- `/confirmacion` - Success page after submission
- `/uploads/<filename>` - Serve locally stored CVs

**Admin Routes** (app.py:713-1139):
- `/admin/login` - Admin authentication
- `/admin/logout` - Session cleanup
- `/admin/candidatos` - View all applicants with pagination
- `/admin/vacantes` - Manage job postings
- `/admin/vacantes/nueva` - Create new job posting
- `/admin/vacantes/<id>/cerrar` - Close a job posting
- `/admin/vacantes/<id>/eliminar` - Delete a job posting
- `/admin/postulaciones` - View applications with filtering and status management
- `/admin/postulaciones/<id>/estado` - AJAX endpoint to update application status
- `/admin/postulaciones/borrar` - Delete an application

### Form Validation

`validar_campos_postulacion()` (app.py:434) enforces required fields:
- Personal: nombre_apellido, dni, edad
- Contact: celular, mail, localidad
- Preferences: area_preferencia, disponibilidad
- Flags: licencia_conducir, movilidad_propia, familiar_en_clinica, fuente_postulacion
- File: cv (PDF upload)
- DNI must be numeric only

### Data Normalization

**Checkbox Handler**: `normalizar_checkbox()` (app.py:64) converts various formats to boolean:
- Accepts: "si", "sí", "true", "1", "on", "yes" → True
- Everything else → False

**Area Resolution**: `resolver_area_desde_form()` (app.py:251) handles multiple input formats:
- Numeric ID → looks up name in areas_preferencia then areas
- UUID → looks up name in catalogs
- Text name → returns as-is, attempts to find ID

### Supabase Migration Guidelines

When creating Supabase migrations, follow these rules:
- **ALWAYS use full timestamp format**: YYYYMMDDHHmmss (not just YYYYMMDD)
- Example: `20241119143522_add_column.sql` (not `20241119_add_column.sql`)
- This maintains correct chronological ordering in Supabase migrations

### Testing Strategy

- **test_verification.py**: Smoke test that validates imports and helper functions work
- **test_upload_and_insert.py**: Integration test for Supabase upload and insert operations
- No formal test framework; tests are standalone scripts

### Frontend

- **TailwindCSS**: Loaded via CDN for styling
- **Google Fonts**: Nunito Sans as primary typeface
- **Brand Colors**: Custom CSS variables for Pantone 286 C (blue) and 377 C (green)
- **AJAX**: Used in admin panel for updating application status without page reload

### Dependencies

Core Python packages (from pip freeze):
- Flask==3.1.1
- python-dotenv==1.0.1
- Werkzeug==3.1.3
- supabase-py (optional, gracefully handled if missing)

### Development Notes

- The app runs in debug mode by default when started via `python app.py`
- Hot reload is enabled during development
- All routes use type hints extensively for better IDE support
- The codebase uses defensive programming with extensive null checking
- Admin panel includes pagination for large datasets (50 items per page for candidates, 30 for applications)
