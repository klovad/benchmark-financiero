"""Constantes de las fuentes externas: URLs, sub-portales, nombres de carpeta, ids de
descarga. No dependen del entorno; cambian solo cuando cambia el sitio de origen."""

# --- Superbancos: CAPCOL y Boletín (Playwright, plugin Share-one-Drive) -------------------
CAPCOL_URL = "https://www.superbancos.gob.ec/estadisticas/portalestudios/capcol-bancos/"
CAPCOL_INSTITUCIONES_PUBLICAS_URL = "https://www.superbancos.gob.ec/estadisticas/portalestudios/capcol-instituciones-publicas/"

# Sub-portales CAPCOL: mismo plugin, mismo layout de carpetas y mismas hojas BASE (ver
# docs/fuentes_datos.md sección 1.1). tipo_entidad NO se infiere del dato -- lo fija el
# sub-portal del que vino el archivo. subdir="" conserva el layout histórico de bancos
# privados (data/raw/{año}/{cartera|depositos}) sin mover archivos ya descargados.
CAPCOL_PORTALES = {
    "privada": {"url": CAPCOL_URL, "tipo_entidad": "BANCO PRIVADO", "subdir": ""},
    "publica": {
        "url": CAPCOL_INSTITUCIONES_PUBLICAS_URL,
        "tipo_entidad": "BANCO PUBLICO",
        "subdir": "banca_publica",
    },
}
TIPOS_ENTIDAD_CAPCOL = {p["tipo_entidad"] for p in CAPCOL_PORTALES.values()}
BOLETIN_URL = "https://www.superbancos.gob.ec/estadisticas/portalestudios/bancos/"

# Nombres de carpeta usados por el portal CAPCOL para cada reporte. Antes de 2024 se
# llamaban COLOCACIONES/CAPTACIONES; desde 2024 se renombraron a CARTERA/DEPOSITOS.
FOLDER_NAMES = {
    "cartera": ["CARTERA", "COLOCACIONES"],
    "depositos": ["DEPOSITOS", "CAPTACIONES"],
}

# --- BCE: tasas de interés (descarga directa) ---------------------------------------------
# Tasas semanales por banco. Convención de nombres t{s|m}{p|a} = tasas + (semanal|mensual)
# + (pasiva|activa); solo se integran las semanales (tsp/tsa) -- decisión explícita del
# usuario, ver docs/fuentes_datos.md sección 2.
BCE_BASE_URL = (
    "https://contenido.bce.fin.ec/documentos/Estadisticas/SectorMonFin/TasasInteres"
)
BCE_URLS = {
    "tsp": f"{BCE_BASE_URL}/tsp_desde_200801.zip",
    "tsa": f"{BCE_BASE_URL}/tsa_desde_200801.zip",
}

# --- SEPS: cooperativas S1-S3 + mutualistas (descarga directa) ----------------------------
# Plugin "Simple Download Monitor" de WordPress -- sin Playwright. Los download_id no
# siguen ningún patrón derivable del año: se recolectaron a mano del portal
# (estadisticas.seps.gob.ec/index.php/estadisticas-sfps/, 2026-09-30). Al agregar un año
# nuevo, copiar el id del link del año en cada sección:
#   captaciones  -> Depósitos > Reportes (ZIP con Boletin_captaciones_*_{S1,S2,S3,Mut}.xlsm)
#   colocaciones -> Cartera de crédito > Reportes, 2da fila (ZIP con
#                   Reporte_colocaciones_*.xlsm = SALDOS de cartera, no volumen)
#   eeff         -> Situación Financiera > Bases de Datos, 1ra fila (TSV, 6 dígitos)
# Ver docs/fuentes_datos.md sección 4.0.
SEPS_DOWNLOAD_URL = (
    "https://estadisticas.seps.gob.ec/?sdm_process_download=1&download_id={id}"
)
SEPS_DOWNLOAD_IDS = {
    2021: {"captaciones": 906, "colocaciones": 1023, "eeff": 895},
    2022: {"captaciones": 1133, "colocaciones": 1129, "eeff": 1818},
    2023: {"captaciones": 1847, "colocaciones": 1830, "eeff": 1387},
    2024: {"captaciones": 2365, "colocaciones": 2370, "eeff": 2330},
    2025: {"captaciones": 2795, "colocaciones": 2799, "eeff": 2773},
    # Año en curso (2026-10-09): la SEPS reemplaza el ZIP al agregar meses, con el mismo
    # download_id; download_seps.py detecta la versión nueva (HEAD + _descarga.json).
    2026: {"captaciones": 3263, "colocaciones": 3274, "eeff": 3258},
}
