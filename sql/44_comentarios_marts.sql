-- Metadatos en el catálogo de Postgres (COMMENT ON) para todo marts (2026-10-31).
--
-- Hasta ahora las descripciones vivían solo en docs/data_dictionary.md: 0 de 20 tablas,
-- 2 de 18 vistas y 0 de 215 columnas tenían comentario en la base, así que DBeaver,
-- pgAdmin, Power BI o el catálogo del repo de análisis mostraban todo sin explicar.
-- Texto resumido del diccionario de datos; el detalle y la historia siguen allá.
-- Unidades: montos en USD; tasas en porcentaje anual (17.5 = 17,5 %).
--
-- Regla desde esta migración (docs/gobernanza_datos.md, regla 10): toda tabla, vista o
-- columna nueva de marts trae su COMMENT en la misma migración;
-- tests/test_metadatos.py falla si alguna queda sin descripción.

-- ───────────── Dimensiones ─────────────
COMMENT ON TABLE marts.dim_entidad IS 'Entidades del sistema financiero: bancos privados y públicos, cooperativas, mutualistas, sociedades financieras, emisoras de tarjetas y entidades de segundo piso. Una fila por entidad. Usar entidad_codigo como referencia estable (entidad_id es sustituta y puede cambiar si la base se reconstruye). Filtrar siempre por tipo_entidad antes de sumar hechos.';
COMMENT ON COLUMN marts.dim_entidad.entidad_id IS 'Llave sustituta. No usar como referencia externa: puede cambiar en una reconstrucción; usar entidad_codigo.';
COMMENT ON COLUMN marts.dim_entidad.entidad_codigo IS 'Llave natural estable: código curado (p. ej. PICHINCHA) para bancos o BCE_<RUC> para entidades auto-registradas.';
COMMENT ON COLUMN marts.dim_entidad.ruc IS 'RUC de la entidad (desde BCE y SEPS). Hay pares de entidades que comparten RUC: ver vw_entidad_ruc_colisiones.';
COMMENT ON COLUMN marts.dim_entidad.segmento_entidad_id IS 'Última clasificación conocida de la entidad en dim_segmento_entidad (SCD1). Para análisis histórico usar la de cada semana en los hechos BCE. NO REPORTA AL BCE si no tiene filas en tsp/tsa.';

COMMENT ON TABLE marts.dim_fecha IS 'Calendario. fecha_id = AAAAMMDD. Contiene los cortes mensuales (último día del mes) y las fechas semanales del BCE.';
COMMENT ON COLUMN marts.dim_fecha.anio IS 'Año.';
COMMENT ON COLUMN marts.dim_fecha.mes IS 'Mes (1-12).';
COMMENT ON COLUMN marts.dim_fecha.dia IS 'Día del mes.';
COMMENT ON COLUMN marts.dim_fecha.trimestre IS 'Trimestre (1-4).';
COMMENT ON COLUMN marts.dim_fecha.nombre_mes IS 'Nombre del mes en español (Enero..Diciembre), independiente del idioma del servidor.';
COMMENT ON COLUMN marts.dim_fecha.anio_mes IS 'Año y mes como entero AAAAMM, para agrupar fechas semanales por mes.';

COMMENT ON TABLE marts.dim_provincia IS 'Provincias del Ecuador con región y código oficial INEC. Incluye S/N (operaciones sin provincia, cantón NACIONAL del BCE) y ZONA NO DELIMITADA, ambas sin región.';
COMMENT ON COLUMN marts.dim_provincia.region IS 'Región natural (COSTA, SIERRA, AMAZONIA, INSULAR). NULL para S/N y ZONA NO DELIMITADA.';
COMMENT ON COLUMN marts.dim_provincia.codigo_inec IS 'Código de provincia del INEC (2 dígitos, DPA vigente).';

COMMENT ON TABLE marts.dim_canton IS 'Cantones (DPA del INEC vigente, 221 cantones más NACIONAL). Una fila por par (cantón, provincia): los homónimos de provincias distintas (BOLIVAR, OLMEDO) son filas distintas; unir siempre por canton_id, nunca por nombre. Fuente de verdad: seed canton_provincia.csv del ETL.';
COMMENT ON COLUMN marts.dim_canton.codigo_inec IS 'Código de cantón del INEC (4 dígitos: provincia + cantón). Permite unir con estadísticas del INEC.';

