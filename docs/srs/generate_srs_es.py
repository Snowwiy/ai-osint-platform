"""Build the Spanish RavenTech OSINT software requirements specification."""

# ruff: noqa: E501

from __future__ import annotations

from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Flowable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "docs" / "srs" / "RavenTech_OSINT_SRS_ES.md"
PDF = ROOT / "docs" / "deliverables" / "RavenTech_OSINT_SRS_v1.0_ES.pdf"
PRODUCT = "RavenTech OSINT"
PRODUCT_VERSION = "5.0.0-rc6"
DOCUMENT_VERSION = "1.0"
ISSUE_DATE = date(2026, 9, 24).isoformat()
STATUS = "Especificación para candidato de lanzamiento"


# Requirement tuple: id, name, subsystem, platform, implementation, verification,
# test area, acceptance criterion.
FR: list[tuple[str, str, str, str, str, str, str, str]] = []


def add(area: str, rows: list[tuple[str, str, str, str, str, str, str]]) -> None:
    for number, (
        name,
        subsystem,
        platform,
        state,
        verification,
        test,
        criterion,
    ) in enumerate(rows, 1):
        FR.append(
            (
                f"FR-{area}-{number:03}",
                name,
                subsystem,
                platform,
                state,
                verification,
                test,
                criterion,
            )
        )


IMPLEMENTED = "Implementado"
PARTIAL = "Parcial"
PLANNED = "Planificado"
NFR_SPECIFIED = "Especificado"
AUTO = "Prueba automatizada/API e inspección"

