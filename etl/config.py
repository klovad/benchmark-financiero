import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / os.getenv("SCRAPER_DOWNLOAD_DIR", "data/raw")

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

# BCE: tasas de interés semanales por banco. Convención de nombres t{s|m}{p|a} = tasas +
# (semanal|mensual) + (pasiva|activa); solo se integran las semanales (tsp/tsa) --
# decisión explícita del usuario, ver docs/fuentes_datos.md sección 2.
BCE_BASE_URL = (
    "https://contenido.bce.fin.ec/documentos/Estadisticas/SectorMonFin/TasasInteres"
)
BCE_URLS = {
    "tsp": f"{BCE_BASE_URL}/tsp_desde_200801.zip",
    "tsa": f"{BCE_BASE_URL}/tsa_desde_200801.zip",
}
BCE_DIR = RAW_DIR / "bce"

# SEPS (cooperativas S1-S3 + mutualistas): descarga directa desde el plugin "Simple
# Download Monitor" de WordPress -- sin Playwright. Los download_id no siguen ningún
# patrón derivable del año: se recolectaron a mano del portal
# (estadisticas.seps.gob.ec/index.php/estadisticas-sfps/, 2026-09-30). Al agregar un año
# nuevo, copiar el id del link del año en cada sección:
#   captaciones  -> Depósitos > Reportes (ZIP con Boletin_captaciones_*_{S1,S2,S3,Mut}.xlsm)
#   colocaciones -> Cartera de crédito > Reportes, 2da fila (ZIP con
#                   Reporte_colocaciones_*.xlsm = SALDOS de cartera, no volumen)
#   eeff         -> Situación Financiera > Bases de Datos, 1ra fila (TSV, 6 dígitos)
# Ver docs/fuentes_datos.md sección 4.0.
SEPS_DIR = RAW_DIR / "seps"
SEPS_DOWNLOAD_URL = (
    "https://estadisticas.seps.gob.ec/?sdm_process_download=1&download_id={id}"
)
SEPS_DOWNLOAD_IDS = {
    2021: {"captaciones": 906, "colocaciones": 1023, "eeff": 895},
    2022: {"captaciones": 1133, "colocaciones": 1129, "eeff": 1818},
    2023: {"captaciones": 1847, "colocaciones": 1830, "eeff": 1387},
    2024: {"captaciones": 2365, "colocaciones": 2370, "eeff": 2330},
    2025: {"captaciones": 2795, "colocaciones": 2799, "eeff": 2773},
}
# Entidades de segundo piso que la SEPS publica junto a las cooperativas (sql/29).
SEPS_RUC_SEGUNDO_PISO = {
    "1768168480001",  # CONAFIPS
    "1791708040001",  # CAJA CENTRAL FINANCOOP
}

DB_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "localhost"),
    "port": int(os.getenv("POSTGRES_PORT", "5432")),
    "dbname": os.getenv("POSTGRES_DB", "benchmark_cartera_depositos"),
    "user": os.getenv("POSTGRES_USER", "bp_etl"),
    "password": os.getenv("POSTGRES_PASSWORD", "changeme"),
}

DEFAULT_YEARS = [
    int(y) for y in os.getenv("SCRAPER_YEARS", "2021,2022,2023,2024,2025").split(",")
]

# Nombres de carpeta usados por el portal CAPCOL para cada reporte. Antes de 2024 se
# llamaban COLOCACIONES/CAPTACIONES; desde 2024 se renombraron a CARTERA/DEPOSITOS.
FOLDER_NAMES = {
    "cartera": ["CARTERA", "COLOCACIONES"],
    "depositos": ["DEPOSITOS", "CAPTACIONES"],
}

# Mapea palabras clave encontradas en el NOMBRE DE LA HOJA 'BASE ...' al tipo_credito
# canónico (no el nombre del archivo: el archivo "Cartera de Vivienda" en realidad trae
# DOS hojas BASE -inmobiliario y vivienda de interés público-, cada una un tipo_credito
# distinto según la ficha metodológica de Superbancos). El orden importa: "vivienda
# interes" se evalúa antes que "inmobiliario" porque ambas palabras pueden coexistir.
TIPO_CREDITO_KEYWORDS = {
    "vivienda interes": "vivienda_interes_publico",
    "inmobiliario": "inmobiliario",
    "productivo": "comercial",
    "consumo": "consumo",
    "microcredito": "microcredito",
    "educativo": "educativo",
    # Solo Banca Pública: hoja 'BASE B PUBLICA INVERSION PUBLIC(A)'.
    "inversion": "inversion_publica",
}

# Región geográfica de cada provincia del Ecuador (el archivo de cartera no trae región,
# solo depositos la incluye; se deriva aquí para tener el dato en ambos reportes).
PROVINCIA_REGION = {
    "AZUAY": "SIERRA",
    "BOLIVAR": "SIERRA",
    "CAÑAR": "SIERRA",
    "CARCHI": "SIERRA",
    "COTOPAXI": "SIERRA",
    "CHIMBORAZO": "SIERRA",
    "IMBABURA": "SIERRA",
    "LOJA": "SIERRA",
    "PICHINCHA": "SIERRA",
    "TUNGURAHUA": "SIERRA",
    "SANTO DOMINGO DE LOS TSACHILAS": "SIERRA",
    "EL ORO": "COSTA",
    "ESMERALDAS": "COSTA",
    "GUAYAS": "COSTA",
    "LOS RIOS": "COSTA",
    "MANABI": "COSTA",
    "SANTA ELENA": "COSTA",
    "MORONA SANTIAGO": "ORIENTE",
    "NAPO": "ORIENTE",
    "ORELLANA": "ORIENTE",
    "PASTAZA": "ORIENTE",
    "SUCUMBIOS": "ORIENTE",
    "ZAMORA CHINCHIPE": "ORIENTE",
    "GALAPAGOS": "INSULAR",
}