COMMENT ON TABLE marts.dim_segmento_credito IS 'Segmento normativo de crédito (nivel grueso, 7 valores: PRODUCTIVO, CONSUMO, INMOBILIARIO, MICROCRÉDITO, VIVIENDA DE INTERÉS PÚBLICO, EDUCATIVO, INVERSIÓN PÚBLICA). Agrupa también la terminología anterior a 2022 (Comercial, Vivienda).';
COMMENT ON TABLE marts.dim_subsegmento_credito IS 'Subsegmento de crédito tal como lo reporta el BCE (nivel fino, 26 valores). Sube al segmento grueso por segmento_id.';
COMMENT ON COLUMN marts.dim_subsegmento_credito.subsegmento IS 'Nombre del subsegmento según el BCE (p. ej. CONSUMO ORDINARIO, MICROCRÉDITO MINORISTA).';

COMMENT ON TABLE marts.dim_categoria_deposito IS 'Categorías de depósito conformadas entre CAPCOL, SEPS y BCE (ahorro, monetarios, a plazo, restringidos, etc.).';
COMMENT ON COLUMN marts.dim_categoria_deposito.categoria IS 'Nombre de la categoría de depósito.';

COMMENT ON TABLE marts.dim_plazo IS 'Bandas de plazo por rango de días, descubiertas desde cada fuente. Bandas de fuentes distintas que no calzan quedan como filas separadas (p. ej. más de 360 vs. más de 361 días).';
COMMENT ON COLUMN marts.dim_plazo.dias_desde IS 'Inicio de la banda, en días.';
COMMENT ON COLUMN marts.dim_plazo.dias_hasta IS 'Fin de la banda, en días. NULL = sin tope.';
COMMENT ON COLUMN marts.dim_plazo.plazo_codigo IS 'Etiqueta original de la banda en la fuente que la creó.';

COMMENT ON TABLE marts.dim_segmento_entidad IS 'Clasificación de la entidad publicada por el BCE en tsp/tsa: SEGMENTO 1-5 y SIN SEGMENTO (cooperativas; SIN SEGMENTO = antes de 2015), SEGMENTO 1 MUTUALISTA, BANCO GRANDE/MEDIANO/PEQUEÑO, BANCOS PUBLICOS, SOCIEDAD FINANCIERA, ADMINISTRADORA DE TARJETAS DE CREDITO y NO REPORTA AL BCE.';
COMMENT ON COLUMN marts.dim_segmento_entidad.tipo_segmento IS 'Etiqueta de la clasificación. MUTUALISTAS (BCE desde 2025) se homologa a SEGMENTO 1 MUTUALISTA.';

COMMENT ON TABLE marts.dim_cuenta_contable IS 'Plan de cuentas (Catálogo Único de Cuentas) de los reportes BALANCE y PYG, descubierto en el Boletín de Superbancos y en los EEFF de la SEPS. Claves: cartera bruta = 14 - 1499, depósitos = 21, ingresos = 5, gastos = 4.';
COMMENT ON COLUMN marts.dim_cuenta_contable.cuenta_id IS 'Llave sustituta de la cuenta.';
COMMENT ON COLUMN marts.dim_cuenta_contable.reporte IS 'Reporte al que pertenece la cuenta: BALANCE o PYG.';
COMMENT ON COLUMN marts.dim_cuenta_contable.codigo IS 'Código de la cuenta en el Catálogo Único (1 a 6 dígitos).';
COMMENT ON COLUMN marts.dim_cuenta_contable.cuenta IS 'Nombre de la cuenta (redacción de Superbancos cuando el código es compartido con la SEPS).';
COMMENT ON COLUMN marts.dim_cuenta_contable.nivel IS 'Nivel jerárquico = cantidad de dígitos del código.';
COMMENT ON COLUMN marts.dim_cuenta_contable.codigo_padre IS 'Código de la cuenta padre en la jerarquía.';
COMMENT ON COLUMN marts.dim_cuenta_contable.seccion IS 'Sección por primer dígito (activo, pasivo, patrimonio, gastos, ingresos, contingentes, orden).';
COMMENT ON COLUMN marts.dim_cuenta_contable.grupo_met IS 'Grupo funcional de la hoja MET del Boletín (solo BALANCE; un código puede pertenecer a varios, se guarda el primero).';