add(
    "AUTH",
    [
        (
            "Inicio de sesión",
            "Autenticación",
            "Windows/Linux",
            IMPLEMENTED,
            AUTO,
            "AUTH-01",
            "Credenciales válidas abren sesión y las inválidas se rechazan sin revelar secretos.",
        ),
        (
            "Perfil autenticado",
            "Autenticación",
            "Windows/Linux",
            IMPLEMENTED,
            AUTO,
            "AUTH-02",
            "El perfil devuelve el usuario activo y su rol sin exponer credenciales.",
        ),
        (
            "Rotación de refresh",
            "Autenticación",
            "Windows/Linux",
            IMPLEMENTED,
            AUTO,
            "AUTH-03",
            "La renovación rota el token y el token anterior deja de ser aceptado.",
        ),
        (
            "Revocación de sesión",
            "Autenticación",
            "Windows/Linux",
            IMPLEMENTED,
            AUTO,
            "AUTH-04",
            "Cerrar sesión invalida el refresh asociado y limpia la cookie según el contrato.",
        ),
        (
            "Invalidación administrativa",
            "Autenticación",
            "Windows/Linux",
            IMPLEMENTED,
            "Prueba de integración",
            "AUTH-05",
            "Un usuario deshabilitado pierde acceso en solicitudes posteriores.",
        ),
        (
            "Limitación de intentos",
            "Autenticación",
            "Windows/Linux",
            IMPLEMENTED,
            "Prueba de integración y configuración",
            "AUTH-06",
            "Los fallos se limitan y el estado nativo no exige Redis.",
        ),
        (
            "Política de registro",
            "Autenticación",
            "Windows/Linux",
            IMPLEMENTED,
            AUTO,
            "AUTH-07",
            "El registro público sigue la configuración y nunca concede rol administrador.",
        ),
    ],
)
add(
    "RBAC",
    [
        (
            "Control por rol",
            "Autorización",
            "Windows/Linux",
            IMPLEMENTED,
            AUTO,
            "RBAC-01",
            "Cada ruta protegida permite solo los roles declarados.",
        ),
        (
            "Membresía de caso",
            "Autorización",
            "Windows/Linux",
            IMPLEMENTED,
            "Prueba API",
            "RBAC-02",
            "Un analista no accede a casos sin membresía; el administrador sigue la política definida.",
        ),
        (
            "Gestión de usuarios",
            "Administración",
            "Windows/Linux",
            IMPLEMENTED,
            AUTO,
            "RBAC-03",
            "Solo administradores pueden listar y modificar usuarios.",
        ),
        (
            "Protección del último administrador",
            "Administración",
            "Windows/Linux",
            IMPLEMENTED,
            "Prueba de integración",
            "RBAC-04",
            "La plataforma rechaza deshabilitar o degradar al último administrador activo.",
        ),
        (
            "Rechazo de acceso insuficiente",
            "Autorización",
            "Windows/Linux",
            IMPLEMENTED,
            AUTO,
            "RBAC-05",
            "La solicitud no autorizada recibe una respuesta 401/403 sin filtrar datos.",
        ),
    ],
)
add(
    "CASE",
    [
        (
            "Crear investigación",
            "Investigaciones",
            "Windows/Linux",
            IMPLEMENTED,
            AUTO,
            "CASE-01",
            "Un usuario autorizado crea un caso con base de autorización y alcance documentados.",
        ),
        (
            "Editar metadatos",
            "Investigaciones",
            "Windows/Linux",
            IMPLEMENTED,
            "Prueba API",
            "CASE-02",
            "Solo miembros autorizados modifican los campos permitidos.",
        ),
        (
            "Estados del caso",
            "Investigaciones",
            "Windows/Linux",
            IMPLEMENTED,
            "Prueba de flujo",
            "CASE-03",
            "El ciclo de revisión conserva estados y transiciones válidas.",
        ),
        (
            "Compartir caso",
            "Membresía",
            "Windows/Linux",
            IMPLEMENTED,
            AUTO,
            "CASE-04",
            "El propietario administra colaboradores y la API aplica el rol interno.",
        ),
        (
            "Notas y tareas",
            "Gestión de casos",
            "Windows/Linux",
            IMPLEMENTED,
            "Prueba API",
            "CASE-05",
            "Notas y tareas quedan asociadas al caso y respetan autorización.",
        ),
        (
            "Advertencia de alcance",
            "Gobernanza",
            "Windows/Linux",
            IMPLEMENTED,
            "Prueba de flujo",
            "CASE-06",
            "Destinos sin alcance claro muestran aviso y no se presentan como autorizados.",
        ),
        (
            "Cierre y entrega",
            "Gobernanza",
            "Windows/Linux",
            IMPLEMENTED,
            "Prueba de flujo",
            "CASE-07",
            "El cierre conserva lista de revisión, entregables y riesgos residuales.",
        ),
    ],
)
add(
    "RECON",
    [
        (
            "Admitir entidades compatibles",
            "Recon pasivo",
            "Windows/Linux",
            IMPLEMENTED,
            "Prueba de servicio/API",
            "RECON-01",
            "Solo tipos admitidos y valores normalizados se guardan como objetivos.",
        ),
        (
            "Consultar fuentes pasivas",
            "Recon pasivo",
            "Windows/Linux",
            IMPLEMENTED,
            "Prueba con adaptadores simulados",
            "RECON-02",
            "El flujo usa únicamente adaptadores pasivos habilitados y configurados.",
        ),
        (
            "Conservar resultados parciales",
            "Recon pasivo",
            "Windows/Linux",
            IMPLEMENTED,
            "Prueba con fallos parciales",
            "RECON-03",
            "Resultados válidos sobreviven; fallos de proveedor aparecen como advertencias.",
        ),
        (
            "Sanear errores de proveedor",
            "Recon pasivo",
            "Windows/Linux",
            IMPLEMENTED,
            "Prueba de seguridad",
            "RECON-04",
            "Mensajes visibles no contienen claves, respuestas sensibles ni trazas internas.",
        ),
        (
            "Evitar expansión activa",
            "Seguridad",
            "Windows/Linux",
            IMPLEMENTED,
            "Inspección y prueba",
            "RECON-05",
            "El smoke autorizado no inicia barrido público, explotación ni enumeración de credenciales.",
        ),
    ],
)
add(
    "EVID",
    [
        (
            "Registrar evidencia",
            "Evidencia",
            "Windows/Linux",
            IMPLEMENTED,
            "Prueba API",
            "EVID-01",
            "La evidencia queda ligada al caso/objetivo con origen y fecha disponibles.",
        ),
        (
            "Normalizar hallazgos",
            "Hallazgos",
            "Windows/Linux",
            IMPLEMENTED,
            "Prueba de servicio",
            "EVID-02",
            "Los hallazgos usan un esquema normalizado y preservan su procedencia.",
        ),
        (
            "Marcar confianza",
            "Hallazgos",
            "Windows/Linux",
            IMPLEMENTED,
            "Prueba de servicio",
            "EVID-03",
            "La confianza se conserva como atributo explícito y no como certeza implícita.",
        ),
        (
            "Vincular hallazgo con evidencia",
            "Evidencia",
            "Windows/Linux",
            IMPLEMENTED,
            "Prueba de base de datos",
            "EVID-04",
            "Un hallazgo mantiene referencias a sus observaciones de origen.",
        ),
        (
            "Limitar contenido sensible",
            "Privacidad",
            "Windows/Linux",
            IMPLEMENTED,
            "Inspección de salida",
            "EVID-05",
            "Tokens, contraseñas y argumentos secretos no se exponen en vistas ni reportes.",
        ),
    ],
)
add(
    "TIME",
    [
        (
            "Registrar eventos de actividad",
            "Línea de tiempo",
            "Windows/Linux",
            IMPLEMENTED,
            "Prueba API",
            "TIME-01",
            "Los eventos relevantes se muestran con marca temporal y entidad asociada.",
        ),
        (
            "Registrar cambios de servicio",
            "Línea de tiempo",
            "Windows/Linux",
            IMPLEMENTED,
            "Prueba con muestras",
            "TIME-02",
            "Cambios de servicio se deduplican y contienen estado anterior/nuevo.",
        ),
        (
            "Registrar recuperación",
            "Línea de tiempo",
            "Windows/Linux",
            IMPLEMENTED,
            "Prueba de flujo",
            "TIME-03",
            "La recuperación queda correlacionada con el evento previo cuando hay evidencia.",
        ),
        (
            "Evitar spam de eventos",
            "Línea de tiempo",
            "Windows/Linux",
            IMPLEMENTED,
            "Prueba determinista",
            "TIME-04",
            "Muestras idénticas no producen eventos repetidos innecesarios.",
        ),
    ],
)
add(
    "CORR",
    [
        (
            "Correlación interna",
            "Correlación",
            "Windows/Linux",
            IMPLEMENTED,
            "Prueba de servicio",
            "CORR-01",
            "La correlación opera sobre evidencia almacenada y accesible al usuario.",
        ),
        (
            "Deduplicar indicadores",
            "Correlación",
            "Windows/Linux",
            IMPLEMENTED,
            "Prueba de servicio",
            "CORR-02",
            "Indicadores coincidentes se vinculan sin duplicar el registro fuente.",
        ),
        (
            "Explicar vínculos",
            "Correlación",
            "Windows/Linux",
            IMPLEMENTED,
            "Prueba de contrato",
            "CORR-03",
            "La interfaz conserva el indicador y la evidencia que soporta cada vínculo.",
        ),
        (
            "Controlar alcance",
            "Gobernanza",
            "Windows/Linux",
            IMPLEMENTED,
            "Prueba de autorización",
            "CORR-04",
            "Solo se correlacionan datos visibles para la investigación autorizada.",
        ),
    ],
)
add(
    "RPT",
    [
        (
            "Crear informes",
            "Informes",
            "Windows/Linux",
            IMPLEMENTED,
            "Prueba de integración",
            "RPT-01",
            "La solicitud genera un artefacto asociado a caso y solicitante.",
        ),
        (
            "Exportar PDF",
            "Informes",
            "Windows/Linux",
            IMPLEMENTED,
            "Estructura y MIME",
            "RPT-02",
            "El archivo PDF no está vacío, abre como PDF y contiene contexto RavenTech.",
        ),
        (
            "Exportar DOCX",
            "Informes",
            "Windows/Linux",
            IMPLEMENTED,
            "Prueba OOXML",
            "RPT-03",
            "El documento es un paquete DOCX válido y no contiene credenciales de prueba.",
        ),
        (
            "Exportar HTML y Markdown",
            "Informes",
            "Windows/Linux",
            IMPLEMENTED,
            "Prueba de contenido",
            "RPT-04",
            "Los artefactos son no vacíos, legibles y codificados con el tipo esperado.",
        ),
        (
            "Controlar descarga",
            "Informes",
            "Windows/Linux",
            IMPLEMENTED,
            "Prueba RBAC/API",
            "RPT-05",
            "Solo usuarios autorizados descargan informes de investigaciones accesibles.",
        ),
        (
            "Presentar conclusiones ejecutivas",
            "Informes",
            "Windows/Linux",
            IMPLEMENTED,
            "Revisión de contenido",
            "RPT-06",
            "El informe distingue evidencia, confianza, observación y recomendación.",
        ),
    ],
)
add(
    "MON",
    [
        (
            "Métricas del host",
            "Monitoreo",
            "Windows/Linux",
            IMPLEMENTED,
            "Prueba de proveedor/API",
            "MON-01",
            "CPU, memoria, discos, tiempo activo, SO y nombre del host se normalizan.",
        ),
        (
            "Refrescar resumen",
            "Monitoreo",
            "Windows/Linux",
            IMPLEMENTED,
            "Prueba de integración",
            "MON-02",
            "El resumen se refresca con intervalos y cooldowns acotados.",
        ),
        (
            "Inventario de procesos",
            "Monitoreo del host",
            "Windows/Linux",
            IMPLEMENTED,
            "Prueba de proveedor",
            "MON-03",
            "Se muestran PID, nombre, CPU/memoria y tiempos permitidos, sin argumentos.",
        ),
        (
            "Inventario de servicios",
            "Monitoreo del host",
            "Windows/Linux",
            IMPLEMENTED,
            "Prueba de proveedor",
            "MON-04",
            "El inventario distingue estado y fuente del proveedor local.",
        ),
        (
            "Acciones locales protegidas",
            "Administración local",
            "Windows/Linux",
            IMPLEMENTED,
            "Prueba simulada",
            "MON-05",
            "Acciones requieren rol/confirmación y rechazan proceso/servicio protegido.",
        ),
        (
            "Salud de servicios",
            "Monitoreo",
            "Windows/Linux",
            IMPLEMENTED,
            "Reglas deterministas",
            "MON-06",
            "La severidad considera baseline, criticidad, exposición y frescura.",
        ),
        (
            "Inventario de puertos locales",
            "Monitoreo",
            "Windows/Linux",
            IMPLEMENTED,
            "Prueba de proveedor",
            "MON-07",
            "Los sockets de escucha se presentan sin ejecutar comandos remotos.",
        ),
        (
            "Origen y frescura",
            "Monitoreo",
            "Windows/Linux",
            IMPLEMENTED,
            "Prueba de contrato",
            "MON-08",
            "Cada muestra incluye origen y tiempo, y la telemetría obsoleta se indica.",
        ),
    ],
)
add(
    "LAN",
    [
        (
            "Limitar red autorizada",
            "Monitoreo LAN",
            "Windows/Linux",
            IMPLEMENTED,
            "Prueba de política",
            "LAN-01",
            "Solo rangos privados configurados y autorizados admiten observación.",
        ),
        (
            "Registrar activos",
            "Activos LAN",
            "Windows/Linux",
            IMPLEMENTED,
            "Prueba API",
            "LAN-02",
            "Los activos conservan IP/MAC, disponibilidad y fecha de observación.",
        ),
        (
            "Observar servicios TCP",
            "Monitoreo LAN",
            "Windows/Linux",
            IMPLEMENTED,
            "Prueba acotada",
            "LAN-03",
            "La comprobación es TCP-connect acotada y no autentica ni envía payloads.",
        ),
        (
            "Expresar estado del puerto",
            "Monitoreo LAN",
            "Windows/Linux",
            IMPLEMENTED,
            "Prueba de contrato",
            "LAN-04",
            "Los estados open/closed/filtered/timeout/unknown conservan confianza.",
        ),
        (
            "Interpretar baseline de servicio",
            "Postura",
            "Windows/Linux",
            IMPLEMENTED,
            "Prueba de reglas",
            "LAN-05",
            "Un puerto abierto no se declara vulnerabilidad sin regla/evidencia.",
        ),
        (
            "Clasificar sistema y tipo",
            "Activos LAN",
            "Windows/Linux",
            IMPLEMENTED,
            "Prueba de clasificación",
            "LAN-06",
            "La clasificación registra fuente, evidencia y confianza; se desconoce ante falta de evidencia.",
        ),
        (
            "Presentar cambios",
            "Línea de tiempo",
            "Windows/Linux",
            IMPLEMENTED,
            "Prueba de deduplicación",
            "LAN-07",
            "Aperturas/cierres/cambios se registran una vez por transición observada.",
        ),
        (
            "Evitar control remoto",
            "Seguridad",
            "Windows/Linux",
            IMPLEMENTED,
            "Inspección y prueba",
            "LAN-08",
            "No se ejecutan órdenes, detenciones ni cambios de servicios remotos.",
        ),
        (
            "Observar interfaces, rutas y vecinos locales",
            "Proveedor LAN nativo",
            "Windows/Linux",
            IMPLEMENTED,
            "Pruebas deterministas de proveedor y aceptación nativa",
            "LAN-09",
            "El escritorio obtiene interfaces, rutas y vecinos mediante proveedores locales de solo lectura y registra el host RavenTech sin exigir el agente manual.",
        ),
        (
            "Descubrir activos agentless automáticamente",
            "Inventario LAN",
            "Windows/Linux",
            IMPLEMENTED,
            "Pruebas de integración y límites",
            "LAN-10",
            "Los vecinos autorizados y las respuestas TCP acotadas crean o actualizan activos sin requerir un agente; los activos nuevos quedan pendientes de revisión.",
        ),
        (
            "Seleccionar redes según rutas autorizadas",
            "Autorización LAN",
            "Windows/Linux",
            IMPLEMENTED,
            "Pruebas de intersección de ruta/CIDR",
            "LAN-11",
            "Solo se observa la intersección alcanzable entre rutas activas y CIDR RFC1918 configurados; destinos públicos y rutas no autorizadas se rechazan.",
        ),
        (
            "Acotar la detección activa",
            "Seguridad de red",
            "Windows/Linux",
            IMPLEMENTED,
            "Pruebas de límite de host, puerto y concurrencia",
            "LAN-12",
            "El descubrimiento usa como máximo 256 hosts y 32 puertos TCP configurados con concurrencia limitada; no ejecuta ICMP externo, autenticación ni comandos de protocolo.",
        ),
        (
            "Programar descubrimiento y observación de servicios",
            "Trabajos nativos",
            "Windows/Linux",
            IMPLEMENTED,
            "Pruebas de scheduler, deduplicación y cooldown",
            "LAN-13",
            "El descubrimiento periódico respeta un mínimo de 300 segundos y la observación de servicios 600 segundos, sin duplicar ciclos solapados.",
        ),
        (
            "Deduplicar identidad y conservar decisiones manuales",
            "Inventario LAN",
            "Windows/Linux",
            IMPLEMENTED,
            "Pruebas de identidad DHCP y preservación manual",
            "LAN-14",
            "MAC estable correlaciona cambios de IP; conflictos de reutilización de IP se omiten y no reemplazan nombres, autorización, criticidad ni notas manuales.",
        ),
        (
            "Representar evidencia y frescura de activos",
            "Inventario LAN",
            "Windows/Linux",
            IMPLEMENTED,
            "Pruebas de estado y transición de línea de tiempo",
            "LAN-15",
            "La presencia fuerte o TCP reciente puede indicar online; ausencia de vecinos por sí sola no marca offline y la falta de evidencia permanece unknown.",
        ),
        (
            "Clasificar dispositivo con confianza explícita",
            "Clasificación LAN",
            "Windows/Linux",
            IMPLEMENTED,
            "Pruebas de clasificación agentless y metadatos",
            "LAN-16",
            "Tipo y sistema operativo conservan origen, evidencia y confianza; señales pasivas débiles permanecen desconocidas o de confianza baja/media.",
        ),
        (
            "Informar medio físico solo con evidencia confiable",
            "Identidad de red",
            "Windows/Linux",
            IMPLEMENTED,
            "Pruebas de evidencia de medio de conexión",
            "LAN-17",
            "Ethernet o Wi-Fi se asignan únicamente por evidencia directa del operador/router; en otro caso el medio se presenta como desconocido.",
        ),
        (
            "Explicar visibilidad limitada del escritorio nativo",
            "Monitoreo LAN",
            "Windows/Linux",
            IMPLEMENTED,
            "Prueba de interfaz nativa y compatibilidad",
            "LAN-18",
            "El escritorio identifica el proveedor nativo y muestra CIDR, estado de vecinos y horarios; guía de Docker/ServerHost manual aparece solo en perfiles de compatibilidad.",
        ),
    ],
)
add(
    "AGENT",
    [
        (
            "Registrar ServerHost",
            "Agentes",
            "Windows/Linux",
            IMPLEMENTED,
            "Prueba de integración",
            "AGENT-01",
            "El agente de host reporta telemetría dentro del ámbito local autorizado.",
        ),
        (
            "Registrar LanEndpoint",
            "Agentes",
            "Windows/Linux",
            IMPLEMENTED,
            "Prueba de integración",
            "AGENT-02",
            "El endpoint informa telemetría; no recibe órdenes ejecutables.",
        ),
        (
            "Autenticar agente",
            "Agentes",
            "Windows/Linux",
            IMPLEMENTED,
            "Prueba de autenticación",
            "AGENT-03",
            "El enrolamiento/autenticación usa credenciales dedicadas y almacena solo material protegido.",
        ),
        (
            "Reportar metadatos de SO",
            "Agentes",
            "Windows/Linux",
            IMPLEMENTED,
            "Prueba de contrato",
            "AGENT-04",
            "Familia, nombre, versión evidenciada, arquitectura, host y modo se normalizan.",
        ),
        (
            "Mostrar frescura del agente",
            "Agentes",
            "Windows/Linux",
            IMPLEMENTED,
            "Prueba temporal",
            "AGENT-05",
            "Estado stale/offline se basa en marca temporal y umbral configurado.",
        ),
    ],
)
add(
    "POST",
    [
        (
            "Recomendar controles",
            "Postura",
            "Windows/Linux",
            IMPLEMENTED,
            "Prueba de reglas",
            "POST-01",
            "Las recomendaciones describen observación, relevancia, confianza y acción manual.",
        ),
        (
            "Reglas por tipo de dispositivo",
            "Postura",
            "Windows/Linux",
            IMPLEMENTED,
            "Prueba de reglas",
            "POST-02",
            "Las recomendaciones distinguen escritorio/servidor/móvil/router/IoT.",
        ),
        (
            "Baseline de vulnerabilidad",
            "Postura",
            "Windows/Linux",
            IMPLEMENTED,
            "Prueba de servicio",
            "POST-03",
            "El baseline usa observaciones almacenadas; no ejecuta exploit validation.",
        ),
        (
            "Estado explicable de exposición",
            "Postura",
            "Windows/Linux",
            IMPLEMENTED,
            "Prueba de reglas",
            "POST-04",
            "Cada warning/critical incluye una razón respaldada por datos.",
        ),
        (
            "Mantener advisory",
            "Seguridad",
            "Windows/Linux",
            IMPLEMENTED,
            "Revisión de contenido",
            "POST-05",
            "Inferencias no se expresan como vulnerabilidad o compromiso confirmado.",
        ),
    ],
)
add(
    "ALERT",
    [
        (
            "Crear alertas relevantes",
            "Alertas",
            "Windows/Linux",
            IMPLEMENTED,
            "Prueba de flujo",
            "ALERT-01",
            "Solo reglas configuradas y observaciones relevantes generan alertas.",
        ),
        (
            "Deduplicar y enfriar",
            "Alertas",
            "Windows/Linux",
            IMPLEMENTED,
            "Prueba determinista",
            "ALERT-02",
            "Dedupe/cooldown evita alertar en cada muestra normal.",
        ),
        (
            "Reconocer y silenciar",
            "Alertas",
            "Windows/Linux",
            IMPLEMENTED,
            "Prueba de integración",
            "ALERT-03",
            "Reconocimiento, mute/supresión y ventana de mantenimiento se respetan.",
        ),
        (
            "Generar notificación",
            "Notificaciones",
            "Windows/Linux",
            IMPLEMENTED,
            "Prueba API",
            "ALERT-04",
            "La notificación conserva tipo, destinatario interno y vínculo de triage.",
        ),
        (
            "Separar recomendación de alarma",
            "Postura",
            "Windows/Linux",
            IMPLEMENTED,
            "Prueba de reglas",
            "ALERT-05",
            "Un puerto abierto esperado no emite alerta por defecto.",
        ),
    ],
)
add(
    "OPS",
    [
        (
            "Centro de operaciones",
            "Operaciones",
            "Windows/Linux",
            IMPLEMENTED,
            "Prueba API/UI",
            "OPS-01",
            "El resumen incluye dependencias, trabajos y diagnósticos seguros.",
        ),
        (
            "Estado de runtime",
            "Operaciones",
            "Windows/Linux",
            IMPLEMENTED,
            "Prueba de contrato",
            "OPS-02",
            "Se distingue perfil desktop/docker/development y dependencias opcionales.",
        ),
        (
            "Respaldos",
            "Operaciones",
            "Windows/Linux",
            PARTIAL,
            "Prueba de integración/documentación",
            "OPS-03",
            "Las funciones disponibles crean y validan respaldo con permisos; no se afirma cobertura no implementada.",
        ),
        (
            "Validar restauración",
            "Operaciones",
            "Windows/Linux",
            PARTIAL,
            "Ensayo de restauración aislada",
            "OPS-04",
            "La validación dry-run no modifica base activa ni sustituye una prueba de recuperación.",
        ),
        (
            "Mostrar limitaciones",
            "Operaciones",
            "Windows/Linux",
            IMPLEMENTED,
            "Revisión de UX",
            "OPS-05",
            "Los diagnósticos presentan causa segura y siguiente paso sin traza cruda.",
        ),
    ],
)
add(
    "JOB",
    [
        (
            "Persistir trabajos",
            "Trabajos nativos",
            "Windows/Linux",
            IMPLEMENTED,
            "Prueba PostgreSQL",
            "JOB-01",
            "El trabajo permitido se almacena en PostgreSQL con tipo y estado tipados.",
        ),
        (
            "Despachar handlers allowlist",
            "Trabajos nativos",
            "Windows/Linux",
            IMPLEMENTED,
            "Prueba de rechazo",
            "JOB-02",
            "Tipos no registrados se rechazan y ningún payload selecciona código.",
        ),
        (
            "Reintentar con límites",
            "Trabajos nativos",
            "Windows/Linux",
            IMPLEMENTED,
            "Prueba determinista",
            "JOB-03",
            "Los reintentos son acotados, clasificados y con espera controlada.",
        ),
        (
            "Cancelar cooperativamente",
            "Trabajos nativos",
            "Windows/Linux",
            IMPLEMENTED,
            "Prueba determinista",
            "JOB-04",
            "La cancelación se revisa en límites seguros y no mata procesos del SO.",
        ),
        (
            "Recuperar leases obsoletos",
            "Trabajos nativos",
            "Windows/Linux",
            IMPLEMENTED,
            "Prueba PostgreSQL",
            "JOB-05",
            "Los leases vencidos se recuperan sin duplicar trabajos completados.",
        ),
        (
            "Exponer progreso seguro",
            "Trabajos nativos",
            "Windows/Linux",
            IMPLEMENTED,
            "Prueba API/RBAC",
            "JOB-06",
            "Operaciones muestra progreso/errores resumidos y acciones solo válidas.",
        ),
    ],
)
add(
    "DB",
    [
        (
            "PostgreSQL administrado",
            "Persistencia",
            "Windows/Linux",
            IMPLEMENTED,
            "Prueba de paquete y proceso",
            "DB-01",
            "La versión empaquetada inicializa solo una ruta administrada vacía y marcada.",
        ),
        (
            "PostgreSQL loopback",
            "Seguridad de datos",
            "Windows/Linux",
            IMPLEMENTED,
            "Inspección de config/socket",
            "DB-02",
            "La escucha predeterminada es loopback y no expone LAN/público.",
        ),
        (
            "Autenticación SCRAM",
            "Seguridad de datos",
            "Windows/Linux",
            IMPLEMENTED,
            "Inspección de pg_hba y conexión",
            "DB-03",
            "La autenticación normal exige SCRAM-SHA-256; no se usa trust.",
        ),
        (
            "Proteger datos existentes",
            "Persistencia",
            "Windows/Linux",
            IMPLEMENTED,
            "Pruebas de seguridad de ruta",
            "DB-04",
            "Datos desconocidos, externos o inicializados no se borran ni reinicializan.",
        ),
        (
            "Conservar migraciones",
            "Persistencia",
            "Windows/Linux",
            IMPLEMENTED,
            "Alembic current/heads/check",
            "DB-05",
            "Existe una cabeza lineal y el esquema coincide con migraciones.",
        ),
        (
            "Mantener compatibilidad externa",
            "Persistencia",
            "Windows/Linux",
            IMPLEMENTED,
            "Prueba por perfil",
            "DB-06",
            "Las conexiones externas/Docker preservan su URL y semántica configuradas.",
        ),
    ],
)
add(
    "DESK",
    [
        (
            "Iniciar componentes ordenados",
            "Desktop nativo",
            "Windows/Linux",
            IMPLEMENTED,
            "Prueba supervisor",
            "DESK-01",
            "El shell espera DB, migración, backend, worker y salud antes de Ready.",
        ),
        (
            "Cerrar componentes propios",
            "Desktop nativo",
            "Windows/Linux",
            IMPLEMENTED,
            "Prueba supervisor",
            "DESK-02",
            "El cierre cooperativo detiene solo procesos propiedad del runtime.",
        ),
        (
            "Frontend embebido",
            "Desktop nativo",
            "Windows/Linux",
            IMPLEMENTED,
            "Build y paquete",
            "DESK-03",
            "El empaquetado productivo no depende de Vite/puerto 5173.",
        ),
        (
            "Conservar rutas por plataforma",
            "Desktop nativo",
            "Windows/Linux",
            IMPLEMENTED,
            "Prueba de rutas",
            "DESK-04",
            "Windows usa LocalAppData; Linux respeta XDG y fallbacks documentados.",
        ),
        (
            "Detectar conflictos",
            "Desktop nativo",
            "Windows/Linux",
            IMPLEMENTED,
            "Prueba simulada",
            "DESK-05",
            "Puerto ocupado genera diagnóstico; no se finaliza el proceso ajeno.",
        ),
        (
            "Mostrar primer inicio",
            "Desktop nativo",
            "Windows/Linux",
            IMPLEMENTED,
            "Prueba UI/contrato",
            "DESK-06",
            "El primer inicio presenta progreso, estado y siguiente acción segura.",
        ),
        (
            "Mantener compatibilidad de desarrollo",
            "Perfiles",
            "Windows/Linux",
            IMPLEMENTED,
            "Configuración/build",
            "DESK-07",
            "Docker y desarrollo Python/Vite permanecen como perfiles distintos.",
        ),
    ],
)
add(
    "HOST",
    [
        (
            "CPU y memoria",
            "Proveedor de host",
            "Windows/Linux",
            IMPLEMENTED,
            "Prueba de proveedor",
            "HOST-01",
            "Métricas de CPU/memoria tienen unidades y fuente normalizadas.",
        ),
        (
            "Discos y uptime",
            "Proveedor de host",
            "Windows/Linux",
            IMPLEMENTED,
            "Prueba de proveedor",
            "HOST-02",
            "Capacidad/uso y tiempo activo se exponen sin datos personales.",
        ),
        (
            "Identidad OS/host",
            "Proveedor de host",
            "Windows/Linux",
            IMPLEMENTED,
            "Prueba de proveedor",
            "HOST-03",
            "Nombre, familia y arquitectura se reportan con evidencia del sistema.",
        ),
        (
            "Procesos",
            "Proveedor de host",
            "Windows/Linux",
            IMPLEMENTED,
            "Prueba de proveedor",
            "HOST-04",
            "PID/nombre/recurso/tiempo se exponen; argumentos y entorno no.",
        ),
        (
            "Servicios Windows",
            "Proveedor de host",
            "Windows",
            IMPLEMENTED,
            "Prueba SCM simulada",
            "HOST-05",
            "Inventario SCM presenta nombre, estado y capacidades sin shell genérico.",
        ),
        (
            "Servicios systemd",
            "Proveedor de host",
            "Linux",
            IMPLEMENTED,
            "Prueba D-Bus/fallback",
            "HOST-06",
            "Inventario systemd muestra estado y expone acción local solo si está disponible.",
        ),
        (
            "Puertos escuchando",
            "Proveedor de host",
            "Windows/Linux",
            IMPLEMENTED,
            "Prueba de proveedor",
            "HOST-07",
            "Los endpoints/listeners tienen formato compartido entre plataformas.",
        ),
        (
            "Interfaces y vecinos",
            "Proveedor de host",
            "Windows/Linux",
            IMPLEMENTED,
            "Prueba de proveedor",
            "HOST-08",
            "La interfaz recoge datos locales de interfaces/vecinos sin administración remota.",
        ),
        (
            "Negar procesos protegidos",
            "Seguridad local",
            "Windows/Linux",
            IMPLEMENTED,
            "Prueba con mocks",
            "HOST-09",
            "Los procesos protegidos/críticos no se terminan desde RavenTech.",
        ),
    ],
)
add(
    "AUD",
    [
        (
            "Auditar acciones",
            "Auditoría",
            "Windows/Linux",
            IMPLEMENTED,
            "Prueba de integración",
            "AUD-01",
            "Operaciones administrativas generan evento con sujeto/objeto/resultado saneados.",
        ),
        (
            "No registrar secretos",
            "Privacidad",
            "Windows/Linux",
            IMPLEMENTED,
            "Prueba de patrones",
            "AUD-02",
            "Tokens, claves y contraseñas no aparecen en auditoría, logs ni payloads.",
        ),
        (
            "Preservar procedencia",
            "Auditoría",
            "Windows/Linux",
            IMPLEMENTED,
            "Prueba de contrato",
            "AUD-03",
            "Acciones mantienen actor y hora para revisión administrativa.",
        ),
    ],
)
add(
    "I18N",
    [
        (
            "Interfaz bilingüe",
            "Localización",
            "Windows/Linux",
            IMPLEMENTED,
            "Prueba de catálogo/build",
            "I18N-01",
            "Etiquetas principales existen en español e inglés y conservan fallback.",
        ),
        (
            "Formato regional",
            "Localización",
            "Windows/Linux",
            PARTIAL,
            "Prueba visual/manual",
            "I18N-02",
            "Fechas/números son legibles; no se afirma localización exhaustiva de contenidos externos.",
        ),
    ],
)
add(
    "KNOW",
    [
        (
            "Referencias actuales",
            "Conocimiento",
            "Windows/Linux",
            PARTIAL,
            "Inspección funcional",
            "KNOW-01",
            "Las referencias integradas siguen disponibles y se distinguen de las fuentes locales importadas.",
        ),
        (
            "Importar vault o documentos seleccionados",
            "Conocimiento",
            "Windows/Linux",
            IMPLEMENTED,
            "Pruebas API y de ingestión",
            "KNOW-02",
            "Solo archivos elegidos por el operador se copian al almacén local y se indexan mediante trabajo nativo.",
        ),
        (
            "Parsear formatos locales soportados",
            "Conocimiento",
            "Windows/Linux",
            IMPLEMENTED,
            "Pruebas deterministas de parser",
            "KNOW-03",
            "Markdown, TXT, PDF, DOCX, HTML, JSON y CSV usan límites de tamaño y errores clasificados; otros tipos se omiten.",
        ),
        (
            "Preservar metadatos Obsidian seguros",
            "Conocimiento",
            "Windows/Linux",
            IMPLEMENTED,
            "Pruebas de parser Markdown",
            "KNOW-04",
            "Se extraen título, aliases, tags, estado, categoría y referencias permitidas sin ejecutar YAML.",
        ),
        (
            "Registrar procedencia y verificación",
            "Conocimiento",
            "Windows/Linux",
            IMPLEMENTED,
            "Pruebas de esquema e integración",
            "KNOW-05",
            "Documento y fragmento conservan fuente, nombre relativo, hash, sección, página disponible, confianza y verificación.",
        ),
        (
            "Sincronizar cambios incrementalmente",
            "Conocimiento",
            "Windows/Linux",
            IMPLEMENTED,
            "Pruebas de sincronización PostgreSQL",
            "KNOW-06",
            "Contenido sin cambios se omite; nuevas versiones reemplazan fragmentos; renombres preservan identidad cuando el hash es único y eliminaciones reconciliadas no borran originales.",
        ),
        (
            "Resolver relaciones Obsidian explícitas",
            "Conocimiento",
            "Windows/Linux",
            IMPLEMENTED,
            "Pruebas de grafo local",
            "KNOW-07",
            "Wikilinks/embeds crean relaciones explícitas con resolución local y profundidad acotada.",
        ),
        (
            "Buscar conocimiento local con filtros",
            "Conocimiento",
            "Windows/Linux",
            IMPLEMENTED,
            "Pruebas de búsqueda API",
            "KNOW-08",
            "Búsqueda local combina palabras clave y vector opcional, con filtros de fuente, confianza, verificación, idioma, categoría y tags.",
        ),
        (
            "Citar referencias locales estables",
            "Conocimiento e informes",
            "Windows/Linux",
            IMPLEMENTED,
            "Pruebas de salida PDF/DOCX/HTML/Markdown",
            "KNOW-09",
            "Los informes incluyen documentos locales solo cuando el operador selecciona sus identificadores y muestran procedencia sin rutas absolutas.",
        ),
        (
            "Administrar fuentes y estado de índice",
            "Conocimiento y operaciones",
            "Windows/Linux",
            IMPLEMENTED,
            "Pruebas RBAC/API/UI",
            "KNOW-10",
            "La fuente puede revisarse, sincronizarse, deshabilitarse o quitarse del índice sin borrar los originales seleccionados.",
        ),
        (
            "Aislar ingestión de archivos",
            "Seguridad y privacidad",
            "Windows/Linux",
            IMPLEMENTED,
            "Pruebas de límites y rutas",
            "KNOW-11",
            "La ingestión copia archivos elegidos, rechaza traversal/enlaces inseguros, no ejecuta contenido y no envía texto a proveedores externos automáticamente.",
        ),
        (
            "Indexar sin servicio externo de IA",
            "Conocimiento local",
            "Windows/Linux",
            IMPLEMENTED,
            "Prueba sin modelo/vector disponible",
            "KNOW-12",
            "El índice PostgreSQL y la búsqueda por palabras permanecen disponibles cuando no existe modelo local de embeddings.",
        ),
        (
            "Preparar recuperación RAG gobernada",
            "Conocimiento local",
            "Windows/Linux",
            IMPLEMENTED,
            "Revisión de separación y contratos",
            "KNOW-13",
            "La recuperación expone referencias y metadatos de confianza; el material importado no se incorpora a prompts externos automáticamente.",
        ),
    ],
)
add(
    "AI",
    [
        (
            "Descubrir proveedores y modelos dinámicamente",
            "Gateway de modelos AI",
            "Windows/Linux",
            IMPLEMENTED,
            "Pruebas de catálogo con fixtures",
            "AI-01",
            "El catálogo refleja solo proveedores/modelos informados por OpenCode o los proveedores locales soportados.",
        ),
        (
            "Clasificar ubicación y costo actual",
            "Gateway de modelos AI",
            "Windows/Linux",
            IMPLEMENTED,
            "Pruebas de metadatos",
            "AI-02",
            "Cada modelo disponible distingue local/remoto y free/paid/unknown sin prometer un precio futuro.",
        ),
        (
            "Aplicar modo de ejecución elegido",
            "Gateway de modelos AI",
            "Windows/Linux",
            IMPLEMENTED,
            "Pruebas de política/API",
            "AI-03",
            "Free only y Local only rechazan un modelo que no cumple el modo; no hay fallback pagado silencioso.",
        ),
        (
            "Persistir preferencias por usuario",
            "Gateway de modelos AI",
            "Windows/Linux",
            IMPLEMENTED,
            "Prueba PostgreSQL/RBAC",
            "AI-04",
            "La selección y el modo pertenecen al usuario autenticado y no guardan credenciales de proveedor.",
        ),
        (
            "Mantener sesiones de análisis acotadas",
            "Consola AI",
            "Windows/Linux",
            IMPLEMENTED,
            "Pruebas de persistencia y límites",
            "AI-05",
            "Las sesiones son propias del usuario, conservan solo mensajes visibles saneados y respetan límites configurados.",
        ),
        (
            "Transmitir y cancelar una respuesta",
            "Consola AI",
            "Windows/Linux",
            IMPLEMENTED,
            "Prueba SSE/cancelación",
            "AI-06",
            "Los deltas visibles llegan progresivamente cuando el proveedor lo soporta y la cancelación conserva la conversación.",
        ),
        (
            "Seleccionar y citar contexto Knowledge",
            "Consola AI y Knowledge",
            "Windows/Linux",
            IMPLEMENTED,
            "Pruebas de recuperación y citas",
            "AI-07",
            "Solo se envían extractos seleccionados y acotados; las citas generadas se validan contra IDs suministrados.",
        ),
        (
            "Generar una transferencia defensiva",
            "Consola AI",
            "Windows/Linux",
            IMPLEMENTED,
            "Prueba de plantilla/quoting",
            "AI-08",
            "El prompt y comando OpenCode se generan con datos saneados y se copian sin lanzar terminal ni ejecutarse.",
        ),
        (
            "Mostrar estado AI sin degradar el core",
            "Operations Center",
            "Windows/Linux",
            IMPLEMENTED,
            "Pruebas de contrato/RBAC",
            "AI-09",
            "Diagnóstico de OpenCode/modelos es administrativo, saneado y opcional para la salud central del producto.",
        ),
        (
            "Restringir AI integrada a análisis de chat",
            "Gateway de modelos AI",
            "Windows/Linux",
            IMPLEMENTED,
            "Prueba de perfil de permisos",
            "AI-10",
            "El perfil niega herramientas de shell, archivos, procesos, web y MCP y usa un workspace neutral fuera del repositorio.",
        ),
    ],
)
add(
    "BACK",
    [
        (
            "Crear respaldo local",
            "Respaldo",
            "Windows/Linux",
            PARTIAL,
            "Prueba de integración aislada",
            "BACK-01",
            "Las operaciones existentes usan ruta controlada y registran resultado seguro.",
        ),
        (
            "Validar respaldo",
            "Recuperación",
            "Windows/Linux",
            PARTIAL,
            "Prueba de validación",
            "BACK-02",
            "La validación no sobreescribe base activa y comunica limitaciones.",
        ),
        (
            "Restaurar con control",
            "Recuperación",
            "Windows/Linux",
            PARTIAL,
            "Ensayo fuera de producción",
            "BACK-03",
            "Toda restauración requiere acción administrativa explícita y objetivo aislado.",
        ),
    ],
)


