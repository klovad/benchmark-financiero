-- SEPS (cooperativas S1-S3 + mutualistas): única pieza de esquema que la fuente necesita.
-- Ver docs/fuentes_datos.md sección 4.0.
--
-- Todo lo demás conforma contra tablas existentes, sin DDL nuevo:
--   captaciones  -> staging.depositos      -> marts.fact_saldo_depositos
--   colocaciones -> staging.cartera        -> marts.fact_saldo_cartera (son saldos)
--   EEFF         -> staging.boletin_balance/pyg -> marts.fact_balance/fact_pyg
--   raw          -> raw.depositos/raw.cartera/raw.boletin_* (mismo JSONB append-only);
--                   raw.source_files registra con prefijo 'seps/{año}/' y report_type
--                   'depositos'/'cartera'/'boletin_balance' (ya permitidos, sql/13).
--   tipo_entidad -> 'COOPERATIVA'/'MUTUALISTA' ya existían; 'ENTIDAD DE SEGUNDO PISO'
--                   en sql/29.
--
-- 'DEPÓSITOS A LA VISTA': taxonomía de la SEPS (vista/plazo/garantía/restringidos). No
-- se asimila a DEPÓSITOS DE AHORRO ni a MONETARIOS: el sector cooperativo no distingue
-- esos productos en este reporte y fusionarlo por similitud de nombre inventaría una
-- equivalencia que la fuente no afirma. Mismo patrón que sql/12 (DEPÓSITOS MONETARIOS).

INSERT INTO marts.dim_categoria_deposito (categoria) VALUES ('DEPÓSITOS A LA VISTA')
ON CONFLICT (categoria) DO NOTHING;