-- ───────────── Hechos ─────────────
COMMENT ON TABLE marts.fact_saldo_cartera IS 'Saldo de cartera de crédito por mes x entidad x cantón x segmento de crédito, en USD. Fuentes: CAPCOL de Superbancos (bancos privados y públicos) y SEPS (cooperativas S1-S3, mutualistas, segundo piso). Mezcla tipos de entidad. En mutualistas incluye cartera de vivienda vendida al fideicomiso (no está en su balance).';
COMMENT ON COLUMN marts.fact_saldo_cartera.fact_saldo_cartera_id IS 'Llave sustituta de la fila.';
COMMENT ON COLUMN marts.fact_saldo_cartera.saldo_por_vencer IS 'Cartera por vencer, USD.';
COMMENT ON COLUMN marts.fact_saldo_cartera.saldo_no_devenga_intereses IS 'Cartera que no devenga intereses, USD.';
COMMENT ON COLUMN marts.fact_saldo_cartera.saldo_vencida IS 'Cartera vencida, USD.';
COMMENT ON COLUMN marts.fact_saldo_cartera.saldo_total IS 'Suma de por vencer + no devenga + vencida, USD (columna generada). Morosidad = (no devenga + vencida) / total.';

COMMENT ON TABLE marts.fact_saldo_depositos IS 'Saldo de depósitos por mes x entidad x cantón x categoría de depósito x plazo, en USD. Fuentes: CAPCOL (bancos) y SEPS. La SEPS no trae banda de plazo (plazo_id NULL). Los depósitos de bancos por cantón no cubren 5 subcuentas del grupo 21 del balance.';
COMMENT ON COLUMN marts.fact_saldo_depositos.fact_saldo_depositos_id IS 'Llave sustituta de la fila.';
COMMENT ON COLUMN marts.fact_saldo_depositos.saldo IS 'Saldo de depósitos, USD.';
COMMENT ON COLUMN marts.fact_saldo_depositos.numero_clientes IS 'Número de clientes depositantes.';
COMMENT ON COLUMN marts.fact_saldo_depositos.numero_cuentas IS 'Número de cuentas.';

COMMENT ON TABLE marts.fact_colocaciones_cartera IS 'Operaciones de crédito concedidas por semana x entidad x subsegmento x plazo x cantón (BCE, tasas activas tsa, desde 2008). Sistema financiero completo. Las tasas se promedian ponderando por monto_total, nunca en forma simple. Incluye filas con cantón NACIONAL: son sumables y excluirlas subcuenta.';
COMMENT ON COLUMN marts.fact_colocaciones_cartera.fact_colocaciones_cartera_id IS 'Llave sustituta de la fila.';
COMMENT ON COLUMN marts.fact_colocaciones_cartera.monto_total IS 'Monto concedido en la semana, USD. Sumable.';
COMMENT ON COLUMN marts.fact_colocaciones_cartera.numero_operaciones IS 'Número de operaciones en la semana. Sumable.';
COMMENT ON COLUMN marts.fact_colocaciones_cartera.tasa_activa_efectiva IS 'Tasa activa efectiva anual, %, ponderada por monto dentro de la fila. Agregar con SUM(tasa*monto)/SUM(monto).';
COMMENT ON COLUMN marts.fact_colocaciones_cartera.tasa_nominal IS 'Tasa nominal anual, %, ponderada por monto. Agregar con SUM(tasa*monto)/SUM(monto).';

COMMENT ON TABLE marts.fact_captaciones_depositos IS 'Captaciones por semana x entidad x categoría de depósito x plazo x cantón (BCE, tasas pasivas tsp, desde 2008). Sistema financiero completo. Las tasas se promedian ponderando por monto_total. Incluye filas con cantón NACIONAL: son sumables y excluirlas subcuenta.';
COMMENT ON COLUMN marts.fact_captaciones_depositos.fact_captaciones_depositos_id IS 'Llave sustituta de la fila.';
COMMENT ON COLUMN marts.fact_captaciones_depositos.monto_total IS 'Monto captado en la semana, USD. Sumable.';
COMMENT ON COLUMN marts.fact_captaciones_depositos.numero_operaciones IS 'Número de operaciones en la semana. Sumable.';
COMMENT ON COLUMN marts.fact_captaciones_depositos.tasa_pasiva_efectiva IS 'Tasa pasiva efectiva anual, %, ponderada por monto. Agregar con SUM(tasa*monto)/SUM(monto).';
COMMENT ON COLUMN marts.fact_captaciones_depositos.tasa_nominal IS 'Tasa nominal anual, %, ponderada por monto. Agregar con SUM(tasa*monto)/SUM(monto).';