NFR: list[tuple[str, str, str, str, str, str, str]] = []


def add_nfr(area: str, rows: list[tuple[str, str, str, str, str, str]]) -> None:
    for number, (
        name,
        requirement,
        platform,
        verification,
        test,
        criterion,
    ) in enumerate(rows, 1):
        NFR.append(
            (
                f"NFR-{area}-{number:03}",
                name,
                requirement,
                platform,
                verification,
                test,
                criterion,
            )
        )


add_nfr(
    "SEC",
    [
        (
            "PostgreSQL loopback",
            "PostgreSQL administrado escucha en loopback por defecto.",
            "Windows/Linux",
            "Inspección y socket",
            "SEC-01",
            "No existe listener PostgreSQL administrado en LAN/público.",
        ),
        (
            "SCRAM obligatorio",
            "La autenticación normal usa SCRAM-SHA-256 y secreto aleatorio por instalación.",
            "Windows/Linux",
            "Configuración y conexión",
            "SEC-02",
            "No se usa trust ni contraseña fija.",
        ),
        (
            "Protección de secretos",
            "Secretos no se escriben en logs, informes, paquetes ni metadatos de trabajos.",
            "Windows/Linux",
            "Escaneo de salida",
            "SEC-03",
            "El escaneo de artefactos/salidas no halla secretos de prueba.",
        ),
        (
            "Ejecución restringida",
            "El producto no ofrece ejecución arbitraria de shell/Python ni rutas ejecutables desde entrada.",
            "Windows/Linux",
            "Inspección estática y tests",
            "SEC-04",
            "Solo handlers y operaciones codificados/validados pueden ejecutarse.",
        ),
        (
            "Sin administración remota",
            "No se ejecutan comandos, detenciones o servicios en activos remotos.",
            "Windows/Linux",
            "Inspección de API/red",
            "SEC-05",
            "LanEndpoint permanece de telemetría; no hay canal de comando.",
        ),
        (
            "Alcance de red",
            "Observaciones LAN permanecen en rangos privados expresamente autorizados.",
            "Windows/Linux",
            "Pruebas de política",
            "SEC-06",
            "Direcciones fuera de alcance no reciben checks TCP/ICMP.",
        ),
        (
            "Control destructivo",
            "Acciones locales requieren permiso, confirmación y rechazo de objetos protegidos.",
            "Windows/Linux",
            "Pruebas simuladas",
            "SEC-07",
            "No se termina proceso protegido ni se controla objeto remoto.",
        ),
        (
            "Defensa exclusivamente",
            "No incluye brute force, credential testing, explotación, escaneo público ni persistencia.",
            "Windows/Linux",
            "Revisión de seguridad",
            "SEC-08",
            "Capacidad no está implementada ni se activa por configuración.",
        ),
    ],
)
add_nfr(
    "PRIV",
    [
        (
            "Minimización",
            "Solo se recoge información necesaria para caso, telemetría y operación.",
            "Windows/Linux",
            "Revisión de campos",
            "PRIV-01",
            "No se recolectan argumentos, entorno o datos de navegador por defecto.",
        ),
        (
            "Retención",
            "La retención sigue las políticas operativas configuradas y la acción administrativa.",
            "Windows/Linux",
            "Revisión de política",
            "PRIV-02",
            "La interfaz no promete borrado automático no existente.",
        ),
        (
            "Transparencia de inferencia",
            "La clasificación pasiva conserva fuente, confianza y evidencia.",
            "Windows/Linux",
            "Prueba de contrato",
            "PRIV-03",
            "Inferencia de dispositivo/OS no aparece como hecho de alta certeza sin agente.",
        ),
        (
            "Separación de datos",
            "El usuario solo ve registros permitidos por rol y membresía.",
            "Windows/Linux",
            "Pruebas RBAC",
            "PRIV-04",
            "No hay lectura cruzada de investigaciones sin permiso.",
        ),
    ],
)
add_nfr(
    "AI",
    [
        (
            "Propiedad de credenciales de proveedor",
            "Las credenciales permanecen en OpenCode o el proveedor local y nunca se duplican en la base RavenTech ni en el frontend.",
            "Windows/Linux",
            "Inspección de esquema y payloads",
            "AI-NFR-01",
            "Los registros AI conservan identificadores/preferencias, nunca valores de credenciales.",
        ),
        (
            "Conexión local acotada",
            "La integración de OpenCode/Ollama/LM Studio solo conecta con endpoints loopback y el workspace AI es neutral.",
            "Windows/Linux",
            "Pruebas de URL, workspace y recursos",
            "AI-NFR-02",
            "No se usa destino LAN/público ni el cwd/repositorio como directorio de proyecto OpenCode.",
        ),
        (
            "Transferencia explícita de contexto",
            "El operador ve el destino local/remoto y selecciona extractos antes de enviarlos.",
            "Windows/Linux",
            "Prueba UI/contrato de contexto",
            "AI-NFR-03",
            "No se carga vault, base de datos, inventario o logs completos automáticamente.",
        ),
        (
            "Aislamiento de instrucciones no confiables",
            "Datos Knowledge se delimitan como evidencia no confiable y el perfil de chat no admite ejecución de herramientas.",
            "Windows/Linux",
            "Pruebas de prompt-injection/permisos",
            "AI-NFR-04",
            "Las instrucciones dentro de extractos no amplían permisos ni autorizan acciones operativas.",
        ),
    ],
)
add_nfr(
    "KNOW",
    [
        (
            "Privacidad local de Knowledge",
            "El contenido, fragmentos y metadatos importados permanecen en almacenamiento local y no se envían a proveedores externos automáticamente.",
            "Windows/Linux",
            "Inspección de red y pruebas de configuración",
            "KNOW-NFR-01",
            "La ingestión, indexación y búsqueda funcionan sin solicitudes de red a proveedores de IA.",
        ),
        (
            "Límite de lectura del vault",
            "La sincronización puede leer únicamente el directorio de vault seleccionado y sus descendientes regulares.",
            "Windows/Linux",
            "Pruebas de traversal/enlaces",
            "KNOW-NFR-02",
            "Rutas fuera de raíz, symlinks y directorios excluidos no se leen ni modifican.",
        ),
        (
            "Parser acotado y no ejecutable",
            "Los parsers aplican límites de archivo y contenido activo no se ejecuta.",
            "Windows/Linux",
            "Pruebas de parser y carga malformada",
            "KNOW-NFR-03",
            "Un archivo malformado falla de forma aislada sin ejecutar macros, scripts ni adjuntos.",
        ),
        (
            "Reenlace local explícito",
            "Una fuente no disponible permanece offline hasta que el operador la religa mediante el selector nativo.",
            "Windows/Linux",
            "Pruebas de disponibilidad y relink",
            "KNOW-NFR-04",
            "La indisponibilidad no elimina índice ni cambia silenciosamente la ubicación de origen.",
        ),
    ],
)
add_nfr(
    "REL",
    [
        (
            "Inicio ordenado",
            "El supervisor declara Ready solo después de DB, migración, backend y worker.",
            "Windows/Linux",
            "Prueba de supervisor",
            "REL-01",
            "Fallo de dependencia evita estado Ready y no borra datos.",
        ),
        (
            "Cierre cooperativo",
            "Componentes propios cierran ordenadamente en secuencia.",
            "Windows/Linux",
            "Prueba de ciclo",
            "REL-02",
            "Procesos ajenos permanecen activos.",
        ),
        (
            "Recuperación no destructiva",
            "Fallos preservan el directorio cuando su propiedad/estado no puede probarse.",
            "Windows/Linux",
            "Prueba de rutas",
            "REL-03",
            "No se elimina ni reinicializa un directorio ambiguo.",
        ),
        (
            "Cola persistente",
            "Trabajos aceptados se registran en PostgreSQL y recuperan leases obsoletos de forma limitada.",
            "Windows/Linux",
            "Prueba concurrente",
            "REL-04",
            "No se ejecuta dos veces trabajo completado por recuperación.",
        ),
        (
            "Dependencias opcionales",
            "Redis/Celery no degradan desktop cuando se selecciona backend nativo.",
            "Windows/Linux",
            "Prueba de readiness",
            "REL-05",
            "PostgreSQL y worker nativo gobiernan disponibilidad de trabajos.",
        ),
    ],
)
add_nfr(
    "PERF",
    [
        (
            "Carga acotada",
            "Cola, concurrencia, cooldown y tamaño de muestras están limitados.",
            "Windows/Linux",
            "Prueba de límites",
            "PERF-01",
            "La cola respeta profundidad/concurrencia configurada.",
        ),
        (
            "Respuesta visual",
            "Las páginas muestran estados de carga, error recuperable y datos parciales.",
            "Windows/Linux",
            "Build/prueba UI",
            "PERF-02",
            "El usuario puede identificar espera o fallo sin congelación silenciosa.",
        ),
        (
            "Actualización de monitoreo",
            "El refresco automático respeta intervalo mínimo y no genera trabajos repetidos.",
            "Windows/Linux",
            "Prueba cooldown",
            "PERF-03",
            "La misma ventana de cooldown no crea duplicados.",
        ),
        (
            "Informe asíncrono",
            "Generación costosa usa trabajo persistente cuando se despacha como tarea.",
            "Windows/Linux",
            "Prueba de integración",
            "PERF-04",
            "El cliente recibe estado/progreso y descarga tras completion.",
        ),
    ],
)
add_nfr(
    "PORT",
    [
        (
            "Rutas por SO",
            "Los datos mutables usan LocalAppData en Windows y XDG en Linux.",
            "Windows/Linux",
            "Prueba de ruta",
            "PORT-01",
            "No depende de cwd ni de ancestry del repositorio.",
        ),
        (
            "Artefactos nativos",
            "Backend, worker y PostgreSQL se resuelven dentro de recursos empaquetados.",
            "Windows/Linux",
            "Validador de paquete",
            "PORT-02",
            "No requiere Python, Node, PostgreSQL CLI ni Docker instalado.",
        ),
        (
            "Contrato compartido",
            "El frontend consume esquemas normalizados de host entre Windows/Linux.",
            "Windows/Linux",
            "Pruebas de contrato",
            "PORT-03",
            "Campos específicos no requeridos no rompen la representación común.",
        ),
        (
            "Compatibilidad Docker",
            "El perfil Docker conserva configuración y hostname interno existente.",
            "Docker",
            "Compose config y smoke",
            "PORT-04",
            "El camino de desarrollo conserva Redis/Celery/PostgreSQL compatibles.",
        ),
    ],
)
add_nfr(
    "DATA",
    [
        (
            "Integridad referencial",
            "La base conserva referencias de propietario, caso y evidencia.",
            "Windows/Linux",
            "Pruebas DB",
            "DATA-01",
            "Las operaciones inválidas se rechazan sin registros huérfanos.",
        ),
        (
            "Migraciones lineales",
            "El esquema usa una única cabeza Alembic en la release evaluada.",
            "Windows/Linux",
            "Alembic current/heads/check",
            "DATA-02",
            "Una cabeza; current igual a head; sin drift.",
        ),
        (
            "Idempotencia",
            "Actualizaciones de postura, observaciones y trabajos evitan duplicación cuando es posible.",
            "Windows/Linux",
            "Pruebas repetidas",
            "DATA-03",
            "Una repetición no duplica resultados equivalentes según la política.",
        ),
        (
            "Procedencia",
            "Datos recolectados conservan fuente, fecha y confianza cuando aplica.",
            "Windows/Linux",
            "Revisión de modelo/API",
            "DATA-04",
            "La vista y el informe muestran contexto de evidencia.",
        ),
    ],
)
add_nfr(
    "OBS",
    [
        (
            "Diagnóstico seguro",
            "Errores visibles tienen código/categoría/resumen aptos para usuario.",
            "Windows/Linux",
            "Pruebas de fallo",
            "OBS-01",
            "No se exponen stack traces ni datos de conexión sensibles.",
        ),
        (
            "Estado del runtime",
            "El estado diferencia starting, healthy, degraded, failed, external y stopped.",
            "Windows/Linux",
            "Prueba de contrato",
            "OBS-02",
            "Cada estado contiene razón segura o acción siguiente cuando falla.",
        ),
        (
            "Trazabilidad",
            "Cambios relevantes y acciones administrativas incluyen actor y timestamp.",
            "Windows/Linux",
            "Prueba auditoría",
            "OBS-03",
            "El historial puede reconstruir evento sin argumentos sensibles.",
        ),
    ],
)
add_nfr(
    "UX",
    [
        (
            "Idioma",
            "La interfaz proporciona español e inglés para rutas operativas principales.",
            "Windows/Linux",
            "Prueba de catálogo",
            "UX-01",
            "Etiquetas accesibles de operación están disponibles en ambos idiomas.",
        ),
        (
            "Accesibilidad no cromática",
            "Estados no dependen solo del color.",
            "Windows/Linux",
            "Inspección de componentes",
            "UX-02",
            "Texto/icono acompaña estado y mantiene contraste legible.",
        ),
        (
            "Uso normal sin terminal",
            "Inicio normal no solicita comandos de shell al usuario.",
            "Windows/Linux",
            "Aceptación instalada",
            "UX-03",
            "La aplicación inicia componentes propios desde la UI.",
        ),
        (
            "Errores accionables",
            "La interfaz propone acción manual segura según categoría.",
            "Windows/Linux",
            "Prueba UI/contrato",
            "UX-04",
            "No sugiere borrar datos ambiguos ni matar procesos ajenos.",
        ),
    ],
)


