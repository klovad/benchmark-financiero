-- BCE tsp/tsa: cambio de grano de provincia a cantón en fact_captaciones_depositos /
-- fact_colocaciones_cartera, unificando la geografía de BCE con el patrón ya usado por
-- CAPCOL (fact_saldo_cartera/fact_saldo_depositos: dim_canton como FK directa,
-- dim_provincia como outrigger vía dim_canton.provincia_id -- ver sql/20_dim_provincia.sql
-- y "Kimball outrigger over forced grain" en CLAUDE.md). Antes:
-- src/benchmark_bancos/transform/parse_bce_tasas.py::_weighted_agg() colapsaba cantón dentro de provincia
-- ANTES de staging (comentario original en sql/11_schema_bce.sql líneas 6-9) -- el
-- archivo fuente SÍ trae cantón, solo se perdía en el parser.
--
-- Investigación verificada contra raw.bce_tasas_pasivas/activas completos (2026-09-01,
-- Postgres nativo, pg_postmaster_start_time() confirma instancia de producción, no un
-- contenedor docker-compose vacío): 219 nombres de cantón distintos, 226 pares
-- (canton, provincia) distintos excluyendo el placeholder 'NACIONAL'. marts.dim_canton
-- tenía 132 filas (sembradas desde CAPCOL) -- comparando insensible a tildes,
-- 95 pares (canton, provincia) son net-new (cooperativas/mutualistas pequeñas con
-- presencia donde CAPCOL no opera, ej. '24 DE MAYO', 'ARCHIDONA', 'SÍGSIG' -- este
-- último SÍ coincidía ya, no todos los ejemplos de la investigación preliminar
-- resultaron netos-nuevos tras la comparación final).
--
-- 5 pares NO se tratan como cantón nuevo -- son el MISMO cantón físico que BCE escribe
-- con una forma de texto distinta a la ya sembrada desde CAPCOL (detectado con
-- difflib + verificación manual contra la división político-administrativa real del
-- Ecuador antes de aceptar cualquier match, para no fusionar cantones que en realidad
-- son distintos -- ver 'PUERTO QUITO', cantón real y separado de 'QUITO', que SÍ quedó
-- como net-new):
--   DISTRITO METROPOLITANO DE QUITO (Pichincha) = QUITO
--   EL EMPALME (Guayas)                          = EMPALME
--   GENERAL ANTONIO ELIZALDE (Guayas)             = GENERAL ANTONIO ELIZALDE (BUCAY)
--   PUEBLOVIEJO (Los Ríos)                        = PUEBLO VIEJO
--   SAN FRANCISCO DE ORELLANA (Orellana)          = ORELLANA
-- Estos 5 alias viven en src/benchmark_bancos/transform/canton_matching.py::_ALIASES_BCE, resueltos en
-- Python antes de staging (principio de diseño #2) -- NO se agregan como filas nuevas acá.
--
-- 4+ pares son cantones reales con el MISMO nombre en DOS provincias distintas por
-- reclasificación administrativa histórica de Ecuador (no error de dato): LA CONCORDIA
-- (Esmeraldas / Santo Domingo de los Tsáchilas, YA existía así en dim_canton antes de
-- esta migración), SANTO DOMINGO (Pichincha / Santo Domingo de los Tsáchilas), BOLÍVAR
-- (Carchi / Manabí), LORETO y AGUARICO (Napo / Orellana, previos a la creación de la
-- provincia de Orellana en 1998) -- la UNIQUE (canton, provincia_id) de dim_canton ya
-- soporta esto sin rediseño, solo hacía falta poblarla con el par completo de cada fila
-- fuente en vez de asumir un solo provincia_id por nombre de cantón.
--
-- Placeholder de "sin cantón desagregado": provincia='S/N' <=> canton='NACIONAL' es una
-- relación 1:1 perfecta en las 3.077.976 filas de raw.bce_tasas_pasivas (cero
-- excepciones) -- estructural para varios instrumentos (depósitos de ahorro, monetarios,
-- fondos de tarjetahabientes, reportos: 100% NACIONAL siempre) y para todo el histórico
-- 2008-~2015 (ningún instrumento traía cantón todavía). Se agrega como fila normal de
-- dim_canton (canton='NACIONAL', provincia_id de la fila 'S/N' ya sembrada en
-- sql/20_dim_provincia.sql), mismo patrón que 'ZONA NO DELIMITADA'/'LAS GOLONDRINAS' de
-- CAPCOL. IMPORTANTE para consumidores: monto_total/numero_operaciones de las filas
-- 'NACIONAL' NUNCA se solapan con las de cantón real para la misma combinación
-- (fecha, banco, instrumento, plazo) -- sumar TODO (incluido 'NACIONAL') da el total
-- correcto; un reporte que filtre solo cantones con geografía conocida SUBCONTARÁ, para
-- varios instrumentos perdería el 100% del volumen. Ver docs/gobernanza_datos.md.
--
-- ================================================================================
-- 1. marts.dim_canton: estado_validacion (two-tier, mismo patrón que dim_plazo/sql/27)
-- ================================================================================
-- dim_canton es un catálogo geográfico real y finito (INEC), no una enumeración cerrada
-- por definición normativa/regulatoria (a diferencia de dim_segmento_credito/
-- dim_subsegmento_credito/dim_categoria_deposito/dim_segmento_entidad, que se quedan con
-- fail-fast absoluto) -- un cantón nuevo en el dato es autoexplicativo una vez que la
-- provincia ya es conocida, igual que un rango de días nuevo lo es para dim_plazo. Se
-- extiende el mismo tratamiento two-tier a este 6to catálogo: shape sano (provincia
-- resuelve) pero par fuera del universo curado -> AUTO_INGRESADO, no aborta la carga.
-- Ver src/benchmark_bancos/transform/canton_matching.py::resolver_canton_bce() para el mecanismo Python
-- correspondiente.
ALTER TABLE marts.dim_canton
    ADD COLUMN estado_validacion TEXT NOT NULL DEFAULT 'AUTO_INGRESADO'
    CHECK (estado_validacion IN ('CONFIRMADO', 'AUTO_INGRESADO', 'RECHAZADO'));

-- Backfill explícito de las 132 filas preexistentes (CAPCOL, ya en producción) -- curadas
-- de facto por haber sobrevivido múltiples cargas sin incidentes, mismo criterio que
-- dim_cuenta_contable (sql/25) y dim_plazo (sql/27).
UPDATE marts.dim_canton SET estado_validacion = 'CONFIRMADO';

-- 96 filas nuevas (95 pares net-new de BCE + el placeholder NACIONAL/S-N), todas
-- CONFIRMADO -- son el resultado de una investigación deliberada contra raw.* completo,
-- no un descubrimiento incidental de refresh_marts(). Universo idéntico al sembrado en
-- src/benchmark_bancos/seeds/canton_provincia.csv (228 pares = 132 preexistentes + estas 96), consultado
-- por src/benchmark_bancos/transform/canton_matching.py::resolver_canton_bce() para decidir cuándo NO
-- lanzar (nivel 2 del two-tier).
INSERT INTO marts.dim_canton (canton, provincia_id, estado_validacion) VALUES
    ('24 DE MAYO', (SELECT provincia_id FROM marts.dim_provincia WHERE provincia = 'MANABI'), 'CONFIRMADO'),
    ('AGUARICO', (SELECT provincia_id FROM marts.dim_provincia WHERE provincia = 'NAPO'), 'CONFIRMADO'),
    ('AGUARICO', (SELECT provincia_id FROM marts.dim_provincia WHERE provincia = 'ORELLANA'), 'CONFIRMADO'),
    ('ALFREDO BAQUERIZO MORENO (JUJAN)', (SELECT provincia_id FROM marts.dim_provincia WHERE provincia = 'GUAYAS'), 'CONFIRMADO'),
    ('ARAJUNO', (SELECT provincia_id FROM marts.dim_provincia WHERE provincia = 'PASTAZA'), 'CONFIRMADO'),
    ('ARCHIDONA', (SELECT provincia_id FROM marts.dim_provincia WHERE provincia = 'NAPO'), 'CONFIRMADO'),
    ('BALAO', (SELECT provincia_id FROM marts.dim_provincia WHERE provincia = 'GUAYAS'), 'CONFIRMADO'),
    ('BOLIVAR', (SELECT provincia_id FROM marts.dim_provincia WHERE provincia = 'CARCHI'), 'CONFIRMADO'),
    ('CARLOS JULIO AROSEMENA TOLA', (SELECT provincia_id FROM marts.dim_provincia WHERE provincia = 'NAPO'), 'CONFIRMADO'),
    ('CASCALES', (SELECT provincia_id FROM marts.dim_provincia WHERE provincia = 'SUCUMBIOS'), 'CONFIRMADO'),
    ('CELICA', (SELECT provincia_id FROM marts.dim_provincia WHERE provincia = 'LOJA'), 'CONFIRMADO'),
    ('CENTINELA DEL CONDOR', (SELECT provincia_id FROM marts.dim_provincia WHERE provincia = 'ZAMORA CHINCHIPE'), 'CONFIRMADO'),
    ('CEVALLOS', (SELECT provincia_id FROM marts.dim_provincia WHERE provincia = 'TUNGURAHUA'), 'CONFIRMADO'),
    ('CHAGUARPAMBA', (SELECT provincia_id FROM marts.dim_provincia WHERE provincia = 'LOJA'), 'CONFIRMADO'),
    ('CHAMBO', (SELECT provincia_id FROM marts.dim_provincia WHERE provincia = 'CHIMBORAZO'), 'CONFIRMADO'),
    ('CHILLA', (SELECT provincia_id FROM marts.dim_provincia WHERE provincia = 'EL ORO'), 'CONFIRMADO'),
    ('CHIMBO', (SELECT provincia_id FROM marts.dim_provincia WHERE provincia = 'BOLIVAR'), 'CONFIRMADO'),
    ('CHINCHIPE', (SELECT provincia_id FROM marts.dim_provincia WHERE provincia = 'ZAMORA CHINCHIPE'), 'CONFIRMADO'),
    ('CHORDELEG', (SELECT provincia_id FROM marts.dim_provincia WHERE provincia = 'AZUAY'), 'CONFIRMADO'),
    ('COLIMES', (SELECT provincia_id FROM marts.dim_provincia WHERE provincia = 'GUAYAS'), 'CONFIRMADO'),
    ('COLTA', (SELECT provincia_id FROM marts.dim_provincia WHERE provincia = 'CHIMBORAZO'), 'CONFIRMADO'),
    ('CUMANDA', (SELECT provincia_id FROM marts.dim_provincia WHERE provincia = 'CHIMBORAZO'), 'CONFIRMADO'),
    ('CUYABENO', (SELECT provincia_id FROM marts.dim_provincia WHERE provincia = 'SUCUMBIOS'), 'CONFIRMADO'),
    ('ECHEANDIA', (SELECT provincia_id FROM marts.dim_provincia WHERE provincia = 'BOLIVAR'), 'CONFIRMADO'),
    ('EL PAN', (SELECT provincia_id FROM marts.dim_provincia WHERE provincia = 'AZUAY'), 'CONFIRMADO'),
    ('ELOY ALFARO', (SELECT provincia_id FROM marts.dim_provincia WHERE provincia = 'ESMERALDAS'), 'CONFIRMADO'),
    ('ESPINDOLA', (SELECT provincia_id FROM marts.dim_provincia WHERE provincia = 'LOJA'), 'CONFIRMADO'),
    ('FLAVIO ALFARO', (SELECT provincia_id FROM marts.dim_provincia WHERE provincia = 'MANABI'), 'CONFIRMADO'),
    ('GONZALO PIZARRO', (SELECT provincia_id FROM marts.dim_provincia WHERE provincia = 'SUCUMBIOS'), 'CONFIRMADO'),
    ('GONZANAMA', (SELECT provincia_id FROM marts.dim_provincia WHERE provincia = 'LOJA'), 'CONFIRMADO'),
    ('GUACHAPALA', (SELECT provincia_id FROM marts.dim_provincia WHERE provincia = 'AZUAY'), 'CONFIRMADO'),
    ('HUAMBOYA', (SELECT provincia_id FROM marts.dim_provincia WHERE provincia = 'MORONA SANTIAGO'), 'CONFIRMADO'),
    ('ISABELA', (SELECT provincia_id FROM marts.dim_provincia WHERE provincia = 'GALAPAGOS'), 'CONFIRMADO'),
    ('ISIDRO AYORA', (SELECT provincia_id FROM marts.dim_provincia WHERE provincia = 'GUAYAS'), 'CONFIRMADO'),
    ('JAMA', (SELECT provincia_id FROM marts.dim_provincia WHERE provincia = 'MANABI'), 'CONFIRMADO'),
    ('JARAMIJO', (SELECT provincia_id FROM marts.dim_provincia WHERE provincia = 'MANABI'), 'CONFIRMADO'),
    ('JUNIN', (SELECT provincia_id FROM marts.dim_provincia WHERE provincia = 'MANABI'), 'CONFIRMADO'),
    ('LA JOYA DE LOS SACHAS', (SELECT provincia_id FROM marts.dim_provincia WHERE provincia = 'NAPO'), 'CONFIRMADO'),
    ('LAS LAJAS', (SELECT provincia_id FROM marts.dim_provincia WHERE provincia = 'EL ORO'), 'CONFIRMADO'),
    ('LAS NAVES', (SELECT provincia_id FROM marts.dim_provincia WHERE provincia = 'BOLIVAR'), 'CONFIRMADO'),
    ('LIMON INDANZA', (SELECT provincia_id FROM marts.dim_provincia WHERE provincia = 'MORONA SANTIAGO'), 'CONFIRMADO'),
    ('LOGROÑO', (SELECT provincia_id FROM marts.dim_provincia WHERE provincia = 'MORONA SANTIAGO'), 'CONFIRMADO'),
    ('LOMAS DE SARGENTILLO', (SELECT provincia_id FROM marts.dim_provincia WHERE provincia = 'GUAYAS'), 'CONFIRMADO'),
    ('LORETO', (SELECT provincia_id FROM marts.dim_provincia WHERE provincia = 'NAPO'), 'CONFIRMADO'),
    ('LORETO', (SELECT provincia_id FROM marts.dim_provincia WHERE provincia = 'ORELLANA'), 'CONFIRMADO'),
    ('MARCABELI', (SELECT provincia_id FROM marts.dim_provincia WHERE provincia = 'EL ORO'), 'CONFIRMADO'),
    ('MERA', (SELECT provincia_id FROM marts.dim_provincia WHERE provincia = 'PASTAZA'), 'CONFIRMADO'),
    ('MIRA', (SELECT provincia_id FROM marts.dim_provincia WHERE provincia = 'CARCHI'), 'CONFIRMADO'),
    ('MOCHA', (SELECT provincia_id FROM marts.dim_provincia WHERE provincia = 'TUNGURAHUA'), 'CONFIRMADO'),
    ('MONTECRISTI', (SELECT provincia_id FROM marts.dim_provincia WHERE provincia = 'MANABI'), 'CONFIRMADO'),
    ('MUISNE', (SELECT provincia_id FROM marts.dim_provincia WHERE provincia = 'ESMERALDAS'), 'CONFIRMADO'),
    ('NABON', (SELECT provincia_id FROM marts.dim_provincia WHERE provincia = 'AZUAY'), 'CONFIRMADO'),
    ('NACIONAL', (SELECT provincia_id FROM marts.dim_provincia WHERE provincia = 'S/N'), 'CONFIRMADO'),
    ('NANGARITZA', (SELECT provincia_id FROM marts.dim_provincia WHERE provincia = 'ZAMORA CHINCHIPE'), 'CONFIRMADO'),
    ('NOBOL', (SELECT provincia_id FROM marts.dim_provincia WHERE provincia = 'GUAYAS'), 'CONFIRMADO'),
    ('OLMEDO', (SELECT provincia_id FROM marts.dim_provincia WHERE provincia = 'LOJA'), 'CONFIRMADO'),
    ('OLMEDO', (SELECT provincia_id FROM marts.dim_provincia WHERE provincia = 'MANABI'), 'CONFIRMADO'),
    ('OÑA', (SELECT provincia_id FROM marts.dim_provincia WHERE provincia = 'AZUAY'), 'CONFIRMADO'),
    ('PABLO SEXTO', (SELECT provincia_id FROM marts.dim_provincia WHERE provincia = 'MORONA SANTIAGO'), 'CONFIRMADO'),
    ('PALANDA', (SELECT provincia_id FROM marts.dim_provincia WHERE provincia = 'ZAMORA CHINCHIPE'), 'CONFIRMADO'),
    ('PALENQUE', (SELECT provincia_id FROM marts.dim_provincia WHERE provincia = 'LOS RIOS'), 'CONFIRMADO'),
    ('PALESTINA', (SELECT provincia_id FROM marts.dim_provincia WHERE provincia = 'GUAYAS'), 'CONFIRMADO'),
    ('PALLATANGA', (SELECT provincia_id FROM marts.dim_provincia WHERE provincia = 'CHIMBORAZO'), 'CONFIRMADO'),
    ('PALORA', (SELECT provincia_id FROM marts.dim_provincia WHERE provincia = 'MORONA SANTIAGO'), 'CONFIRMADO'),
    ('PAQUISHA', (SELECT provincia_id FROM marts.dim_provincia WHERE provincia = 'ZAMORA CHINCHIPE'), 'CONFIRMADO'),
    ('PENIPE', (SELECT provincia_id FROM marts.dim_provincia WHERE provincia = 'CHIMBORAZO'), 'CONFIRMADO'),
    ('PUCARA', (SELECT provincia_id FROM marts.dim_provincia WHERE provincia = 'AZUAY'), 'CONFIRMADO'),
    ('PUERTO QUITO', (SELECT provincia_id FROM marts.dim_provincia WHERE provincia = 'PICHINCHA'), 'CONFIRMADO'),
    ('PUTUMAYO', (SELECT provincia_id FROM marts.dim_provincia WHERE provincia = 'SUCUMBIOS'), 'CONFIRMADO'),
    ('QUERO', (SELECT provincia_id FROM marts.dim_provincia WHERE provincia = 'TUNGURAHUA'), 'CONFIRMADO'),
    ('QUIJOS', (SELECT provincia_id FROM marts.dim_provincia WHERE provincia = 'NAPO'), 'CONFIRMADO'),
    ('QUILANGA', (SELECT provincia_id FROM marts.dim_provincia WHERE provincia = 'LOJA'), 'CONFIRMADO'),
    ('RIOVERDE', (SELECT provincia_id FROM marts.dim_provincia WHERE provincia = 'ESMERALDAS'), 'CONFIRMADO'),
    ('ROCAFUERTE', (SELECT provincia_id FROM marts.dim_provincia WHERE provincia = 'MANABI'), 'CONFIRMADO'),
    ('SALITRE', (SELECT provincia_id FROM marts.dim_provincia WHERE provincia = 'GUAYAS'), 'CONFIRMADO'),
    ('SAN FERNANDO', (SELECT provincia_id FROM marts.dim_provincia WHERE provincia = 'AZUAY'), 'CONFIRMADO'),
    ('SAN JACINTO DE YAGUACHI', (SELECT provincia_id FROM marts.dim_provincia WHERE provincia = 'GUAYAS'), 'CONFIRMADO'),
    ('SAN MIGUEL DE URCUQUI', (SELECT provincia_id FROM marts.dim_provincia WHERE provincia = 'IMBABURA'), 'CONFIRMADO'),
    ('SAN PEDRO DE HUACA', (SELECT provincia_id FROM marts.dim_provincia WHERE provincia = 'CARCHI'), 'CONFIRMADO'),
    ('SAN VICENTE', (SELECT provincia_id FROM marts.dim_provincia WHERE provincia = 'MANABI'), 'CONFIRMADO'),
    ('SANTA CLARA', (SELECT provincia_id FROM marts.dim_provincia WHERE provincia = 'PASTAZA'), 'CONFIRMADO'),
    ('SANTA LUCIA', (SELECT provincia_id FROM marts.dim_provincia WHERE provincia = 'GUAYAS'), 'CONFIRMADO'),
    ('SANTIAGO', (SELECT provincia_id FROM marts.dim_provincia WHERE provincia = 'MORONA SANTIAGO'), 'CONFIRMADO'),
    ('SANTO DOMINGO', (SELECT provincia_id FROM marts.dim_provincia WHERE provincia = 'PICHINCHA'), 'CONFIRMADO'),
    ('SAQUISILI', (SELECT provincia_id FROM marts.dim_provincia WHERE provincia = 'COTOPAXI'), 'CONFIRMADO'),
    ('SARAGURO', (SELECT provincia_id FROM marts.dim_provincia WHERE provincia = 'LOJA'), 'CONFIRMADO'),
    ('SEVILLA DE ORO', (SELECT provincia_id FROM marts.dim_provincia WHERE provincia = 'AZUAY'), 'CONFIRMADO'),
    ('SIGCHOS', (SELECT provincia_id FROM marts.dim_provincia WHERE provincia = 'COTOPAXI'), 'CONFIRMADO'),
    ('SIMON BOLIVAR', (SELECT provincia_id FROM marts.dim_provincia WHERE provincia = 'GUAYAS'), 'CONFIRMADO'),
    ('SOZORANGA', (SELECT provincia_id FROM marts.dim_provincia WHERE provincia = 'LOJA'), 'CONFIRMADO'),
    ('SUCUMBIOS', (SELECT provincia_id FROM marts.dim_provincia WHERE provincia = 'SUCUMBIOS'), 'CONFIRMADO'),
    ('TAISHA', (SELECT provincia_id FROM marts.dim_provincia WHERE provincia = 'MORONA SANTIAGO'), 'CONFIRMADO'),
    ('TISALEO', (SELECT provincia_id FROM marts.dim_provincia WHERE provincia = 'TUNGURAHUA'), 'CONFIRMADO'),
    ('TIWINTZA', (SELECT provincia_id FROM marts.dim_provincia WHERE provincia = 'MORONA SANTIAGO'), 'CONFIRMADO'),
    ('YACUAMBI', (SELECT provincia_id FROM marts.dim_provincia WHERE provincia = 'ZAMORA CHINCHIPE'), 'CONFIRMADO'),
    ('ZAPOTILLO', (SELECT provincia_id FROM marts.dim_provincia WHERE provincia = 'LOJA'), 'CONFIRMADO')
ON CONFLICT (canton, provincia_id) DO NOTHING;

-- ================================================================================
-- 2. marts.vw_dim_canton_geografia: ergonomía de "¿tengo geografía conocida?" SIN
--    reintroducir redundancia de `region`
-- ================================================================================
-- Se evaluó agregar una columna GENERATED ALWAYS AS (...) STORED a dim_canton para esto
-- (idea original de la investigación previa), pero Postgres NO permite que una columna
-- GENERATED referencie otra tabla -- region vive únicamente en dim_provincia
-- (sql/20_dim_provincia.sql la hizo la ÚNICA fuente de verdad ahí, deliberadamente,
-- después de un bug real de 2 regiones distintas para la misma provincia). Duplicar la
-- nulidad de region como columna propia de dim_canton reabriría exactamente esa clase de
-- redundancia. Una vista sin almacenamiento propio logra la misma ergonomía (no hace falta
-- recordar el valor mágico 'NACIONAL'/'S/N' ni escribir el JOIN a mano) sin duplicar
-- ningún dato.
CREATE VIEW marts.vw_dim_canton_geografia AS
SELECT
    c.canton_id,
    c.canton,
    c.provincia_id,
    p.provincia,
    p.region,
    c.estado_validacion,
    (p.region IS NOT NULL) AS es_geografia_conocida
FROM marts.dim_canton c
JOIN marts.dim_provincia p ON p.provincia_id = c.provincia_id;

-- ================================================================================
-- 3. staging.bce_tasas_pasivas / staging.bce_tasas_activas: columna `canton`
-- ================================================================================
-- Nullable a propósito: las filas YA cargadas (grano provincia, colapsado por
-- _weighted_agg()) no tienen de dónde derivar el cantón real sin volver a parsear el
-- archivo fuente -- ese reproceso es responsabilidad de data-engineer (parser +
-- backfill), fuera del alcance de esta migración de esquema. Una vez reprocesado,
-- `canton` nunca debería quedar NULL en una fila nueva (raw.* trae `canton` poblado en
-- el 100% de las filas, incluido el placeholder 'NACIONAL' -- ver nota arriba), pero no
-- se fuerza NOT NULL acá para no romper el ALTER TABLE sobre las filas históricas
-- existentes.
ALTER TABLE staging.bce_tasas_pasivas ADD COLUMN IF NOT EXISTS canton TEXT;
ALTER TABLE staging.bce_tasas_activas ADD COLUMN IF NOT EXISTS canton TEXT;

-- Llave natural NULL-safe: se agrega canton a la llave existente (mismo criterio
-- COALESCE(col, sentinela) de sql/10_fix_null_unique_constraints.sql). Para las filas
-- históricas (canton siempre NULL hoy) esto es un componente constante ('') en la
-- expresión -- no reduce el poder distintivo de la llave para esas filas, así que este
-- ALTER no requiere backfill/dedupe previo, a diferencia de los fact_* de la sección 4
-- (donde SÍ hace falta, porque ahí se elimina provincia_id en vez de agregar una columna
-- nueva al final de la llave).
DROP INDEX IF EXISTS staging.staging_bce_tasas_pasivas_unique;
CREATE UNIQUE INDEX staging_bce_tasas_pasivas_unique
    ON staging.bce_tasas_pasivas (fecha, banco_codigo, categoria_deposito, plazo_dias_desde,
                                   COALESCE(plazo_dias_hasta, -1), COALESCE(provincia, ''),
                                   COALESCE(canton, ''));

DROP INDEX IF EXISTS staging.staging_bce_tasas_activas_unique;
CREATE UNIQUE INDEX staging_bce_tasas_activas_unique
    ON staging.bce_tasas_activas (fecha, banco_codigo, segmento_credito, plazo_dias_desde,
                                   COALESCE(plazo_dias_hasta, -1), COALESCE(provincia, ''),
                                   COALESCE(canton, ''));

-- row_hash de staging.bce_tasas_pasivas/activas NO cambia: canton (como provincia) es
-- parte de la LLAVE NATURAL, no una columna de valor que el ON CONFLICT DO UPDATE
-- reafirme -- mismo criterio ya aplicado a provincia_id en fact_captaciones_depositos/
-- fact_colocaciones_cartera (sql/20), que tampoco entra al row_hash de esas tablas.

-- ================================================================================
-- 4. marts.fact_captaciones_depositos / fact_colocaciones_cartera: provincia_id -> canton_id
-- ================================================================================
-- provincia_id se ELIMINA (no se deja en paralelo a canton_id): provincia ya es
-- derivable de canton_id vía dim_canton.provincia_id -> dim_provincia, y el proyecto ya
-- estableció "una sola fuente de verdad por atributo" para este exacto caso
-- (sql/20_dim_provincia.sql eliminó las columnas provincia/region propias de dim_canton
-- por la misma razón). Mantener provincia_id acá reabriría el mismo antipatrón un nivel
-- más arriba.
--
-- TRUNCATE requerido (mismo patrón que sql/20 usó para estas 2 tablas exactas al
-- introducir provincia_id): a diferencia de esa migración -- donde staging.bce_tasas_*
-- YA tenía el histórico completo con provincia ya homologada, listo para reconstruir sin
-- reproceso de archivo -- acá NINGUNA fila de staging tiene todavía `canton` poblado (se
-- acaba de agregar la columna en la sección 3, nullable, sin backfill posible sin volver
-- a parsear el archivo fuente). Eliminar provincia_id de columnas SIN reemplazo
-- resolvible haría que decenas de filas antes distintas por provincia colapsaran en la
-- misma llave (fecha, banco, categoría/subsegmento, plazo, canton_id=NULL) -- violaría
-- el UNIQUE nuevo. Se trunca y se deja lista para el reproceso completo (parser +
-- refresh_marts()) que sigue a esta migración -- carril de data-engineer, no de esta
-- migración. No se pierde nada: staging.bce_tasas_pasivas/activas conserva el histórico
-- completo con `provincia` (y, tras el reproceso, `canton`) -- fact_captaciones_depositos/
-- fact_colocaciones_cartera son 100% derivables de ahí.
TRUNCATE marts.fact_captaciones_depositos;
TRUNCATE marts.fact_colocaciones_cartera;

ALTER TABLE marts.fact_captaciones_depositos DROP COLUMN IF EXISTS provincia_id;
ALTER TABLE marts.fact_captaciones_depositos
    ADD COLUMN canton_id INT REFERENCES marts.dim_canton (canton_id);
DROP INDEX IF EXISTS marts.fact_captaciones_depositos_unique;
CREATE UNIQUE INDEX fact_captaciones_depositos_unique
    ON marts.fact_captaciones_depositos (fecha_id, banco_id, categoria_deposito_id, plazo_id, COALESCE(canton_id, -1));

ALTER TABLE marts.fact_colocaciones_cartera DROP COLUMN IF EXISTS provincia_id;
ALTER TABLE marts.fact_colocaciones_cartera
    ADD COLUMN canton_id INT REFERENCES marts.dim_canton (canton_id);
DROP INDEX IF EXISTS marts.fact_colocaciones_cartera_unique;
CREATE UNIQUE INDEX fact_colocaciones_cartera_unique
    ON marts.fact_colocaciones_cartera (fecha_id, banco_id, subsegmento_id, plazo_id, COALESCE(canton_id, -1));

-- canton_id nullable, igual criterio que dim_canton.canton_id en fact_saldo_cartera/
-- fact_saldo_depositos (CAPCOL, sql/03_schema_marts.sql/sql/21) y que provincia_id lo
-- era antes en estas mismas 2 tablas (sql/20): defensivo ante el borde real de que un
-- futuro par (canton, provincia) no resuelva por algún motivo no previsto hoy (ej. un
-- LEFT JOIN de refresh_marts() que no matchee) -- preferible NULL explícito y detectable
-- (COALESCE(canton_id, -1) en el índice) a una carga que aborte por completo. En la
-- práctica, una vez reprocesado, se espera 0 filas NULL (canton siempre poblado en
-- raw.*, resolver_canton_bce() nunca deja pasar un par con provincia no resuelta) --
-- verificar esto explícitamente después del reproceso, mismo criterio que
-- _log_cantones_no_resueltos() ya aplica para CAPCOL.
--
-- row_hash de fact_captaciones_depositos/fact_colocaciones_cartera NO cambia: canton_id,
-- como antes provincia_id, es parte de la LLAVE NATURAL (columna del UNIQUE INDEX / del
-- ON CONFLICT), no una columna de valor que el ON CONFLICT DO UPDATE reafirme -- ver
-- sql/19_dim_segmento_entidad.sql para el precedente exacto de esta distinción
-- (segmento_entidad_id SÍ entra al row_hash porque SÍ es una columna de valor que cambia
-- de contenido sin cambiar de llave; provincia_id nunca entró).