COMMENT ON TABLE marts.fact_balance IS 'Saldos de balance por mes x entidad x cuenta contable, en USD. Fuentes: Boletín de Superbancos (bancos privados) y EEFF de la SEPS (cooperativas y mutualistas). Banca pública no tiene balance cargado. La SEPS no carga saldos en cero: una cuenta ausente vale 0.';
COMMENT ON COLUMN marts.fact_balance.fact_id IS 'Llave sustituta de la fila.';
COMMENT ON COLUMN marts.fact_balance.saldo_usd IS 'Saldo de la cuenta al corte, USD (el Boletín reporta en miles; ya convertido).';

COMMENT ON TABLE marts.fact_pyg IS 'Estado de resultados por mes x entidad x cuenta contable, en USD, acumulado del año a la fecha de corte. Mismas fuentes que fact_balance. Para anualizar ver vw_utilidad_anualizada.';
COMMENT ON COLUMN marts.fact_pyg.fact_id IS 'Llave sustituta de la fila.';
COMMENT ON COLUMN marts.fact_pyg.valor_usd IS 'Valor de la cuenta acumulado en el año, USD.';

COMMENT ON TABLE marts.fact_tasas_referenciales_cartera IS 'Tasas activas regulatorias por mes x subsegmento de crédito (BCE TasasHistorico, desde 2009-07): máxima vigente y referencial. Nivel sistema, no por entidad.';
COMMENT ON COLUMN marts.fact_tasas_referenciales_cartera.tasa_activa_maxima IS 'Tasa activa efectiva máxima (techo legal) del subsegmento, %.';
COMMENT ON COLUMN marts.fact_tasas_referenciales_cartera.tasa_activa_referencial IS 'Tasa activa efectiva referencial del subsegmento, %.';

COMMENT ON TABLE marts.fact_tasas_referenciales_depositos_instrumento IS 'Tasa pasiva promedio del sistema por mes x categoría de depósito (BCE TasasHistorico).';
COMMENT ON COLUMN marts.fact_tasas_referenciales_depositos_instrumento.tasa_pasiva_promedio IS 'Tasa pasiva efectiva promedio del instrumento, %.';

COMMENT ON TABLE marts.fact_tasas_referenciales_depositos_plazo IS 'Tasa pasiva referencial por mes x banda de plazo (BCE TasasHistorico).';
COMMENT ON COLUMN marts.fact_tasas_referenciales_depositos_plazo.tasa_pasiva_referencial IS 'Tasa pasiva efectiva referencial de la banda de plazo, %.';

COMMENT ON TABLE marts.fact_tasas_referenciales_sistema IS 'Tasas de referencia del sistema por mes (BCE TasasHistorico): pasiva y activa referencial, tasa legal y máxima convencional.';
COMMENT ON COLUMN marts.fact_tasas_referenciales_sistema.tasa_pasiva_referencial_sistema IS 'Tasa pasiva referencial del sistema (TPR), %.';
COMMENT ON COLUMN marts.fact_tasas_referenciales_sistema.tasa_activa_referencial_sistema IS 'Tasa activa referencial del sistema (TAR), %.';
COMMENT ON COLUMN marts.fact_tasas_referenciales_sistema.tasa_legal IS 'Tasa legal, %.';
COMMENT ON COLUMN marts.fact_tasas_referenciales_sistema.tasa_maxima_convencional IS 'Tasa máxima convencional, %.';

