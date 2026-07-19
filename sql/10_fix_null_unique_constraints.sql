-- Bug: UNIQUE (dias_desde, dias_hasta) en dim_plazo y UNIQUE (fecha_id, banco_id,
-- canton_id, categoria_deposito_id, plazo_id) en fact_depositos no detectan conflicto
-- cuando la columna nullable (dias_hasta / plazo_id) es NULL, porque en SQL NULL <> NULL
-- también bajo UNIQUE/ON CONFLICT. Cada corrida de refresh_marts() volvía a insertar una
-- fila "nueva" para el bucket sin tope superior ("DE MÁS DE 361 DÍAS", dias_hasta NULL),
-- y el LEFT JOIN de fact_depositos contra dim_plazo duplicado producía fan-out.
-- Fix: reemplazar ambos UNIQUE por índices únicos sobre COALESCE(col, sentinela), que sí
-- tratan los NULLs como iguales entre sí. Verificado que ON CONFLICT (a, COALESCE(b, -1))
-- apunta correctamente a un índice de expresión de esa forma.

-- 0) Se suelta el constraint viejo ANTES de remapear datos: mientras existan las 2 filas
--    fan-out (plazo_id 5 y 10) para la misma fila real, reapuntar una de ellas al
--    plazo_id canónico produce temporalmente una llave duplicada bajo el constraint
--    original (que sigue activo hasta que se reemplaza más abajo).
ALTER TABLE marts.fact_depositos DROP CONSTRAINT IF EXISTS fact_depositos_unique;

-- 1) Dedupe dim_plazo: consolidar duplicados de (dias_desde, dias_hasta) en el plazo_id
--    más antiguo, y reapuntar cualquier fact_depositos.plazo_id que use el descartado.
WITH duplicados AS (
    SELECT
        plazo_id,
        MIN(plazo_id) OVER (PARTITION BY dias_desde, COALESCE(dias_hasta, -1)) AS plazo_id_canonico
    FROM marts.dim_plazo
),
mapeo AS (
    SELECT plazo_id, plazo_id_canonico FROM duplicados WHERE plazo_id <> plazo_id_canonico
)
UPDATE marts.fact_depositos f
SET plazo_id = m.plazo_id_canonico
FROM mapeo m
WHERE f.plazo_id = m.plazo_id;

WITH duplicados AS (
    SELECT
        plazo_id,
        MIN(plazo_id) OVER (PARTITION BY dias_desde, COALESCE(dias_hasta, -1)) AS plazo_id_canonico
    FROM marts.dim_plazo
)
DELETE FROM marts.dim_plazo
WHERE plazo_id IN (SELECT plazo_id FROM duplicados WHERE plazo_id <> plazo_id_canonico);

-- 2) dim_plazo: constraint NULL-safe
ALTER TABLE marts.dim_plazo DROP CONSTRAINT IF EXISTS dim_plazo_dias_desde_dias_hasta_key;
CREATE UNIQUE INDEX IF NOT EXISTS dim_plazo_rango_unique
    ON marts.dim_plazo (dias_desde, COALESCE(dias_hasta, -1));

-- 3) fact_depositos: mismo problema con plazo_id nullable (toda categoría distinta de
--    "DEPÓSITOS A PLAZO" tiene plazo_id NULL) -- dedupe primero, luego constraint NULL-safe.
WITH duplicados AS (
    SELECT
        fact_depositos_id,
        ROW_NUMBER() OVER (
            PARTITION BY fecha_id, banco_id, canton_id, categoria_deposito_id, COALESCE(plazo_id, -1)
            ORDER BY fact_depositos_id
        ) AS rn
    FROM marts.fact_depositos
)
DELETE FROM marts.fact_depositos
WHERE fact_depositos_id IN (SELECT fact_depositos_id FROM duplicados WHERE rn > 1);

CREATE UNIQUE INDEX IF NOT EXISTS fact_depositos_rango_unique
    ON marts.fact_depositos (fecha_id, banco_id, canton_id, categoria_deposito_id, COALESCE(plazo_id, -1));
