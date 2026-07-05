import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / os.getenv("SCRAPER_DOWNLOAD_DIR", "data/raw")

CAPCOL_URL = "https://www.superbancos.gob.ec/estadisticas/portalestudios/capcol-bancos/"

DB_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "localhost"),
    "port": int(os.getenv("POSTGRES_PORT", "5432")),
    "dbname": os.getenv("POSTGRES_DB", "benchmark_cartera_depositos"),
    "user": os.getenv("POSTGRES_USER", "bp_etl"),
    "password": os.getenv("POSTGRES_PASSWORD", "changeme"),
}

DEFAULT_YEARS = [int(y) for y in os.getenv("SCRAPER_YEARS", "2021,2022,2023,2024,2025").split(",")]

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
}

# Región geográfica de cada provincia del Ecuador (el archivo de cartera no trae región,
# solo depositos la incluye; se deriva aquí para tener el dato en ambos reportes).
PROVINCIA_REGION = {
    "AZUAY": "SIERRA", "BOLIVAR": "SIERRA", "CAÑAR": "SIERRA", "CARCHI": "SIERRA",
    "COTOPAXI": "SIERRA", "CHIMBORAZO": "SIERRA", "IMBABURA": "SIERRA", "LOJA": "SIERRA",
    "PICHINCHA": "SIERRA", "TUNGURAHUA": "SIERRA", "SANTO DOMINGO DE LOS TSACHILAS": "SIERRA",
    "EL ORO": "COSTA", "ESMERALDAS": "COSTA", "GUAYAS": "COSTA", "LOS RIOS": "COSTA",
    "MANABI": "COSTA", "SANTA ELENA": "COSTA",
    "MORONA SANTIAGO": "ORIENTE", "NAPO": "ORIENTE", "ORELLANA": "ORIENTE",
    "PASTAZA": "ORIENTE", "SUCUMBIOS": "ORIENTE", "ZAMORA CHINCHIPE": "ORIENTE",
    "GALAPAGOS": "INSULAR",
}