-- ───────────── Vistas ─────────────
COMMENT ON VIEW marts.vw_cartera_market_share IS 'Cuota de cartera por entidad y mes sobre TODO el sistema (no filtra tipo de entidad). Para cuota entre pares, calcular filtrando por tipo_entidad.';
COMMENT ON COLUMN marts.vw_cartera_market_share.saldo_entidad IS 'Cartera total de la entidad en el mes, USD.';
COMMENT ON COLUMN marts.vw_cartera_market_share.saldo_total_mes IS 'Cartera total del sistema en el mes, USD.';
COMMENT ON COLUMN marts.vw_cartera_market_share.market_share_pct IS 'Cuota de la entidad sobre el sistema, % (0-100).';
COMMENT ON VIEW marts.vw_depositos_market_share IS 'Cuota de depósitos por entidad y mes sobre TODO el sistema (no filtra tipo de entidad).';
COMMENT ON COLUMN marts.vw_depositos_market_share.saldo_entidad IS 'Depósitos totales de la entidad en el mes, USD.';
COMMENT ON COLUMN marts.vw_depositos_market_share.saldo_total_mes IS 'Depósitos totales del sistema en el mes, USD.';
COMMENT ON COLUMN marts.vw_depositos_market_share.market_share_pct IS 'Cuota de la entidad sobre el sistema, % (0-100).';
COMMENT ON VIEW marts.vw_cartera_hhi IS 'Índice Herfindahl-Hirschman de la cartera por mes, sobre todo el sistema.';
COMMENT ON COLUMN marts.vw_cartera_hhi.hhi IS 'HHI = suma de cuotas % al cuadrado (0-10.000; más de 2.500 se lee como mercado concentrado).';
COMMENT ON VIEW marts.vw_depositos_hhi IS 'Índice Herfindahl-Hirschman de los depósitos por mes, sobre todo el sistema.';
COMMENT ON COLUMN marts.vw_depositos_hhi.hhi IS 'HHI = suma de cuotas % al cuadrado (0-10.000).';

COMMENT ON VIEW marts.vw_cartera_bruta IS 'Cartera bruta contable por entidad y mes: cuenta 14 menos provisiones 1499 (fact_balance).';
COMMENT ON COLUMN marts.vw_cartera_bruta.cartera_bruta IS 'Cartera bruta = 14 - 1499, USD.';
COMMENT ON VIEW marts.vw_cartera_bruta_segmento IS 'Cartera bruta contable por entidad, mes y segmento de crédito (subcuentas de nivel 4 del grupo 14).';
COMMENT ON COLUMN marts.vw_cartera_bruta_segmento.cartera_bruta_segmento IS 'Cartera bruta del segmento, USD.';
COMMENT ON VIEW marts.vw_cartera_improductiva IS 'Cartera improductiva contable (que no devenga intereses + vencida) por entidad y mes.';
COMMENT ON COLUMN marts.vw_cartera_improductiva.cartera_improductiva IS 'Cartera que no devenga intereses + vencida, USD.';
COMMENT ON VIEW marts.vw_cartera_improductiva_segmento IS 'Cartera improductiva contable por entidad, mes y segmento de crédito.';
COMMENT ON COLUMN marts.vw_cartera_improductiva_segmento.cartera_improductiva IS 'Cartera que no devenga intereses + vencida del segmento, USD.';
COMMENT ON VIEW marts.vw_depositos_corto_plazo IS 'Depósitos de corto plazo por entidad y mes: cuentas 2101 (a la vista) + 210305 y 210310 (a plazo de 1 a 90 días).';
COMMENT ON COLUMN marts.vw_depositos_corto_plazo.depositos_corto_plazo IS 'Depósitos de corto plazo, USD.';
COMMENT ON VIEW marts.vw_pyg_total_gastos IS 'Total de gastos por entidad y mes como suma de las cuentas 41 a 48 (la cuenta 4 no siempre viene en la fuente). Acumulado del año.';
COMMENT ON COLUMN marts.vw_pyg_total_gastos.total_gastos IS 'Gastos acumulados del año, USD.';
COMMENT ON VIEW marts.vw_utilidad_acumulada IS 'Utilidad acumulada del año por entidad y mes: ingresos (cuenta 5) menos gastos (vw_pyg_total_gastos).';
COMMENT ON COLUMN marts.vw_utilidad_acumulada.ingresos IS 'Ingresos acumulados del año (cuenta 5), USD.';
COMMENT ON COLUMN marts.vw_utilidad_acumulada.total_gastos IS 'Gastos acumulados del año (cuentas 41-48), USD.';
COMMENT ON COLUMN marts.vw_utilidad_acumulada.utilidad_acumulada IS 'Ingresos - gastos acumulados del año, USD.';
COMMENT ON VIEW marts.vw_utilidad_anualizada IS 'Utilidad anualizada por entidad y mes: utilidad acumulada x 12 / mes.';
COMMENT ON COLUMN marts.vw_utilidad_anualizada.mes IS 'Mes del corte (1-12), usado para anualizar.';
COMMENT ON COLUMN marts.vw_utilidad_anualizada.utilidad_acumulada IS 'Utilidad acumulada del año, USD.';
COMMENT ON COLUMN marts.vw_utilidad_anualizada.utilidad_anualizada IS 'Utilidad acumulada x 12 / mes, USD. Base de ROA y ROE.';
COMMENT ON VIEW marts.vw_activo_promedio_ytd IS 'Activo total (cuenta 1) promedio desde diciembre del año anterior hasta el corte, por entidad y mes. Denominador del ROA. Pesada: tarda decenas de segundos.';
COMMENT ON COLUMN marts.vw_activo_promedio_ytd.activo_promedio_ytd IS 'Promedio del activo total en la ventana diciembre anterior - corte, USD.';
COMMENT ON VIEW marts.vw_patrimonio_promedio_ytd IS 'Patrimonio (cuenta 3) promedio desde diciembre del año anterior hasta el corte, por entidad y mes. Denominador del ROE. Pesada.';
COMMENT ON COLUMN marts.vw_patrimonio_promedio_ytd.patrimonio_promedio_ytd IS 'Promedio del patrimonio en la ventana diciembre anterior - corte, USD.';

