-- Códigos oficiales del INEC en la geografía + fusión de provincias anteriores (2026-10-09).
--
-- 1. marts.dim_provincia.codigo_inec (2 dígitos) y marts.dim_canton.codigo_inec (4 dígitos),
--    del Clasificador Geográfico Estadístico del INEC (DPA vigente, censo 2022). Fuente de
--    verdad: src/benchmark_bancos/seeds/canton_provincia.csv y config/domain.py::
--    PROVINCIA_CODIGO_INEC; refresh_marts() vuelve a sincronizar los cantones desde el CSV en
--    cada corrida (load_postgres.py::sincronizar_cantones_seed). Cubre los 221 cantones
--    vigentes; 'LAS GOLONDRINAS' (ZONA NO DELIMITADA) conserva el 9001 de la DPA 2012 y el
--    placeholder 'NACIONAL'/'S/N' del BCE no tiene código.
--
-- 2. Fusión de 5 pares con provincia ANTERIOR, que algunas entidades siguen reportando
--    (2015-2026): AGUARICO, LA JOYA DE LOS SACHAS y LORETO en Napo (Orellana desde 1998),
--    SANTO DOMINGO en Pichincha (Santo Domingo de los Tsáchilas desde 2007) y LA CONCORDIA en
--    Esmeraldas (Santo Domingo de los Tsáchilas desde 2012). Mismo cantón y mismo código INEC
--    que el par vigente, así que se llevan a la provincia vigente (decisión 2026-10-09:
--    geografía actual en toda la serie). La causa se corrige en
--    canton_matching.py::_ALIASES_PROVINCIA_ANTERIOR.
--    - CAPCOL/SEPS (staging.cartera/depositos): se renombra la provincia. Verificado antes que
--      no hay choque de llave natural con filas del par vigente.
--    - BCE (staging.bce_tasas_*): SÍ hay choques (la misma entidad, semana, segmento y plazo
--      reportada en las dos provincias: 453 filas). Combinar tasas ya agregadas no sería exacto,
--      así que se borran las filas del par anterior y se borra el registro de tsp/tsa en
--      meta.source_files: la siguiente `benchmark-bancos bce` reprocesa el archivo con el alias
--      y _weighted_agg suma montos y pondera tasas desde la fuente. HASTA ESA CORRIDA, los
--      hechos del BCE de esos 5 cantones quedan sin la parte que venía con la provincia anterior.
--    - marts: los hechos de saldos se reasignan al canton_id vigente; los del BCE del par
--      anterior se borran (el reproceso los regenera); se borran los 5 dim_canton anteriores.
--
-- Idempotente: en una base nueva (sql/28 siembra los 5 pares anteriores sin hechos) solo
-- borra esas 5 filas de dim_canton y carga los códigos.

BEGIN;

-- 1a. Provincias
ALTER TABLE marts.dim_provincia ADD COLUMN IF NOT EXISTS codigo_inec char(2);
UPDATE marts.dim_provincia d
SET codigo_inec = v.codigo
FROM (VALUES
    ('AZUAY', '01'),
    ('BOLIVAR', '02'),
    ('CAÑAR', '03'),
    ('CARCHI', '04'),
    ('COTOPAXI', '05'),
    ('CHIMBORAZO', '06'),
    ('EL ORO', '07'),
    ('ESMERALDAS', '08'),
    ('GUAYAS', '09'),
    ('IMBABURA', '10'),
    ('LOJA', '11'),
    ('LOS RIOS', '12'),
    ('MANABI', '13'),
    ('MORONA SANTIAGO', '14'),
    ('NAPO', '15'),
    ('PASTAZA', '16'),
    ('PICHINCHA', '17'),
    ('TUNGURAHUA', '18'),
    ('ZAMORA CHINCHIPE', '19'),
    ('GALAPAGOS', '20'),
    ('SUCUMBIOS', '21'),
    ('ORELLANA', '22'),
    ('SANTO DOMINGO DE LOS TSACHILAS', '23'),
    ('SANTA ELENA', '24'),
    ('ZONA NO DELIMITADA', '90')
) AS v(provincia, codigo)
WHERE d.provincia = v.provincia AND d.codigo_inec IS DISTINCT FROM v.codigo;
CREATE UNIQUE INDEX IF NOT EXISTS dim_provincia_codigo_inec_uq
    ON marts.dim_provincia (codigo_inec) WHERE codigo_inec IS NOT NULL;