SECTIONS: list[tuple[str, list[str]]] = [
    (
        "1. Propósito y alcance",
        [
            "Este documento especifica los requisitos verificables de RavenTech OSINT para la versión de producto 5.0.0-rc6. Describe el producto tal como existe y separa capacidades implementadas, capacidades parciales y capacidades futuras.",
            "El sistema está destinado al análisis OSINT autorizado y a la supervisión defensiva local. El uso requiere autorización documentada, alcance definido y revisión humana de hallazgos y recomendaciones.",
            "La especificación cubre cliente de escritorio Windows/Linux, frontend React embebido, backend FastAPI, PostgreSQL administrado o externo, worker PostgreSQL nativo, telemetría local/de endpoints, operaciones y exportaciones. No especifica hosting multi-tenant, SaaS, producto móvil ni ejecución ofensiva.",
        ],
    ),
    (
        "2. Convenciones, definiciones y prioridad",
        [
            "Cada requisito tiene identificador estable, plataforma, estado de implementación, método de verificación, área de prueba y criterio de aceptación. Implementado significa que existe comportamiento de producto; el criterio individual aún debe poder repetirse en la matriz de verificación.",
            "Los términos deberá/debe expresan un requisito obligatorio; debería expresa recomendación de diseño; puede describe capacidad permitida. Alta, media y baja expresan prioridad del requisito, no riesgo de seguridad del activo.",
            "Los estados funcionales son Implementado, Parcial, Planificado y Limitado por plataforma. Especificado identifica un requisito no funcional con criterio documentado cuya satisfacción se evalúa mediante su verificación. El estado de aceptación describe evidencia del producto y no certificación externa.",
        ],
    ),
    (
        "3. Contexto del producto",
        [
            "RavenTech OSINT es una aplicación local-first. La interfaz web embebida consume APIs autenticadas del backend. PostgreSQL conserva usuarios, casos, evidencia, telemetría, auditoría e información de trabajos. El worker nativo ejecuta handlers registrados desde código de aplicación.",
            "El perfil de escritorio supervisa el runtime en el mismo equipo. PostgreSQL puede ser administrado y empaquetado o una instancia externa configurada. Docker, Redis y Celery se conservan para desarrollo/compatibilidad, no son prerrequisitos del modo escritorio nativo.",
            "Integraciones externas OSINT, cuando están habilitadas, son proveedores de consulta con credenciales configuradas por el operador; los resultados son datos sujetos a validación, alcance y políticas del proveedor.",
        ],
    ),
    (
        "4. Arquitectura de alto nivel",
        [
            "Tauri es la carcasa nativa, supervisor y proveedor de telemetría del host. El frontend embebido presenta las vistas. FastAPI aplica autenticación, autorización, validación, reglas, persistencia, informes y APIs. PostgreSQL es la dependencia persistente requerida. El worker nativo toma trabajos mediante locking PostgreSQL y ejecuta únicamente handlers allowlist.",
            "El gateway AI opcional conecta el backend con un servidor OpenCode loopback o proveedores locales soportados. El backend conserva preferencias y sesiones de mensajes visibles; las credenciales quedan en el proveedor. La consola analiza en modo chat con herramientas denegadas y contexto Knowledge explícitamente seleccionado.",
            "El gateway AI opcional conecta el backend con un servidor OpenCode loopback o proveedores locales soportados. El backend conserva preferencias y sesiones de mensajes visibles; las credenciales quedan en el proveedor. La consola analiza en modo chat con herramientas denegadas y contexto Knowledge explícitamente seleccionado.",
            "Los agentes ServerHost/LanEndpoint son fuentes de telemetría. No exponen ejecución remota. Observaciones LAN se restringen a segmentos privados autorizados y a checks acotados.",
        ],
    ),
    (
        "5. Diagrama de arquitectura",
        [
            "La figura representa límites de confianza e intercambios principales. La UI no ejecuta acciones del sistema operativo por sí misma; las llamadas administrativas locales pasan por controles de autorización/confirmación del backend o del supervisor nativo.",
        ],
    ),
    (
        "6. Actores y clases de usuario",
        [
            "Administrador: gestiona usuarios, configuración operativa y acciones administrativas locales autorizadas. Analista: trabaja investigaciones accesibles, evidencia, hallazgos, reportes y monitoreo permitido. Operador de host: usuario local que inicia/cierra el desktop y revisa salud. Agente: proceso de telemetría autenticado, no interactivo y sin canal de comandos.",
            "Los permisos globales se separan de la membresía de investigación. La interfaz debe mostrar estados de acceso denegado sin revelar existencia o contenido que el usuario no esté autorizado a consultar.",
        ],
    ),
    (
        "7. Entorno operativo y plataformas",
        [
            "Windows: Tauri, artefactos nativos de backend/worker, PostgreSQL 16 administrado, métricas de host, inventario de procesos, SCM, sockets y vecinos. El instalador actual es unsigned y requiere WebView2 disponible en el sistema según el manifiesto.",
            "Linux x86_64: Tauri, backend/worker nativos, PostgreSQL administrado y rutas XDG. El proveedor usa interfaces locales como /proc, /sys, netlink y systemd/D-Bus cuando está disponible. Debian 13 x86_64 en WSL2 validó el paquete Linux actual, el inicio del proceso Tauri empaquetado, PostgreSQL administrado, backend/worker, migraciones y flujos API autenticados. Tras un reinicio controlado de procesos de prueba, el mismo perfil XDG reutilizó el clúster; el marcador, la versión mayor de PostgreSQL, el esquema y cinco usuarios sintéticos persistieron. Esto no valida el cierre normal de la GUI ni es aceptación de instalación limpia; la inspección visual de GUI Linux tampoco se ejecutó.",
            "La aceptación limpia Windows/Linux en VM independiente queda separada de las pruebas en host o WSL. Al corte documental, Windows clean-machine y Linux clean-machine no se ejecutaron; la inspección visual e interacción de Linux GUI tampoco.",
        ],
    ),
    (
        "8. Interfaces de usuario",
        [
            "Vistas principales: tablero, investigaciones, recon pasivo, hallazgos/evidencia, informes, Monitoring Center, LAN Assets, Endpoint Security Posture, Change Timeline, Notifications e Operations Center. El desktop aporta estado de runtime, primer inicio, diagnóstico y configuración local.",
            "RavenTech AI es una consola opcional para seleccionar proveedor/modelo, revisar ubicación local/remota, previsualizar contexto Knowledge y chatear/cancelar. Copiar un prompt OpenCode no ejecuta una terminal ni una acción.",
            "RavenTech AI es una consola opcional para seleccionar proveedor/modelo, revisar ubicación local/remota, previsualizar contexto Knowledge y chatear/cancelar. Copiar un prompt OpenCode no ejecuta una terminal ni una acción.",
            "Los componentes operativos muestran texto y/o icono además del color. Los errores se presentan en lenguaje de usuario con un siguiente paso seguro y sin stack trace, secretos o comandos arbitrarios.",
        ],
    ),
    (
        "9. Interfaces externas",
        [
            "La API HTTP local enlaza al loopback según perfil. Proveedores de OSINT se comunican únicamente cuando el operador activa la función, configura el proveedor y existe base legal/alcance. No se presupone disponibilidad de proveedor ni se ocultan fallos parciales.",
            "El runtime administrado usa binarios PostgreSQL empaquetados; el runtime externo respeta configuración explícita existente. La compatibilidad Docker conserva los nombres de servicio internos y las dependencias del perfil Docker.",
        ],
    ),
    (
        "10. Modelo de datos y retención",
        [
            "Las entidades de alto nivel incluyen usuario, investigación, membresía, objetivo, trabajo, hallazgo, evidencia, informe, notificación, telemetría, alerta, activo y evento de auditoría. Los identificadores y relaciones se almacenan en PostgreSQL; el esquema se administra mediante Alembic.",
            "Las preferencias, sesiones y mensajes visibles de AI se relacionan con el usuario autenticado. La base guarda proveedor/modelo y contexto/citas explícitos, no secretos de proveedor ni razonamiento oculto. Los límites de sesiones y mensajes acotan retención operativa.",
            "Las preferencias, sesiones y mensajes visibles de AI se relacionan con el usuario autenticado. La base guarda proveedor/modelo y contexto/citas explícitos, no secretos de proveedor ni razonamiento oculto. Los límites de sesiones y mensajes acotan retención operativa.",
            "Los secretos de autenticación se almacenan como hashes o material protegido según el subsistema. Los archivos de informe y respaldos se tratan como datos del operador, no como recursos de paquete. La política de retención depende de configuración y operación disponible; el producto no debe prometer borrado automático no implementado.",
        ],
    ),
    (
        "11. Requisitos funcionales",
        [
            "Las subsecciones siguientes son requisitos verificables. Las funciones indicadas como parciales requieren configuración, permisos o ambiente compatible. Las funciones marcadas no implementadas no deben presentarse como activas en la UI o la documentación.",
        ],
    ),
    (
        "12. Autenticación y autorización",
        [
            "La plataforma autentica usuarios, soporta refresh y revocación de sesión y valida el estado activo. El modo escritorio utiliza estado PostgreSQL para las necesidades que no deben depender de Redis. El RBAC se aplica tanto en rutas backend como en operaciones administrativas locales.",
        ],
    ),
    (
        "13. Investigaciones y gobernanza",
        [
            "Los casos documentan autorización, alcance, propietario y colaboradores. Advertencias de alcance son informativas y no sustituyen aprobación legal. Estados de revisión, tareas, notas, cierre y entrega mantienen contexto auditable.",
        ],
    ),
    (
        "14. Recon pasivo y fuentes",
        [
            "El flujo de recon consulta adaptadores pasivos configurados, valida entidades admitidas y conserva resultados parciales. Los errores de proveedor son advertencias sanitizadas. El usuario define el alcance y valida que tiene autorización.",
            "El alcance no incluye escaneo de puertos público, barrido de Internet, autenticación contra terceros, brute force, credential testing, explotación ni automatización de router. Los checks LAN permitidos están limitados a activos privados autorizados y controles acotados.",
        ],
    ),
    (
        "15. Evidencia, hallazgos, cronología y correlación",
        [
            "Los hallazgos conservan procedencia, confianza, timestamps y referencias a evidencia. La correlación relaciona observaciones almacenadas dentro del ámbito visible; no afirma compromiso o causalidad sin evidencia.",
            "La cronología une cambios relevantes del caso y monitoreo. Eventos repetidos se deduplican. Servicio abierto esperado se presenta como observación, no vulnerabilidad automática.",
        ],
    ),
    (
        "16. Informes",
        [
            "La plataforma exporta PDF, DOCX, HTML y Markdown. Los informes deben incluir contexto suficiente, alcance, fecha, fuentes, hallazgos, confianza, limitaciones y recomendaciones según plantilla. Descargas requieren autorización sobre la investigación.",
            "Los secretos, tokens, contraseñas, cadenas de conexión y argumentos de proceso no son contenido de informe. La generación puede operar como trabajo persistente con progreso, error seguro y cancelación cooperativa cuando aplique.",
        ],
    ),
    (
        "17. Monitoring Center y telemetría",
        [
            "El host principal reporta CPU, RAM, almacenamiento, uptime, SO, arquitectura, hostname, interfaces, procesos, servicios, sockets y vecinos, según capacidades del proveedor local. Los esquemas presentados a frontend son normalizados.",
            "Los procesos se muestran con PID y nombre visible y métricas permitidas; no se recolectan argumentos, variables de entorno, handles abiertos ni credenciales por defecto. Los inventarios pueden estar limitados por permisos del usuario local.",
        ],
    ),
    (
        "18. LAN Assets y agentes",
        [
            "En el escritorio nativo, el proveedor del host obtiene interfaces activas, rutas y vecinos desde APIs locales de Windows o las tablas locales de Linux. El worker programa discovery al inicio y periódicamente cuando el perfil LAN revisado está habilitado. El host RavenTech se registra como ServerHost local sin ejecutar manualmente PowerShell, iniciar un agente ni pegar un JWT.",
            "Los activos sin agente se registran desde vecinos autorizados y, solo cuando se habilita por separado, conectividad TCP acotada dentro de la intersección de rutas activas y CIDR privados RFC1918 autorizados. El máximo es 256 hosts, 32 puertos configurados y concurrencia limitada. La ausencia del agente o de entradas ARP/NDP no prueba que un dispositivo esté offline; segmentación, aislamiento y dispositivos inactivos limitan la visibilidad.",
            "Ethernet y Wi-Fi permanecen desconocidos salvo evidencia directa del operador o router. Agentes endpoint son opcionales y agregan telemetría; el discovery agentless no intenta autenticación, comandos de protocolo, acceso a router ni administración remota. La guía de ServerHost manual y limitaciones de vecinos Docker se muestran solo en perfiles de compatibilidad.",
            "La clasificación de activo usa agente autenticado primero, clasificación de operador, pistas de gateway, heurísticas y unknown como fallback. OS y device type retienen source/confidence/evidence. Vendor OUI puede aportar contexto, nunca certeza de clase por sí solo.",
            "Las observaciones de servicio incluyen puerto, guess, estado, confianza, primera/última observación, estado previo y relación con baseline. No se envían credenciales ni comandos de protocolo; banners crudos sensibles no se presentan.",
            "ServerHost/LanEndpoint aportan telemetría. El agente endpoint no admite ejecución de tareas remotas. Alta disponibilidad/controles dependen de conectividad y permisos de endpoint.",
        ],
    ),
    (
        "19. Salud y postura de seguridad",
        [
            "El servicio local se clasifica healthy, warning, critical o neutral a partir de baseline esperado, criticidad, salud, exposición, dispositivo y frescura. Cada warning/critical explica la razón. No se asigna severidad únicamente por puerto abierto o estado running.",
            "Las recomendaciones son asesoría manual y deben explicar observación, relevancia, confianza y acción sugerida. Para móvil/tablet no se aplican supuestos de escritorio/servidor; router/IoT no activa inscripción ni interacción remota.",
        ],
    ),
    (
        "20. Alertas, notificaciones y ventanas",
        [
            "Alertas se originan en reglas relevantes, con deduplicación, cooldown, reconocimiento, supresión y ventanas de mantenimiento disponibles según configuración. La notificación interna incluye vínculo de triage y estado leído/no leído.",
            "Un puerto abierto normal o esperado no genera alerta universal. La alerta reporta evidencia, alcance y severidad advisory, nunca compromiso confirmado sin evidencia.",
        ],
    ),
    (
        "21. Operations Center y trabajos nativos",
        [
            "El motor nativo persiste trabajos en PostgreSQL y ejecuta una registry allowlist. Los estados cubren encolado, programación, ejecución, reintento, completion, fallo y cancelación. Los payloads y resultados se saneán.",
            "La compatibilidad Celery/Redis continúa en el perfil Docker/desarrollo. En escritorio nativo, Redis y Celery son opcionales. La sincronización de fuentes Knowledge utiliza un handler nativo allowlist cuyo payload contiene solo el identificador de fuente.",
        ],
    ),
    (
        "22. Runtime nativo y gestión de PostgreSQL",
        [
            "Orden de inicio: lock, resolución de DB, PostgreSQL administrado si corresponde, readiness, migraciones, backend, health/readiness/release, worker/heartbeat, frontend y monitoreo. Orden de cierre: worker, backend, actividad de DB, PostgreSQL propio y lock.",
            "PostgreSQL administrado 16 usa directorio de datos por usuario, marker de propiedad, secreto por instalación, SCRAM-SHA-256 y binding loopback. El runtime no inicializa encima de datos desconocidos, no hace upgrade major automático, no ejecuta pg_resetwal y no borra cluster por recuperación.",
            "Una instancia externa o Docker no se detiene ni sustituye automáticamente. El usuario decide el modo de DB. FastAPI permanece como ejecutable separado; Tauri supervisa componentes, pero no instala servicio del sistema ni persistencia/autostart.",
        ],
    ),
    (
        "23. Auditoría, administración y respaldos",
        [
            "Las operaciones administrativas y cambios relevantes se registran con actor, tipo, recurso, hora y resultado saneados. No se registran argumentos sensibles no recogidos. El acceso a auditoría sigue RBAC.",
            "Backup/restore se considera parcial y explícitamente acotado a utilidades existentes y revisión humana. Una prueba dry-run no certifica recuperación de producción. Las pruebas usan una DB aislada.",
        ],
    ),
    (
        "24. Conocimiento: capacidad actual y límites",
        [
            "El operador puede importar documentos locales seleccionados o vincular un vault Obsidian mediante el selector nativo. Para el vault, la ruta canónica queda privada en la base local para habilitar sincronización manual; una fuente offline conserva los documentos indexados y requiere relink explícito si se mueve. Las cargas individuales quedan como snapshots administrados por RavenTech.",
            "La ingesta/indexación utiliza trabajo PostgreSQL nativo, hash SHA-256, parser con lista de tipos y límites, estado de confianza/revisión explícito, tags, búsqueda local y grafo Obsidian de vínculos explícitos. Embeddings locales son opcionales; la búsqueda por palabras permanece disponible.",
            "Las referencias importadas no se consideran verificadas por importarlas. Solo documentos elegidos expresamente se agregan como citas en un informe. La ingesta, búsqueda, cita y filtrado no envían contenido a un proveedor externo; la recuperación RAG se limita a contratos gobernados, con referencias y separación de datos.",
            "La sincronización compara hashes y evita reparsear documentos sin cambios, conserva identidad cuando un renombre es inequívoco y reconcilia relaciones. Los documentos eliminados se quitan del índice cuando se puede completar un recorrido válido; los fallos de lectura preservan registros existentes. Quitar una fuente elimina solo el snapshot e índice RavenTech cuya propiedad se verifica; nunca elimina el vault original.",
        ],
    ),
    (
        "25. Requisitos no funcionales",
        [
            "Los requisitos NFR especifican atributos de seguridad, privacidad, confiabilidad, rendimiento, portabilidad, integridad, observabilidad y usabilidad. Su estado es Especificado: el criterio está documentado para verificación, sin afirmar una medición universal en todas las plataformas. Los límites numéricos dependen de equipo de prueba y perfil; se documentan umbrales operativos donde están configurados en producto.",
        ],
    ),
    (
        "26. Seguridad, privacidad y límites de red",
        [
            "La plataforma es defensiva y de uso autorizado. La autenticación y RBAC limitan acceso. PostgreSQL administrado no se expone a LAN/público. La telemetría minimiza datos. Los secretos no aparecen en UI/logs/manifest/reportes.",
            "No se implementa ejecución arbitraria de shell/Python, eval/exec, importación dinámica desde payload, ejecución remota, SSH/WinRM/WMI/PsExec, task kill o servicio remoto, router automation, firewall changes, escaneo público, brute force, credential testing, explotación, persistence/autostart o updater automático.",
        ],
    ),
    (
        "27. Disponibilidad, rendimiento y recuperación",
        [
            "La UI debe diferenciar fallo del proceso, dependencia no lista y telemetría obsoleta. Los trabajos poseen heartbeat, retries bounded, lease recovery y cancellation cooperativa. Cualquier recuperación deja intactos los datos cuya pertenencia/estado es ambiguo.",
            "El producto no promete HA distribuida ni SLA. El servicio desktop está disponible mientras el usuario mantiene la aplicación ejecutándose y la base requerida está accesible. Redis/Celery no condicionan la disponibilidad nativa de flujos migrados.",
        ],
    ),
    (
        "28. Portabilidad, compatibilidad y despliegue",
        [
            "Los paquetes Windows/Linux incluyen los recursos nativos necesarios según manifiestos y excluyen datos de usuario. PostgreSQL no se empaqueta inicializado. El entorno mutable usa rutas plataforma nativas, no el directorio de binarios ni el repositorio.",
            "El instalador Windows actual es unsigned, modo usuario actual. Linux package se construye para x86_64 y requiere bibliotecas/plataforma desktop identificadas en el manifiesto. La compatibilidad de una instalación limpia se valida aparte.",
        ],
    ),
    (
        "29. Aceptación del producto y estado de validación",
        [
            "Para 5.0.0-rc6, la documentación de aceptación registra prueba Windows empaquetada aislada, PostgreSQL administrado, worker, autenticación, reportes, recon pasivo y flujos de operaciones. La máquina Windows limpia independiente no estaba disponible en esta ejecución y permanece NOT RUN.",
            "Debian 13 x86_64/WSL registra validación del paquete actual y del arranque Tauri empaquetado con PostgreSQL administrado, migraciones, backend, worker, autenticación, APIs de Monitoring/Operations/Posture/Timeline/Notifications, reportes y recon pasivo. Un reinicio controlado del perfil XDG reutilizó el clúster existente y conservó el marcador y cinco usuarios sintéticos. El inventario local systemd vía D-Bus devolvió unidades; los proveedores nativos de métricas y procesos pasaron pruebas Linux. No se afirma cierre normal de GUI, instalación limpia ni inspección visual de GUI Linux; el resultado es evidencia de runtime Linux en WSL.",
            "Los criterios detallados se expresan como procedimiento repetible. Una PASS en un entorno no implica certificación en otro. La tabla de trazabilidad remite a los planes de prueba por subsistema.",
        ],
    ),
    (
        "30. Criterios de aceptación",
        [
            "La release candidata se acepta para pruebas de operador cuando: una sola head Alembic; current=head; sin drift; backend test suite pasa; paquetes cumplen manifiestos/checksums; DB administrada usa SCRAM y loopback; el runtime conserva datos; la UI está embebida; el worker ejecuta handlers allowlist; Redis/Celery no son requisito en perfil desktop; no aparecen secretos.",
            "La aceptación Windows clean-machine se marca separadamente. La aceptación limpia solo se completa en máquina/VM realmente independiente, sin checkout o dependencias de desarrollo. Ningún resultado de WSL puede sustituir esa evidencia.",
            "Los workflows críticos se verifican con cuentas temporales aleatorias y base aislada: login, profile, refresh rotation, logout/revocation, RBAC, Dashboard, cases, Monitoring, Operations, posture, timeline, notification, report formats y passive recon.",
        ],
    ),
    (
        "31. Trazabilidad de requisitos",
        [
            "La matriz vincula cada requisito funcional/no funcional con subsistema, plataforma, estado, método, área de prueba y criterio. Los IDs de test representan procedimientos de aceptación reproducibles; no son números de fases ni un resultado de test individual.",
        ],
    ),
    (
        "32. Límites conocidos y evolución",
        [
            "El software es candidato local no firmado; no hay actualización automática. La aceptación Linux clean-machine y la inspección visual/funcional de Tauri GUI Linux deben ejecutarse por separado. El paquete x86_64 y el runtime core fueron validados en Debian 13 WSL2; otras distribuciones no se presumen validadas. Las acciones systemd dependen del entorno/permisos y no se ejercieron en esta ejecución. Capacidades de backup/restore y algunos proveedores OSINT externos también dependen del entorno.",
            "La ruta del vault Obsidian se conserva de forma privada en la base local para sincronización manual; las cargas de documentos individuales continúan como snapshots administrados. Al mover la base a otro equipo, la ruta original puede quedar offline y requiere relink explícito. No hay OCR ni comprensión de imágenes. La confianza es una declaración revisable, no una prueba automática de veracidad.",
        ],
    ),
    (
        "33. Glosario",
        [
            "Activo: dispositivo/red autorizado representado en Monitoring. Agente: proceso autenticado que reporta telemetría. Baseline: estado o exposición esperada configurada. Confianza: fuerza de evidencia que respalda clasificación. Evidencia: observación con fuente y tiempo. Handler: función nativa explícitamente registrada para trabajo. Host principal: equipo local donde se ejecuta el desktop. Perfil runtime: selección desktop/docker/development. SCRAM-SHA-256: mecanismo de autenticación de PostgreSQL. Trabajo: unidad persistente ejecutada por worker nativo. Fuente Knowledge: registro con procedencia y límite de lectura. Snapshot documental: copia local administrada de archivos seleccionados individualmente.",
        ],
    ),
    (
        "34. Referencias y control documental",
        [
            "Fuentes de producto consultadas: README, arquitectura, API, esquema de datos, modelo de seguridad, manual de operador, documentación de runtime nativo y PostgreSQL administrado, monitoreo local/LAN, postura de endpoints, límites conocidos, checklist final y validadores de paquete incluidos en el repositorio.",
            "El identificador de documento es RavenTech-OSINT-SRS-ES. Versión documental 1.0; versión de producto 5.0.0-rc6; estado candidato de lanzamiento; idioma español; fecha de emisión 2026-09-24. La próxima revisión debe conservar trazabilidad y distinguir requisitos nuevos de capacidades existentes.",
        ],
    ),
]