COMMENT ON COLUMN marts.vw_conciliacion_saldos_balance.medida IS 'cartera o depositos.';
COMMENT ON COLUMN marts.vw_conciliacion_saldos_balance.saldo_reportado IS 'Suma de los saldos por cantón de la entidad en el mes (fact_saldo_cartera o fact_saldo_depositos), USD.';
COMMENT ON COLUMN marts.vw_conciliacion_saldos_balance.saldo_contable IS 'Saldo contable de la entidad en el mes (cartera 14 - 1499 o depósitos 21), USD.';
COMMENT ON COLUMN marts.vw_conciliacion_saldos_balance.diferencia_pct IS 'saldo_reportado / saldo_contable - 1 (fracción: 0.01 = 1 %).';
COMMENT ON COLUMN marts.vw_conciliacion_resumen.medida IS 'cartera o depositos.';
COMMENT ON COLUMN marts.vw_conciliacion_resumen.entidades IS 'Entidades conciliadas en el mes.';
COMMENT ON COLUMN marts.vw_conciliacion_resumen.mediana_pct IS 'Mediana de diferencia_pct entre entidades (fracción).';
COMMENT ON COLUMN marts.vw_conciliacion_resumen.dentro_05pct IS 'Fracción de entidades con diferencia dentro de +-0,5 %.';
COMMENT ON COLUMN marts.vw_conciliacion_resumen.dentro_2pct IS 'Fracción de entidades con diferencia dentro de +-2 %.';
COMMENT ON COLUMN marts.vw_conciliacion_resumen.diferencia_agregada_pct IS 'Diferencia del total del tipo de entidad: suma reportada / suma contable - 1 (fracción).';

COMMENT ON VIEW marts.vw_dim_canton_geografia IS 'dim_canton con provincia y región ya resueltas y un indicador de geografía conocida.';
COMMENT ON COLUMN marts.vw_dim_canton_geografia.es_geografia_conocida IS 'false para cantones sin región (NACIONAL, S/N, zona no delimitada): excluirlos en mapas, no en totales.';
COMMENT ON VIEW marts.vw_entidad_ruc_colisiones IS 'Entidades distintas de dim_entidad que comparten RUC (control de gobernanza de identidad).';