ALTER TABLE marts.dim_canton ADD COLUMN IF NOT EXISTS codigo_inec char(4);

-- 2. Fusión de provincias anteriores
CREATE TEMP TABLE _provincia_anterior (canton text, anterior text, vigente text) ON COMMIT DROP;
INSERT INTO _provincia_anterior VALUES
    ('AGUARICO',              'NAPO',       'ORELLANA'),
    ('LA JOYA DE LOS SACHAS', 'NAPO',       'ORELLANA'),
    ('LORETO',                'NAPO',       'ORELLANA'),
    ('SANTO DOMINGO',         'PICHINCHA',  'SANTO DOMINGO DE LOS TSACHILAS'),
    ('LA CONCORDIA',          'ESMERALDAS', 'SANTO DOMINGO DE LOS TSACHILAS');

UPDATE staging.cartera s
SET provincia = a.vigente, region = p.region, fecha_actualizacion = now()
FROM _provincia_anterior a JOIN marts.dim_provincia p ON p.provincia = a.vigente
WHERE s.canton = a.canton AND s.provincia = a.anterior;

UPDATE staging.depositos s
SET provincia = a.vigente, region = p.region, fecha_actualizacion = now()
FROM _provincia_anterior a JOIN marts.dim_provincia p ON p.provincia = a.vigente
WHERE s.canton = a.canton AND s.provincia = a.anterior;

DO $$
DECLARE
    n_pas int;
    n_act int;
BEGIN
    DELETE FROM staging.bce_tasas_pasivas s USING _provincia_anterior a
    WHERE s.canton = a.canton AND s.provincia = a.anterior;
    GET DIAGNOSTICS n_pas = ROW_COUNT;
    DELETE FROM staging.bce_tasas_activas s USING _provincia_anterior a
    WHERE s.canton = a.canton AND s.provincia = a.anterior;
    GET DIAGNOSTICS n_act = ROW_COUNT;
    IF n_pas + n_act > 0 THEN
        DELETE FROM meta.source_files
        WHERE report_type IN ('bce_tasas_pasivas', 'bce_tasas_activas');
        RAISE NOTICE 'sql/36: % filas BCE con provincia anterior borradas. Correr `benchmark-bancos bce` para reprocesar tsp/tsa con el alias.', n_pas + n_act;
    END IF;
END $$;

CREATE TEMP TABLE _fusion_provincia ON COMMIT DROP AS
SELECT ant.canton_id AS id_anterior, vig.canton_id AS id_vigente
FROM _provincia_anterior a
JOIN marts.dim_provincia pa ON pa.provincia = a.anterior
JOIN marts.dim_provincia pv ON pv.provincia = a.vigente
JOIN marts.dim_canton ant ON ant.canton = a.canton AND ant.provincia_id = pa.provincia_id
JOIN marts.dim_canton vig ON vig.canton = a.canton AND vig.provincia_id = pv.provincia_id;

UPDATE marts.fact_saldo_cartera f
SET canton_id = m.id_vigente, fecha_actualizacion = now()
FROM _fusion_provincia m WHERE f.canton_id = m.id_anterior;

UPDATE marts.fact_saldo_depositos f
SET canton_id = m.id_vigente, fecha_actualizacion = now()
FROM _fusion_provincia m WHERE f.canton_id = m.id_anterior;

DELETE FROM marts.fact_captaciones_depositos f
USING _fusion_provincia m WHERE f.canton_id = m.id_anterior;

DELETE FROM marts.fact_colocaciones_cartera f
USING _fusion_provincia m WHERE f.canton_id = m.id_anterior;

DELETE FROM marts.dim_canton d
USING _fusion_provincia m WHERE d.canton_id = m.id_anterior;