def esc(value: str) -> str:
    return escape(value).replace("\n", "<br/>")


def build_markdown() -> str:
    lines = [
        "# Especificación de requisitos de software (SRS)",
        "## RavenTech OSINT",
        "",
        "- Identificador: RavenTech-OSINT-SRS-ES  ",
        f"- Versión del documento: {DOCUMENT_VERSION}  ",
        f"- Versión del producto: {PRODUCT_VERSION}  ",
        f"- Estado: {STATUS}  ",
        f"- Fecha: {ISSUE_DATE}  ",
        "- Idioma: español",
        "",
        "> Especificación basada en las capacidades actuales del candidato de producto. Los elementos futuros se identifican explícitamente como no implementados.",
        "",
        "## Control de cambios",
        "| Versión | Fecha | Cambio | Estado |",
        "|---|---|---|---|",
        f"| {DOCUMENT_VERSION} | {ISSUE_DATE} | Actualización de requisitos verificables de descubrimiento LAN y visibilidad de activos | Candidato de lanzamiento |",
        "",
        "## Contenido",
    ]
    lines.extend(f"- {title}" for title, _ in SECTIONS)
    lines.append("")
    for title, paragraphs in SECTIONS:
        lines.extend([f"## {title}", ""])
        lines.extend(paragraphs)
        lines.append("")
        if title == "5. Diagrama de arquitectura":
            lines.extend(
                [
                    "```mermaid",
                    "flowchart LR",
                    "  U[Operador] --> T[Tauri Desktop]",
                    "  T --> UI[React embebido]",
                    "  UI --> API[FastAPI local]",
                    "  API <--> PG[(PostgreSQL)]",
                    "  API --> W[Worker nativo PostgreSQL]",
                    "  T --> H[Proveedor de host]",
                    "  A[ServerHost / LanEndpoint] --> API",
                    "  API --> C[Casos, OSINT, postura, alertas]",
                    "  API --> R[PDF / DOCX / HTML / Markdown]",
                    "  API --> K[Referencias de conocimiento actuales]",
                    "```",
                    "",
                ]
            )
        if title == "22. Runtime nativo y gestión de PostgreSQL":
            lines.extend(
                [
                    "```text",
                    "Inicio: Desktop -> lock -> PostgreSQL -> readiness -> migraciones -> backend -> worker -> monitoring -> Ready",
                    "Cierre: worker -> backend -> cierre de actividad DB -> PostgreSQL propio -> lock",
                    "```",
                    "",
                ]
            )
        if title == "11. Requisitos funcionales":
            for row in FR:
                lines.extend(
                    [
                        f"### {row[0]} — {row[1]}",
                        "",
                        f"Subsistema: {row[2]}.",
                        "",
                        f"Requisito: El sistema deberá ofrecer o aplicar {row[1].lower()}. Criterio de aceptación: {row[7]}",
                        "",
                        f"Plataforma: {row[3]}. Estado: {row[4]}. Verificación: {row[5]}. Caso de prueba: {row[6]}.",
                        "",
                    ]
                )
        if title == "25. Requisitos no funcionales":
            for row in NFR:
                lines.extend(
                    [
                        f"### {row[0]} — {row[1]}",
                        "",
                        row[2],
                        "",
                        f"Plataforma: {row[3]}. Estado: {NFR_SPECIFIED}. Verificación: {row[4]}. Caso de prueba: {row[5]}. Criterio: {row[6]}",
                        "",
                    ]
                )
        if title == "31. Trazabilidad de requisitos":
            lines.extend(
                [
                    "| ID | Nombre | Subsistema | Plataforma | Estado | Verificación | Prueba | Aceptación |",
                    "|---|---|---|---|---|---|---|---|",
                ]
            )
            lines.extend("| " + " | ".join(row) + " |" for row in FR)
            lines.extend(
                "| "
                + " | ".join(
                    (
                        row[0],
                        row[1],
                        "No funcional",
                        row[3],
                        NFR_SPECIFIED,
                        row[4],
                        row[5],
                        row[6],
                    )
                )
                + " |"
                for row in NFR
            )
    lines.extend(
        [
            "",
            "## Anexo A. Criterios de aceptación ejecutables",
            "",
            "| Caso | Flujo | Aceptación |",
            "|---|---|---|",
            "| AT-01 | Desktop Windows aislado | Runtime administrado, backend/worker sanos, release correcto; clean-machine se registra aparte. |",
            "| AT-02 | Persistencia | Relanzar no reinicializa base sana y conserva el registro de prueba. |",
            "| AT-03 | Autenticación | Login, perfil, rotación, revocación y rechazo de token anterior. |",
            "| AT-04 | Operaciones | Dashboard, casos, monitoring, operaciones, postura, timeline e inbox autorizados. |",
            "| AT-05 | Informes | PDF/DOCX/HTML/Markdown válidos, no vacíos y sin secretos. |",
            "| AT-06 | Recon | Smoke pasivo autorizado conserva entidades válidas y advierte fallas parciales. |",
            "| AT-07 | Linux core | Debian 13 x86_64 WSL2: paquete actual, arranque Tauri empaquetado, PostgreSQL administrado, migraciones, backend/worker y APIs autenticadas; no implica GUI visual ni clean-machine. |",
            "| AT-08 | Esquema | Una cabeza Alembic; current=head; check sin drift. |",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def register_fonts() -> None:
    import reportlab

    font_dir = Path(reportlab.__file__).parent / "fonts"
    pdfmetrics.registerFont(TTFont("Vera", str(font_dir / "Vera.ttf")))
    pdfmetrics.registerFont(TTFont("Vera-Bold", str(font_dir / "VeraBd.ttf")))
    pdfmetrics.registerFont(TTFont("Vera-Italic", str(font_dir / "VeraIt.ttf")))
    pdfmetrics.registerFontFamily(
        "Vera",
        normal="Vera",
        bold="Vera-Bold",
        italic="Vera-Italic",
        boldItalic="Vera-Bold",
    )


class Diagram(Flowable):
    def __init__(self, kind: str):
        super().__init__()
        self.kind = kind
        self.width = 168 * mm
        self.height = 72 * mm if kind == "architecture" else 47 * mm

    def draw(self) -> None:
        canvas = self.canv
        canvas.saveState()
        canvas.setLineWidth(0.8)
        canvas.setStrokeColor(colors.HexColor("#486581"))
        canvas.setFillColor(colors.HexColor("#edf4f8"))
        if self.kind == "architecture":
            boxes = [
                (5, 50, 52, 16, "Desktop Tauri"),
                (63, 50, 52, 16, "UI React embebida"),
                (121, 50, 42, 16, "Operador"),
                (5, 25, 48, 16, "FastAPI"),
                (59, 25, 48, 16, "Worker nativo"),
                (113, 25, 50, 16, "PostgreSQL"),
                (5, 1, 48, 16, "Host local"),
                (59, 1, 48, 16, "Agentes LAN"),
                (113, 1, 50, 16, "Reportes / casos"),
            ]
            for x, y, w, h, label in boxes:
                canvas.roundRect(
                    x * mm, y * mm, w * mm, h * mm, 3 * mm, fill=1, stroke=1
                )
                canvas.setFillColor(colors.HexColor("#183b56"))
                canvas.setFont("Vera-Bold", 7.5)
                canvas.drawCentredString((x + w / 2) * mm, (y + 6.2) * mm, label)
                canvas.setFillColor(colors.HexColor("#edf4f8"))
            arrows = [
                ((57, 58), (63, 58)),
                ((115, 58), (121, 58)),
                ((29, 50), (29, 41)),
                ((53, 33), (59, 33)),
                ((107, 33), (113, 33)),
                ((29, 25), (29, 17)),
                ((83, 25), (83, 17)),
                ((138, 25), (138, 17)),
            ]
            canvas.setStrokeColor(colors.HexColor("#627d98"))
            for (x1, y1), (x2, y2) in arrows:
                canvas.line(x1 * mm, y1 * mm, x2 * mm, y2 * mm)
                canvas.line(x2 * mm, y2 * mm, (x2 - 1.4) * mm, (y2 + 1.5) * mm)
                canvas.line(x2 * mm, y2 * mm, (x2 + 1.4) * mm, (y2 + 1.5) * mm)
        else:
            labels = [
                "1. Shell + lock",
                "2. PostgreSQL",
                "3. Migraciones",
                "4. Backend",
                "5. Worker",
                "6. UI + host",
                "7. Ready",
            ]
            x0, width, gap, y = 1, 22 * mm, 2.1 * mm, 24 * mm
            canvas.setFont("Vera-Bold", 6.4)
            for i, label in enumerate(labels):
                x = x0 + i * (width + gap)
                canvas.setFillColor(colors.HexColor("#e7f5ee" if i == 6 else "#edf4f8"))
                canvas.roundRect(x, y, width, 15 * mm, 2 * mm, fill=1, stroke=1)
                canvas.setFillColor(colors.HexColor("#183b56"))
                canvas.drawCentredString(x + width / 2, y + 6 * mm, label)
                if i < len(labels) - 1:
                    nx = x + width + gap
                    canvas.setStrokeColor(colors.HexColor("#627d98"))
                    canvas.line(x + width, y + 7.5 * mm, nx, y + 7.5 * mm)
                    canvas.line(nx, y + 7.5 * mm, nx - 1.5 * mm, y + 9 * mm)
                    canvas.line(nx, y + 7.5 * mm, nx - 1.5 * mm, y + 6 * mm)
            canvas.setFillColor(colors.HexColor("#5c6f82"))
            canvas.setFont("Vera", 7)
            canvas.drawCentredString(
                self.width / 2,
                7 * mm,
                "Cierre cooperativo: Worker → Backend → PostgreSQL propio → lock",
            )
        canvas.restoreState()


def build_pdf() -> None:
    register_fonts()
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="TitleCustom",
            parent=styles["Title"],
            fontName="Vera-Bold",
            fontSize=24,
            leading=30,
            textColor=colors.HexColor("#16324f"),
            alignment=TA_CENTER,
            spaceAfter=12,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Subtitle",
            fontName="Vera",
            fontSize=13,
            leading=19,
            textColor=colors.HexColor("#486581"),
            alignment=TA_CENTER,
            spaceAfter=8,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Heading1Custom",
            fontName="Vera-Bold",
            fontSize=15.5,
            leading=20,
            textColor=colors.HexColor("#16324f"),
            spaceBefore=6,
            spaceAfter=11,
            keepWithNext=True,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Heading2Custom",
            fontName="Vera-Bold",
            fontSize=10.5,
            leading=14,
            textColor=colors.HexColor("#256d85"),
            spaceBefore=7,
            spaceAfter=5,
            keepWithNext=True,
        )
    )
    styles.add(
        ParagraphStyle(
            name="BodyCustom",
            fontName="Vera",
            fontSize=8.5,
            leading=13.2,
            textColor=colors.HexColor("#243b53"),
            spaceAfter=7,
            alignment=TA_LEFT,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Small",
            fontName="Vera",
            fontSize=6.4,
            leading=8.3,
            textColor=colors.HexColor("#243b53"),
        )
    )
    styles.add(
        ParagraphStyle(
            name="SmallBold",
            fontName="Vera-Bold",
            fontSize=6.4,
            leading=8.3,
            textColor=colors.HexColor("#243b53"),
        )
    )
    styles.add(
        ParagraphStyle(
            name="Meta",
            fontName="Vera",
            fontSize=9,
            leading=15,
            textColor=colors.HexColor("#334e68"),
            alignment=TA_CENTER,
        )
    )
    styles.add(
        ParagraphStyle(
            name="TOCHeading",
            fontName="Vera-Bold",
            fontSize=10,
            leading=13,
            textColor=colors.HexColor("#16324f"),
            leftIndent=0,
            firstLineIndent=0,
            spaceBefore=3,
        )
    )
    styles.add(
        ParagraphStyle(
            name="TOCSub",
            fontName="Vera",
            fontSize=7.5,
            leading=10,
            textColor=colors.HexColor("#486581"),
            leftIndent=14,
            firstLineIndent=0,
        )
    )

    class Doc(SimpleDocTemplate):
        def afterFlowable(self, flowable):
            if (
                isinstance(flowable, Paragraph)
                and flowable.style.name == "Heading1Custom"
            ):
                title = flowable.getPlainText()
                key = f"srs-{self.page:03d}"
                self.canv.bookmarkPage(key)
                self.canv.addOutlineEntry(title, key, 0, False)
                self.notify("TOCEntry", (0, title, self.page, key))

    def page(canvas, doc):
        canvas.saveState()
        w, h = A4
        if doc.page > 1:
            canvas.setStrokeColor(colors.HexColor("#d9e2ec"))
            canvas.line(20 * mm, h - 16 * mm, w - 20 * mm, h - 16 * mm)
            canvas.setFont("Vera", 7)
            canvas.setFillColor(colors.HexColor("#627d98"))
            canvas.drawString(
                20 * mm, h - 12 * mm, "RavenTech OSINT · SRS ES · v" + DOCUMENT_VERSION
            )
            canvas.drawRightString(w - 20 * mm, 10 * mm, f"Página {doc.page}")
            canvas.drawString(
                20 * mm, 10 * mm, "RavenTech OSINT · Documento de producto v1.0"
            )
        canvas.restoreState()

    PDF.parent.mkdir(parents=True, exist_ok=True)
    SOURCE.parent.mkdir(parents=True, exist_ok=True)
    markdown = build_markdown()
    markdown = "\n".join(line.rstrip() for line in markdown.splitlines()) + "\n"
    SOURCE.write_text(markdown, encoding="utf-8")
    doc = Doc(
        str(PDF),
        pagesize=A4,
        rightMargin=19 * mm,
        leftMargin=19 * mm,
        topMargin=22 * mm,
        bottomMargin=18 * mm,
        title="Especificación de requisitos de software — RavenTech OSINT",
        author="RavenTech OSINT",
        subject="SRS en español, producto 5.0.0-rc6",
    )
    story = [
        Spacer(1, 37 * mm),
        Paragraph(
            "ESPECIFICACIÓN DE<br/>REQUISITOS DE SOFTWARE", styles["TitleCustom"]
        ),
        Paragraph("RavenTech OSINT", styles["Subtitle"]),
        Spacer(1, 11 * mm),
        Paragraph("SRS · Versión documental " + DOCUMENT_VERSION, styles["Subtitle"]),
        Spacer(1, 10 * mm),
    ]
    cover = [
        ["Versión del producto", PRODUCT_VERSION],
        ["Estado", STATUS],
        ["Fecha de emisión", ISSUE_DATE],
        ["Idioma", "Español"],
        ["Identificador", "RavenTech-OSINT-SRS-ES"],
    ]
    cover_table = Table(
        [
            [Paragraph(esc(a), styles["SmallBold"]), Paragraph(esc(b), styles["Small"])]
            for a, b in cover
        ],
        colWidths=[55 * mm, 92 * mm],
        hAlign="CENTER",
    )
    cover_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#edf4f8")),
                ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#bcccdc")),
                ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#d9e2ec")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story += [
        cover_table,
        Spacer(1, 24 * mm),
        Paragraph(
            "Especificación del producto en su estado actual. No es certificación, autorización de uso ni promesa de disponibilidad de proveedores externos.",
            styles["Meta"],
        ),
        PageBreak(),
    ]
    story += [
        Paragraph("Control documental", styles["Heading1Custom"]),
        Paragraph(
            "Versión 1.0 · Emisión inicial · Candidato de lanzamiento RC6 · Responsable: Ingeniería de producto RavenTech OSINT.",
            styles["BodyCustom"],
        ),
        Paragraph(
            "Propósito. Establecer requisitos funcionales y no funcionales comprobables, sus límites, plataformas y criterios de aceptación. Este documento registra el estado real de producto y marca capacidades futuras como no implementadas.",
            styles["BodyCustom"],
        ),
        Paragraph(
            "Criterio de interpretación. Los estados de implementación describen capacidad de producto. La matriz de pruebas ofrece procedimientos y criterios verificables; no sustituye la ejecución de una aceptación específica ni certifica un entorno no probado.",
            styles["BodyCustom"],
        ),
        Paragraph("Control de cambios", styles["Heading2Custom"]),
        simple_table(
            [
                ["Versión", "Fecha", "Descripción", "Estado"],
                [
                    DOCUMENT_VERSION,
                    ISSUE_DATE,
                    "Especificación inicial del producto y trazabilidad",
                    "RC6",
                ],
            ],
            [18 * mm, 24 * mm, 89 * mm, 30 * mm],
            styles,
        ),
        PageBreak(),
    ]
    toc = TableOfContents()
    toc.levelStyles = [styles["TOCHeading"], styles["TOCSub"]]
    story += [Paragraph("Contenido", styles["Heading1Custom"]), toc, PageBreak()]
    story += [Paragraph("Resumen ejecutivo", styles["Heading1Custom"])]
    story += [
        Paragraph(
            "RavenTech OSINT integra gestión de investigación autorizada, recolección pasiva de OSINT, hallazgos y evidencia, reportes, monitoreo de host/LAN/endpoints y postura defensiva. El escritorio normal es local: Tauri supervisa PostgreSQL administrado, backend y worker nativo, mientras sirve la interfaz React embebida.",
            styles["BodyCustom"],
        ),
        Paragraph(
            "El perfil desktop requiere PostgreSQL, pero no requiere Docker, Redis, Celery, Python, Node/Vite ni lanzamiento manual de procesos. El perfil Docker/desarrollo continúa disponible. Los resultados de agentes y heurísticas conservan origen/confianza. Todo control remoto y función ofensiva permanece fuera de alcance.",
            styles["BodyCustom"],
        ),
        Paragraph("Estado de validación al corte", styles["Heading2Custom"]),
        simple_table(
            [
                ["Entorno", "Resultado documentado", "Límite"],
                [
                    "Windows host-isolated",
                    "PASS (runtime y flujos API)",
                    "No es clean-machine; inspección visual no se afirma",
                ],
                ["Windows clean-machine", "NOT RUN", "No VM/Sandbox disponible"],
                [
                    "Linux Debian/WSL core",
                    "PASS en runtime/paquete",
                    "No equivale a Linux clean-machine",
                ],
                [
                    "Linux Tauri GUI / clean-machine",
                    "NOT RUN",
                    "Aceptación separada pendiente",
                ],
            ],
            [37 * mm, 51 * mm, 73 * mm],
            styles,
        ),
        PageBreak(),
    ]

    for title, paragraphs in SECTIONS:
        story.append(Paragraph(esc(title), styles["Heading1Custom"]))
        for paragraph in paragraphs:
            story.append(Paragraph(esc(paragraph), styles["BodyCustom"]))
        if title == "5. Diagrama de arquitectura":
            story += [
                Spacer(1, 4 * mm),
                Diagram("architecture"),
                Paragraph(
                    "Las flechas representan flujo funcional/local; la comunicación con endpoint agents es de telemetría autorizada. No hay canal de ejecución remota.",
                    styles["Small"],
                ),
            ]
        if title == "11. Requisitos funcionales":
            groups: dict[str, list[tuple[str, str, str, str, str, str, str, str]]] = {}
            for row in FR:
                groups.setdefault(row[0].split("-")[1], []).append(row)
            for group, rows in groups.items():
                story.append(Paragraph(esc(group), styles["Heading2Custom"]))
                data = [
                    [
                        "ID / Nombre",
                        "Requisito y criterio de aceptación",
                        "Verificación / prueba",
                    ]
                ]
                for row in rows:
                    data.append(
                        [
                            Paragraph(
                                f"<b>{esc(row[0])}</b><br/>{esc(row[1])}"
                                f"<br/><font size='5.8'>{esc(row[3])} · {esc(row[4])}</font>",
                                styles["Small"],
                            ),
                            Paragraph(
                                f"El sistema deberá ofrecer o aplicar {esc(row[1].lower())}. "
                                f"Criterio de aceptación: {esc(row[7])}",
                                styles["Small"],
                            ),
                            Paragraph(
                                f"{esc(row[5])}<br/>Caso {esc(row[6])}",
                                styles["Small"],
                            ),
                        ]
                    )
                story.append(
                    make_table(data, [37 * mm, 92 * mm, 34 * mm], styles, font=6.1)
                )
                story.append(Spacer(1, 2 * mm))
        if title == "22. Runtime nativo y gestión de PostgreSQL":
            story += [Spacer(1, 3 * mm), Diagram("startup")]
        if title == "25. Requisitos no funcionales":
            data = [["ID / atributo", "Requisito", "Verificación y criterio"]]
            for row in NFR:
                data.append(
                    [
                        Paragraph(
                            f"<b>{esc(row[0])}</b><br/>{esc(row[1])}"
                            f"<br/><font size='5.8'>{esc(row[3])} · Estado: {NFR_SPECIFIED}</font>",
                            styles["Small"],
                        ),
                        Paragraph(esc(row[2]), styles["Small"]),
                        Paragraph(
                            f"{esc(row[4])} · {esc(row[5])}<br/>Aceptación: {esc(row[6])}",
                            styles["Small"],
                        ),
                    ]
                )
            story.append(
                make_table(data, [38 * mm, 70 * mm, 55 * mm], styles, font=6.1)
            )
        if title == "29. Aceptación del producto y estado de validación":
            data = [["Prueba", "Procedimiento", "Criterio", "Estado conocido"]]
            checks = [
                (
                    "AT-01 Runtime Windows",
                    "Lanzar artefacto actual sin componentes Docker.",
                    "DB/backend/worker Ready; salud y versión válidas.",
                    "PASS host-isolated; clean-machine NOT RUN",
                ),
                (
                    "AT-02 Persistencia",
                    "Cerrar y relanzar sobre clúster aislado existente.",
                    "No repite initdb; conserva registro de prueba.",
                    "PASS documentado",
                ),
                (
                    "AT-03 Auth",
                    "Cuenta temporal: login, profile, refresh, logout, revocación.",
                    "Token rotado; token anterior/revocado rechazado.",
                    "PASS documentado",
                ),
                (
                    "AT-04 Casos y operaciones",
                    "Consultar tablero, casos, monitoring, operaciones, postura, timeline, inbox.",
                    "API autorizada devuelve contratos coherentes.",
                    "PASS documentado",
                ),
                (
                    "AT-05 Informes",
                    "Crear PDF/DOCX/HTML/Markdown con caso aislado.",
                    "Artefactos válidos, no vacíos y sin secretos.",
                    "PASS documentado",
                ),
                (
                    "AT-06 Recon",
                    "Ejecutar smoke pasivo autorizado.",
                    "Entidades válidas; fallos parciales como advertencias.",
                    "PASS documentado",
                ),
                (
                    "AT-07 Linux core",
                    "Runtime Debian/WSL sin GUI/clean-machine claim.",
                    "DB, migraciones, backend/worker y proveedores core.",
                    "PASS WSL documentado",
                ),
                (
                    "AT-08 Alembic",
                    "current, heads, check contra DB aislada.",
                    "Una head; current=head; no drift.",
                    "PASS en aceptación anterior",
                ),
            ]
            data.extend(
                [
                    [
                        Paragraph(esc(c), styles["SmallBold"]),
                        Paragraph(esc(p), styles["Small"]),
                        Paragraph(esc(a), styles["Small"]),
                        Paragraph(esc(s), styles["Small"]),
                    ]
                    for c, p, a, s in checks
                ]
            )
            story.append(
                make_table(data, [29 * mm, 49 * mm, 47 * mm, 38 * mm], styles, font=6.1)
            )
        if title == "31. Trazabilidad de requisitos":
            data = [
                [
                    "ID",
                    "Nombre",
                    "Subsistema",
                    "SO",
                    "Estado",
                    "Verificación",
                    "Test",
                    "Aceptación",
                ]
            ]
            for row in FR:
                data.append(
                    [
                        Paragraph(esc(v), styles["Small"])
                        for v in [
                            row[0],
                            row[1],
                            row[2],
                            row[3],
                            row[4],
                            row[5],
                            row[6],
                            row[7],
                        ]
                    ]
                )
            for row in NFR:
                data.append(
                    [
                        Paragraph(esc(v), styles["Small"])
                        for v in [
                            row[0],
                            row[1],
                            "No funcional",
                            row[3],
                            NFR_SPECIFIED,
                            row[4],
                            row[5],
                            row[6],
                        ]
                    ]
                )
            story.append(
                make_table(
                    data,
                    [
                        14 * mm,
                        24 * mm,
                        21 * mm,
                        15 * mm,
                        23 * mm,
                        25 * mm,
                        17 * mm,
                        31 * mm,
                    ],
                    styles,
                    font=5.7,
                )
            )
        story.append(PageBreak())
    story.pop()  # discard trailing page break
    doc.multiBuild(story, onFirstPage=page, onLaterPages=page)


