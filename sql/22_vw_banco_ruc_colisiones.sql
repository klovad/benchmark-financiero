-- Los 7 pares de banco_codigo que comparten ruc en marts.dim_banco (6 pares 2-a-2 más el
-- caso 3-vías AMIBANK/FINCA/BP FINCA) estaban documentados solo como prosa en
-- docs/gobernanza_datos.md ("Huecos de gobernanza conocidos"), con la query de
-- verificación mencionada ahí mismo pero no persistida en ningún lado consultable --
-- cualquiera que hiciera SELECT * FROM marts.dim_banco no tenía forma de descubrir la
-- colisión sin haber leído antes ese documento. Esta vista no cambia la decisión de
-- negocio (no se fusionan: el cambio de tipo_entidad es real -- cooperativa/financiera
-- que se convirtió en banco privado licenciado manteniendo el mismo RUC en BCE -- y
-- fusionar ocultaría esa transición, ver docs/gobernanza_datos.md fila "7 pares de
-- dim_banco.banco_codigo distintos comparten el mismo ruc"), solo resuelve que el hueco
-- sea descubrible desde SQL: cualquier análisis longitudinal por banco_codigo puede
-- hacer NOT EXISTS/LEFT JOIN contra esta vista para saber si el banco de interés
-- participa en una colisión antes de agrupar.
--
-- Verificado contra Postgres vivo (2026-08-22): devuelve exactamente los 7 rucs ya
-- documentados en docs/gobernanza_datos.md, 15 filas totales (6 pares x 2 + 1 trío x 3).

CREATE VIEW marts.vw_banco_ruc_colisiones AS
SELECT
    b.ruc,
    b.banco_id,
    b.banco_codigo,
    b.banco,
    b.tipo_entidad
FROM marts.dim_banco b
WHERE b.ruc IN (
    SELECT ruc
    FROM marts.dim_banco
    WHERE ruc IS NOT NULL
    GROUP BY ruc
    HAVING count(*) > 1
)
ORDER BY b.ruc, b.banco_codigo;
