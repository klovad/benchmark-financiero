-- marts.dim_banco.tipo_entidad: nuevo valor 'ENTIDAD DE SEGUNDO PISO'.
--
-- La SEPS (Estados Financieros y Reportes de captaciones/colocaciones, ver
-- docs/fuentes_datos.md sección 4.0) incluye 2 entidades que no captan ni colocan con el
-- público sino con otras entidades del sector popular y solidario:
--   CORPORACION NACIONAL DE FINANZAS POPULARES Y SOLIDARIAS (CONAFIPS, 1768168480001)
--   CAJA CENTRAL FINANCOOP                                   (1791708040001)
-- Ninguna existe en dim_banco (BCE tsp/tsa no las reporta) y ninguno de los 6 valores del
-- CHECK de sql/07 las describe: no son COOPERATIVA de ahorro y crédito (no tienen socios
-- personas naturales) ni BANCO PUBLICO (CONAFIPS es pública, FINANCOOP no). Se agrega un
-- valor propio en vez de forzarlas en una categoría existente, para que un benchmark de
-- cooperativas no las mezcle con entidades de primer piso.
--
-- Solo marts.dim_banco tiene CHECK sobre tipo_entidad (verificado contra la base viva
-- 2026-09-30); staging.banco_maestro/staging.cartera/staging.depositos son TEXT libre.

ALTER TABLE marts.dim_banco DROP CONSTRAINT IF EXISTS dim_banco_tipo_entidad_check;
ALTER TABLE marts.dim_banco ADD CONSTRAINT dim_banco_tipo_entidad_check CHECK (tipo_entidad IN
    ('BANCO PRIVADO', 'BANCO PUBLICO', 'COOPERATIVA', 'MUTUALISTA',
     'SOCIEDAD FINANCIERA', 'TARJETAS DE CREDITO', 'ENTIDAD DE SEGUNDO PISO'));
