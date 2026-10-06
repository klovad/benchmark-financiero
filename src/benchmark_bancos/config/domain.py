"""Catálogos de dominio usados por los parsers: mapeos de vocabulario de las fuentes al
vocabulario canónico del modelo. No dependen del entorno ni del sitio de origen."""

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

# Entidades de segundo piso que la SEPS publica junto a las cooperativas (sql/29).
SEPS_RUC_SEGUNDO_PISO = {
    "1768168480001",  # CONAFIPS
    "1791708040001",  # CAJA CENTRAL FINANCOOP
}