-- Par anterior SIN par vigente (base nueva: sql/28 siembra SANTO DOMINGO/PICHINCHA y LA
-- JOYA DE LOS SACHAS/NAPO sin su par vigente): se mueve a la provincia vigente, sin fusión.
UPDATE marts.dim_canton d
SET provincia_id = pv.provincia_id
FROM _provincia_anterior a
JOIN marts.dim_provincia pa ON pa.provincia = a.anterior
JOIN marts.dim_provincia pv ON pv.provincia = a.vigente
WHERE d.canton = a.canton AND d.provincia_id = pa.provincia_id;

-- 1b. Cantones (mismo contenido que seeds/canton_provincia.csv)
UPDATE marts.dim_canton d
SET codigo_inec = v.codigo, estado_validacion = 'CONFIRMADO'
FROM (VALUES
    ('24 DE MAYO', 'MANABI', '1316'),
    ('AGUARICO', 'ORELLANA', '2202'),
    ('ALAUSI', 'CHIMBORAZO', '0602'),
    ('ALFREDO BAQUERIZO MORENO (JUJAN)', 'GUAYAS', '0902'),
    ('AMBATO', 'TUNGURAHUA', '1801'),
    ('ANTONIO ANTE', 'IMBABURA', '1002'),
    ('ARAJUNO', 'PASTAZA', '1604'),
    ('ARCHIDONA', 'NAPO', '1503'),
    ('ARENILLAS', 'EL ORO', '0702'),
    ('ATACAMES', 'ESMERALDAS', '0806'),
    ('ATAHUALPA', 'EL ORO', '0703'),
    ('AZOGUES', 'CAÑAR', '0301'),
    ('BABA', 'LOS RIOS', '1202'),
    ('BABAHOYO', 'LOS RIOS', '1201'),
    ('BALAO', 'GUAYAS', '0903'),
    ('BALSAS', 'EL ORO', '0704'),
    ('BALZAR', 'GUAYAS', '0904'),
    ('BAÑOS DE AGUA SANTA', 'TUNGURAHUA', '1802'),
    ('BIBLIAN', 'CAÑAR', '0302'),
    ('BOLIVAR', 'CARCHI', '0402'),
    ('BOLIVAR', 'MANABI', '1302'),
    ('BUENA FE', 'LOS RIOS', '1210'),
    ('CALUMA', 'BOLIVAR', '0206'),
    ('CALVAS', 'LOJA', '1102'),
    ('CAMILO PONCE ENRIQUEZ', 'AZUAY', '0115'),
    ('CARLOS JULIO AROSEMENA TOLA', 'NAPO', '1509'),
    ('CASCALES', 'SUCUMBIOS', '2106'),
    ('CATAMAYO', 'LOJA', '1103'),
    ('CAYAMBE', 'PICHINCHA', '1702'),
    ('CAÑAR', 'CAÑAR', '0303'),
    ('CELICA', 'LOJA', '1104'),
    ('CENTINELA DEL CONDOR', 'ZAMORA CHINCHIPE', '1907'),
    ('CEVALLOS', 'TUNGURAHUA', '1803'),
    ('CHAGUARPAMBA', 'LOJA', '1105'),
    ('CHAMBO', 'CHIMBORAZO', '0604'),
    ('CHILLA', 'EL ORO', '0705'),
    ('CHILLANES', 'BOLIVAR', '0202'),
    ('CHIMBO', 'BOLIVAR', '0203'),
    ('CHINCHIPE', 'ZAMORA CHINCHIPE', '1902'),
    ('CHONE', 'MANABI', '1303'),
    ('CHORDELEG', 'AZUAY', '0111'),
    ('CHUNCHI', 'CHIMBORAZO', '0605'),
    ('COLIMES', 'GUAYAS', '0905'),
    ('COLTA', 'CHIMBORAZO', '0603'),
    ('CORONEL MARCELINO MARIDUEÑA', 'GUAYAS', '0923'),
    ('COTACACHI', 'IMBABURA', '1003'),
    ('CUENCA', 'AZUAY', '0101'),
    ('CUMANDA', 'CHIMBORAZO', '0610'),
    ('CUYABENO', 'SUCUMBIOS', '2107'),
    ('DAULE', 'GUAYAS', '0906'),
    ('DELEG', 'CAÑAR', '0306'),
    ('DURAN', 'GUAYAS', '0907'),
    ('ECHEANDIA', 'BOLIVAR', '0204'),
    ('EL CARMEN', 'MANABI', '1304'),
    ('EL CHACO', 'NAPO', '1504'),
    ('EL GUABO', 'EL ORO', '0706'),
    ('EL PAN', 'AZUAY', '0112'),
    ('EL PANGUI', 'ZAMORA CHINCHIPE', '1906'),
    ('EL TAMBO', 'CAÑAR', '0305'),
    ('EL TRIUNFO', 'GUAYAS', '0909'),
    ('ELOY ALFARO', 'ESMERALDAS', '0802'),
    ('EMPALME', 'GUAYAS', '0908'),
    ('ESMERALDAS', 'ESMERALDAS', '0801'),
    ('ESPEJO', 'CARCHI', '0403'),
    ('ESPINDOLA', 'LOJA', '1106'),
    ('FLAVIO ALFARO', 'MANABI', '1305'),
    ('GENERAL ANTONIO ELIZALDE (BUCAY)', 'GUAYAS', '0927'),
    ('GIRON', 'AZUAY', '0102'),
    ('GONZALO PIZARRO', 'SUCUMBIOS', '2102'),
    ('GONZANAMA', 'LOJA', '1107'),
    ('GUACHAPALA', 'AZUAY', '0114'),
    ('GUALACEO', 'AZUAY', '0103'),
    ('GUALAQUIZA', 'MORONA SANTIAGO', '1402'),
    ('GUAMOTE', 'CHIMBORAZO', '0606'),
    ('GUANO', 'CHIMBORAZO', '0607'),
    ('GUARANDA', 'BOLIVAR', '0201'),
    ('GUAYAQUIL', 'GUAYAS', '0901'),
    ('HUAMBOYA', 'MORONA SANTIAGO', '1407'),
    ('HUAQUILLAS', 'EL ORO', '0707'),
    ('IBARRA', 'IMBABURA', '1001'),
    ('ISABELA', 'GALAPAGOS', '2002'),
    ('ISIDRO AYORA', 'GUAYAS', '0928'),
    ('JAMA', 'MANABI', '1320'),
    ('JARAMIJO', 'MANABI', '1321'),
    ('JIPIJAPA', 'MANABI', '1306'),
    ('JUNIN', 'MANABI', '1307'),
    ('LA CONCORDIA', 'SANTO DOMINGO DE LOS TSACHILAS', '2302'),
    ('LA JOYA DE LOS SACHAS', 'ORELLANA', '2203'),
    ('LA LIBERTAD', 'SANTA ELENA', '2402'),
    ('LA MANA', 'COTOPAXI', '0502'),
    ('LA TRONCAL', 'CAÑAR', '0304'),
    ('LAGO AGRIO', 'SUCUMBIOS', '2101'),
    ('LAS GOLONDRINAS', 'ZONA NO DELIMITADA', '9001'),
    ('LAS LAJAS', 'EL ORO', '0714'),
    ('LAS NAVES', 'BOLIVAR', '0207'),
    ('LATACUNGA', 'COTOPAXI', '0501'),
    ('LIMON INDANZA', 'MORONA SANTIAGO', '1403'),
    ('LOGROÑO', 'MORONA SANTIAGO', '1410'),
    ('LOJA', 'LOJA', '1101'),
    ('LOMAS DE SARGENTILLO', 'GUAYAS', '0924'),
    ('LORETO', 'ORELLANA', '2204'),
    ('MACARA', 'LOJA', '1108'),
    ('MACHALA', 'EL ORO', '0701'),
    ('MANTA', 'MANABI', '1308'),
    ('MARCABELI', 'EL ORO', '0708'),
    ('MEJIA', 'PICHINCHA', '1703'),
    ('MERA', 'PASTAZA', '1602'),
    ('MILAGRO', 'GUAYAS', '0910'),
    ('MIRA', 'CARCHI', '0404'),
    ('MOCACHE', 'LOS RIOS', '1212'),
    ('MOCHA', 'TUNGURAHUA', '1804'),
    ('MONTALVO', 'LOS RIOS', '1203'),
    ('MONTECRISTI', 'MANABI', '1309'),
    ('MONTUFAR', 'CARCHI', '0405'),
    ('MORONA', 'MORONA SANTIAGO', '1401'),
    ('MUISNE', 'ESMERALDAS', '0803'),
    ('NABON', 'AZUAY', '0104'),
    ('NACIONAL', 'S/N', NULL),
    ('NANGARITZA', 'ZAMORA CHINCHIPE', '1903'),
    ('NARANJAL', 'GUAYAS', '0911'),
    ('NARANJITO', 'GUAYAS', '0912'),
    ('NOBOL', 'GUAYAS', '0925'),
    ('OLMEDO', 'LOJA', '1116'),
    ('OLMEDO', 'MANABI', '1318'),
    ('ORELLANA', 'ORELLANA', '2201'),
    ('OTAVALO', 'IMBABURA', '1004'),
    ('OÑA', 'AZUAY', '0110'),
    ('PABLO SEXTO', 'MORONA SANTIAGO', '1411'),
    ('PAJAN', 'MANABI', '1310'),
    ('PALANDA', 'ZAMORA CHINCHIPE', '1908'),
    ('PALENQUE', 'LOS RIOS', '1209'),
    ('PALESTINA', 'GUAYAS', '0913'),
    ('PALLATANGA', 'CHIMBORAZO', '0608'),
    ('PALORA', 'MORONA SANTIAGO', '1404'),
    ('PALTAS', 'LOJA', '1109'),
    ('PANGUA', 'COTOPAXI', '0503'),
    ('PAQUISHA', 'ZAMORA CHINCHIPE', '1909'),
    ('PASAJE', 'EL ORO', '0709'),
    ('PASTAZA', 'PASTAZA', '1601'),
    ('PATATE', 'TUNGURAHUA', '1805'),
    ('PAUTE', 'AZUAY', '0105'),
    ('PEDERNALES', 'MANABI', '1317'),
    ('PEDRO CARBO', 'GUAYAS', '0914'),
    ('PEDRO MONCAYO', 'PICHINCHA', '1704'),
    ('PEDRO VICENTE MALDONADO', 'PICHINCHA', '1708'),
    ('PENIPE', 'CHIMBORAZO', '0609'),
    ('PICHINCHA', 'MANABI', '1311'),
    ('PIMAMPIRO', 'IMBABURA', '1005'),
    ('PINDAL', 'LOJA', '1114'),
    ('PIÑAS', 'EL ORO', '0710'),
    ('PLAYAS', 'GUAYAS', '0921'),
    ('PORTOVELO', 'EL ORO', '0711'),
    ('PORTOVIEJO', 'MANABI', '1301'),
    ('PUCARA', 'AZUAY', '0106'),
    ('PUEBLO VIEJO', 'LOS RIOS', '1204'),
    ('PUERTO LOPEZ', 'MANABI', '1319'),
    ('PUERTO QUITO', 'PICHINCHA', '1709'),
    ('PUJILI', 'COTOPAXI', '0504'),
    ('PUTUMAYO', 'SUCUMBIOS', '2103'),
    ('PUYANGO', 'LOJA', '1110'),
    ('QUERO', 'TUNGURAHUA', '1806'),
    ('QUEVEDO', 'LOS RIOS', '1205'),
    ('QUIJOS', 'NAPO', '1507'),
    ('QUILANGA', 'LOJA', '1115'),
    ('QUININDE', 'ESMERALDAS', '0804'),
    ('QUINSALOMA', 'LOS RIOS', '1213'),
    ('QUITO', 'PICHINCHA', '1701'),
    ('RIOBAMBA', 'CHIMBORAZO', '0601'),
    ('RIOVERDE', 'ESMERALDAS', '0807'),
    ('ROCAFUERTE', 'MANABI', '1312'),
    ('RUMIÑAHUI', 'PICHINCHA', '1705'),
    ('SALCEDO', 'COTOPAXI', '0505'),
    ('SALINAS', 'SANTA ELENA', '2403'),
    ('SALITRE', 'GUAYAS', '0919'),
    ('SAMBORONDON', 'GUAYAS', '0916'),
    ('SAN CRISTOBAL', 'GALAPAGOS', '2001'),
    ('SAN FERNANDO', 'AZUAY', '0107'),
    ('SAN JACINTO DE YAGUACHI', 'GUAYAS', '0920'),
    ('SAN JUAN BOSCO', 'MORONA SANTIAGO', '1408'),
    ('SAN LORENZO', 'ESMERALDAS', '0805'),
    ('SAN MIGUEL', 'BOLIVAR', '0205'),
    ('SAN MIGUEL DE LOS BANCOS', 'PICHINCHA', '1707'),
    ('SAN MIGUEL DE URCUQUI', 'IMBABURA', '1006'),
    ('SAN PEDRO DE HUACA', 'CARCHI', '0406'),
    ('SAN PEDRO DE PELILEO', 'TUNGURAHUA', '1807'),
    ('SAN VICENTE', 'MANABI', '1322'),
    ('SANTA ANA', 'MANABI', '1313'),
    ('SANTA CLARA', 'PASTAZA', '1603'),
    ('SANTA CRUZ', 'GALAPAGOS', '2003'),
    ('SANTA ELENA', 'SANTA ELENA', '2401'),
    ('SANTA ISABEL', 'AZUAY', '0108'),
    ('SANTA LUCIA', 'GUAYAS', '0918'),
    ('SANTA ROSA', 'EL ORO', '0712'),
    ('SANTIAGO', 'MORONA SANTIAGO', '1405'),
    ('SANTIAGO DE PILLARO', 'TUNGURAHUA', '1808'),
    ('SANTO DOMINGO', 'SANTO DOMINGO DE LOS TSACHILAS', '2301'),
    ('SAQUISILI', 'COTOPAXI', '0506'),
    ('SARAGURO', 'LOJA', '1111'),
    ('SEVILLA DE ORO', 'AZUAY', '0113'),
    ('SHUSHUFINDI', 'SUCUMBIOS', '2104'),
    ('SIGCHOS', 'COTOPAXI', '0507'),
    ('SIGSIG', 'AZUAY', '0109'),
    ('SIMON BOLIVAR', 'GUAYAS', '0922'),
    ('SOZORANGA', 'LOJA', '1112'),
    ('SUCRE', 'MANABI', '1314'),
    ('SUCUA', 'MORONA SANTIAGO', '1406'),
    ('SUCUMBIOS', 'SUCUMBIOS', '2105'),
    ('SUSCAL', 'CAÑAR', '0307'),
    ('TAISHA', 'MORONA SANTIAGO', '1409'),
    ('TENA', 'NAPO', '1501'),
    ('TISALEO', 'TUNGURAHUA', '1809'),
    ('TIWINTZA', 'MORONA SANTIAGO', '1412'),
    ('TOSAGUA', 'MANABI', '1315'),
    ('TULCAN', 'CARCHI', '0401'),
    ('URDANETA', 'LOS RIOS', '1206'),
    ('VALENCIA', 'LOS RIOS', '1211'),
    ('VENTANAS', 'LOS RIOS', '1207'),
    ('VINCES', 'LOS RIOS', '1208'),
    ('YACUAMBI', 'ZAMORA CHINCHIPE', '1904'),
    ('YANTZAZA', 'ZAMORA CHINCHIPE', '1905'),
    ('ZAMORA', 'ZAMORA CHINCHIPE', '1901'),
    ('ZAPOTILLO', 'LOJA', '1113'),
    ('ZARUMA', 'EL ORO', '0713')
) AS v(canton, provincia, codigo)
JOIN marts.dim_provincia p ON p.provincia = v.provincia
WHERE d.canton = v.canton AND d.provincia_id = p.provincia_id;

CREATE UNIQUE INDEX IF NOT EXISTS dim_canton_codigo_inec_uq
    ON marts.dim_canton (codigo_inec) WHERE codigo_inec IS NOT NULL;

COMMIT;
