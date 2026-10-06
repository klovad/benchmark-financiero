-- Reemplaza dim_producto_cartera (tipo_credito x estado_cartera) y dim_producto_deposito
-- (tipo_deposito plano, que mezclaba categoría + plazo) por 3 catálogos conformados,
-- reutilizables entre CAPCOL y BCE:
--   - dim_segmento_credito: jerarquía real de 2 niveles (26 sub-segmentos de BCE +
--     rollup a los 6 tipo_credito de CAPCOL). Universo completo, sin filtrar por tipo
--     de entidad, para que el catálogo sirva si el proyecto se extiende a
--     cooperativas/mutualistas/banca pública más adelante.
--   - dim_categoria_deposito: una sola columna, sin duplicar entre CAPCOL/BCE.
--   - dim_plazo: catálogo abierto por rango numérico de días, compartido entre todas
--     las fuentes de plazo (CAPCOL depósitos, BCE tsp/tsa).
-- fact_cartera pasa a guardar tipo_credito/estado_cartera directo (dimensión
-- degenerada, ya que nunca tiene el sub-segmento fino de BCE). fact_depositos pasa a
-- categoria_deposito_id + plazo_id.

CREATE TABLE IF NOT EXISTS marts.dim_segmento_credito (
    segmento_id         SERIAL PRIMARY KEY,
    segmento             TEXT NOT NULL UNIQUE,
    tipo_credito_capcol  TEXT
);

CREATE TABLE IF NOT EXISTS marts.dim_categoria_deposito (
    categoria_deposito_id SERIAL PRIMARY KEY,
    categoria              TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS marts.dim_plazo (
    plazo_id     SERIAL PRIMARY KEY,
    dias_desde   INT NOT NULL,
    dias_hasta   INT,
    plazo_codigo TEXT,
    UNIQUE (dias_desde, dias_hasta)
);

-- Universo completo de segmento_credito de BCE (26, todas las entidades) + rollup a
-- CAPCOL. Ver docs/fuentes_datos.md sección 4 para el detalle de por qué 4 quedan NULL.
INSERT INTO marts.dim_segmento_credito (segmento, tipo_credito_capcol) VALUES
    ('COMERCIAL ORDINARIO', 'comercial'),
    ('COMERCIAL PRIORITARIO CORPORATIVO', 'comercial'),
    ('COMERCIAL PRIORITARIO EMPRESARIAL', 'comercial'),
    ('COMERCIAL PRIORITARIO PYMES', 'comercial'),
    ('CONSUMO', 'consumo'),
    ('CONSUMO MINORISTA', 'consumo'),
    ('CONSUMO ORDINARIO', 'consumo'),
    ('CONSUMO PRIORITARIO', 'consumo'),
    ('EDUCATIVO', 'educativo'),
    ('EDUCATIVO SOCIAL', 'educativo'),
    ('INMOBILIARIO', 'inmobiliario'),
    ('INVERSIÓN PÚBLICA', NULL),
    ('MICROCRÉDITO ACUMULACIÓN AMPLIADA (SE)', NULL),
    ('MICROCRÉDITO ACUMULACIÓN SIMPLE (SE)', NULL),
    ('MICROCRÉDITO AGRÍCOLA Y GANADERO', 'microcredito'),
    ('MICROCRÉDITO DE ACUMULACIÓN AMPLIADA', 'microcredito'),
    ('MICROCRÉDITO DE ACUMULACIÓN SIMPLE', 'microcredito'),
    ('MICROCRÉDITO MINORISTA', 'microcredito'),
    ('MICROCRÉDITO MINORISTA (SE)', NULL),
    ('PRODUCTIVO - CORPORATIVO', 'comercial'),
    ('PRODUCTIVO AGRÍCOLA Y GANADERO', 'comercial'),
    ('PRODUCTIVO EMPRESARIAL', 'comercial'),
    ('PRODUCTIVO PYMES', 'comercial'),
    ('VIVIENDA', 'inmobiliario'),
    ('VIVIENDA DE INTERÉS PÚBLICO', 'vivienda_interes_publico'),
    ('VIVIENDA DE INTERÉS SOCIAL', 'vivienda_interes_publico')
ON CONFLICT (segmento) DO NOTHING;

INSERT INTO marts.dim_categoria_deposito (categoria) VALUES
    ('DEPÓSITOS DE AHORRO'),
    ('DEPÓSITOS DE CUENTA BÁSICA'),
    ('DEPÓSITOS DE GARANTÍA'),
    ('DEPÓSITOS MONETARIOS QUE GENERAN INTERESES'),
    ('DEPÓSITOS MONETARIOS QUE NO GENERAN INTERESES'),
    ('DEPÓSITOS MONETARIOS DE INSTITUCIONES FINANCIERAS'),
    ('DEPÓSITOS POR CONFIRMAR'),
    ('DEPÓSITOS RESTRINGIDOS'),
    ('DEPÓSITOS A PLAZO'),
    ('FONDOS DE TARJETAHABIENTES'),
    ('OPERACIONES DE REPORTO')
ON CONFLICT (categoria) DO NOTHING;

-- staging.depositos gana la categoría/plazo ya separados (src/benchmark_bancos/transform/
-- categoria_deposito_matching.py); tipo_deposito crudo se conserva (sigue siendo la
-- llave natural de staging, no cambia).
ALTER TABLE staging.depositos
    ADD COLUMN IF NOT EXISTS categoria_deposito TEXT,
    ADD COLUMN IF NOT EXISTS plazo_dias_desde INT,
    ADD COLUMN IF NOT EXISTS plazo_dias_hasta INT;