-- ───────────── Columnas que se repiten en varias tablas y vistas ─────────────
-- Solo completa las que siguen sin comentario después de lo de arriba.
DO $$
DECLARE
    genericos CONSTANT jsonb := jsonb_build_object(
        'fecha_id', 'Fecha del corte (AAAAMMDD). FK a dim_fecha. Mensual: último día del mes; BCE: fecha de la semana.',
        'fecha', 'Fecha del corte.',
        'entidad_id', 'Entidad financiera. FK a dim_entidad (sustituta: para referencias estables usar dim_entidad.entidad_codigo).',
        'entidad', 'Nombre de la entidad para mostrar.',
        'entidad_codigo', 'Código estable de la entidad (dim_entidad.entidad_codigo).',
        'tipo_entidad', 'Tipo de entidad: BANCO PRIVADO, BANCO PUBLICO, COOPERATIVA, MUTUALISTA, ENTIDAD DE SEGUNDO PISO, SOCIEDAD FINANCIERA o TARJETAS DE CREDITO.',
        'ruc', 'RUC de la entidad.',
        'canton_id', 'Cantón. FK a dim_canton (incluye NACIONAL para operaciones sin cantón).',
        'canton', 'Nombre del cantón (normalizado, sin tildes).',
        'provincia_id', 'Provincia. FK a dim_provincia.',
        'provincia', 'Nombre de la provincia.',
        'region', 'Región natural de la provincia.',
        'segmento_id', 'Segmento normativo de crédito (nivel grueso). FK a dim_segmento_credito.',
        'segmento', 'Nombre del segmento de crédito.',
        'subsegmento_id', 'Subsegmento de crédito del BCE (nivel fino). FK a dim_subsegmento_credito.',
        'categoria_deposito_id', 'Categoría de depósito. FK a dim_categoria_deposito.',
        'plazo_id', 'Banda de plazo. FK a dim_plazo. NULL si la fuente no la trae (SEPS).',
        'cuenta_id', 'Cuenta contable. FK a dim_cuenta_contable.',
        'segmento_entidad_id', 'Clasificación de la entidad en esa fecha según el BCE. FK a dim_segmento_entidad.',
        'estado_validacion', 'CONFIRMADO (curado) o AUTO_INGRESADO (alta automática pendiente de revisión).',
        'fecha_carga', 'Momento en que la fila se insertó (auditoría).',
        'fecha_actualizacion', 'Momento del último cambio real de la fila (auditoría; no se mueve si el dato no cambia).'
    );
    r record;
BEGIN
    FOR r IN
        SELECT c.relname, a.attname
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum > 0 AND NOT a.attisdropped
        WHERE n.nspname = 'marts' AND c.relkind IN ('r', 'v')
          AND col_description(c.oid, a.attnum) IS NULL
          AND genericos ? a.attname
    LOOP
        EXECUTE format('COMMENT ON COLUMN marts.%I.%I IS %L', r.relname, r.attname, genericos ->> r.attname);
    END LOOP;
END $$;

-- PK de cada dimensión: el genérico dice "FK a ..."; en su propia tabla es la llave.
COMMENT ON COLUMN marts.dim_canton.canton_id IS 'Llave sustituta del cantón.';
COMMENT ON COLUMN marts.dim_provincia.provincia_id IS 'Llave sustituta de la provincia.';
COMMENT ON COLUMN marts.dim_segmento_credito.segmento_id IS 'Llave sustituta del segmento de crédito.';
COMMENT ON COLUMN marts.dim_subsegmento_credito.subsegmento_id IS 'Llave sustituta del subsegmento.';
COMMENT ON COLUMN marts.dim_categoria_deposito.categoria_deposito_id IS 'Llave sustituta de la categoría.';
COMMENT ON COLUMN marts.dim_plazo.plazo_id IS 'Llave sustituta de la banda de plazo.';
COMMENT ON COLUMN marts.dim_segmento_entidad.segmento_entidad_id IS 'Llave sustituta de la clasificación.';
COMMENT ON COLUMN marts.dim_fecha.fecha_id IS 'Llave: fecha como entero AAAAMMDD.';
COMMENT ON COLUMN marts.dim_fecha.fecha IS 'Fecha.';
COMMENT ON COLUMN marts.dim_subsegmento_credito.segmento_id IS 'Segmento grueso al que pertenece el subsegmento. FK a dim_segmento_credito.';
COMMENT ON COLUMN marts.dim_canton.provincia_id IS 'Provincia del cantón. FK a dim_provincia.';