def simple_table(rows: list[list[str]], widths: list[float], styles) -> Table:
    data = [
        [
            Paragraph(
                esc(str(cell)), styles["SmallBold"] if ri == 0 else styles["Small"]
            )
            for cell in row
        ]
        for ri, row in enumerate(rows)
    ]
    return make_table(data, widths, styles, font=7)


def make_table(
    data: list[list], widths: list[float], styles, font: float = 6.3
) -> Table:
    header_style = ParagraphStyle(
        name="TableHeader" + str(font),
        fontName="Vera-Bold",
        fontSize=font,
        leading=font + 2,
        textColor=colors.white,
    )
    header = []
    for cell in data[0]:
        raw = cell.getPlainText() if isinstance(cell, Paragraph) else str(cell)
        header.append(Paragraph(esc(raw), header_style))
    data = [header, *data[1:]]
    table = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT", splitByRow=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#16324f")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Vera-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), font),
                ("LEADING", (0, 0), (-1, -1), font + 2),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#bcccdc")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [colors.white, colors.HexColor("#f5f8fa")],
                ),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


if __name__ == "__main__":
    build_pdf()
    print(f"Source: {SOURCE}")
    print(f"PDF: {PDF}")
    print(f"Functional requirements: {len(FR)}")
    print(f"Non-functional requirements: {len(NFR)}")
