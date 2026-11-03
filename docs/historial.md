# Historial de decisiones y correcciones

Una línea por hecho que todavía explica por qué el modelo es como es. El detalle completo
(investigación, conteos, verificaciones) está en el historial de git de cada documento;
`git log -p -- docs/<archivo>.md` lo recupera. Las migraciones `sql/NN_*.sql` traen su
propio encabezado con el motivo.

## 2026-07 — Integración de BCE y normalización del modelo

- **07-18** — La fuente de tasas activas semanales es `tsa`, no `tmp` (que es pasivas mensual). Los mensuales `tmp`/`tma` quedan fuera de alcance.
- **07-19** — BCE se filtraba a bancos privados antes de guardar y se perdía ~85% del archivo. Desde entonces se guarda el sistema completo: bancos privados con crosswalk curado y el resto auto-registrado por RUC.
- **07-19** — Hechos renombrados por proceso de negocio (`sql/15`), por ejemplo `fact_tasas_activas` → `fact_colocaciones_cartera`. Regla: calificador genérico en singular y término de negocio en su número real. Se eliminaron columnas nunca pobladas (`tasa_ponderada`, `morosidad`, `saldo_x_tasa`).
- **07-19** — Choque de grano en el crédito: CAPCOL reporta 7 segmentos normativos y BCE 26 sub-segmentos. Se resolvió con dos dimensiones y outrigger por FK (`sql/16`).
- **07-23** — Se activó `dim_entidad.ruc` (BCE lo trae para todas). Se eliminó `tamano` con un diagnóstico que resultó incorrecto (ver 07-25).
- **07-25** — `tipo_segmento` de BCE trae el tamaño o segmento de la entidad y se venía descartando sin leerlo; se modeló en `dim_segmento_entidad` (`sql/19`). Lección: "columna vacía" no significa "la fuente no lo tiene".
- **07-25** — La misma provincia tenía dos regiones según el reporte de origen. Se creó `dim_provincia` como única fuente de `region` (`sql/20`).
- **07-25** — `estado_cartera` era EAV, con 3 filas por hecho. Se pivotó a 3 columnas de saldo más `saldo_total` generado (`sql/21`).
- Antes de BCE — CAPCOL partía un mismo banco en dos filas cuando cambiaba de nombre (Comercial de Manabí, Amibank). El crosswalk de nombres lo resuelve.

## 2026-08 — Calidad de catálogos

- **08-22** — Pares de entidades que comparten RUC (cambio de forma legal, como cooperativa que pasa a banco). No se fusionan; se exponen en `vw_entidad_ruc_colisiones` (`sql/22`).
- **08-27** — Unicidad NULL-safe sobre `canton` en `staging.cartera` y `staging.depositos` (`sql/23`, `sql/24`). Es el mismo tipo de bug que se corrigió en `sql/10`.
- **08-27 / 08-30** — `dim_plazo` pasó de abierto a fail-fast y luego a two-tier (`sql/27`). `estado_validacion` se agregó también en `dim_cuenta_contable` (`sql/25`) y `dim_entidad` (`sql/26`).
- **08-30** — Validación estructural del RUC (módulo 11) antes de auto-registrar una entidad. Se corrió contra las 409 entidades vigentes: 0 rechazos.
- **08-30** — CDC de `dim_entidad`: una columna omitida en el `INSERT ... ON CONFLICT` hacía que todas las filas se actualizaran en cada refresh. Corregido.
- **08-30** — `_log_cantones_no_resueltos()`: el `INNER JOIN` a provincia descartaba filas sin aviso; ahora queda registrado en el log.

## 2026-09 — Cantón en BCE, Banca Pública y SEPS

- **09-01** — BCE pasa de grano provincia a grano cantón (`sql/28`), compartiendo `dim_canton` con CAPCOL. `dim_canton` queda two-tier, con alias de escritura en `_ALIASES_CANTON`.
- **09-30** — SEPS cargada. Su cartera son saldos y conforma con `fact_saldo_cartera`, así que se descartó el `fact_volumen_cartera` diseñado. Migraciones `sql/29` (segundo piso), `sql/30` (a la vista) y `sql/31`.
- **09-30** — Cantones homónimos (BOLÍVAR en Carchi y en Manabí): la provincia entra en la llave natural de staging (`sql/31`). El paso a COPY con tabla temporal hace que un duplicado dentro de un archivo falle en vez de pisar la fila anterior.

## 2026-10 — Operación desatendida y portabilidad

- **10-01** — Banca Pública cargada. Mutualistas (cartera en fideicomiso) y emisoras de tarjetas (consumo sin tarjetas) explicadas y no corregidas (`docs/fuentes_datos.md`, "Diferencias de criterio y conciliación").
- **10-02** — Las vistas de `sql/18` nunca se habían aplicado a la base viva. Se aplicaron con `sql/32` y se validaron contra el motor de referencia.
- **10-05** — Se elimina la capa `raw` JSONB (12 GB sin lecturas; `sql/33`). CDC por columnas sin `row_hash`, refresh de marts incremental con marca de agua (`sql/34`) y proyecto empaquetado con uv. Los 3 bancos públicos se curan.
- **10-09** — Códigos INEC y fusión de cantones duplicados (`sql/35`, `sql/36`). `dim_banco` → `dim_entidad` (`sql/37`).
- **10-09** — `migrate` con registro de migraciones (`sql/38`), conciliación automática (`sql/39`) y `nombre_mes` sin depender del locale (`sql/40`).
- **10-09** — `actualizar` con bloqueo y códigos de salida, reintentos de red y Power BI retirado del repo.
- **10-09** — `TasasHistorico` ampliado a 2009-07. El parser leía mal el punto decimal y la sección "VIGENTES"; 2022-04 a 2022-07 se reprocesaron.
- **10-10** — Reconstrucción desde cero. Una republicación de CAPCOL con nombres cambiados duplicaba saldos de 13 bancos (ene-jun 2026). Ahora cada publicación reemplaza a la anterior y el refresh borra los hechos huérfanos.
- **10-10** — Ids compactos: el refresh ya no consume la secuencia. Segmento de entidad homologado y sin nulos (`sql/41`). Muestras Parquet a 13 meses e historial de git reescrito (~890 MB → ~29 MB).
- **10-11** — Rol de solo lectura para el repo de análisis (`sql/admin/rol_lectura.sql` y `sql/42`).
- **10-31** — Se quitan 2 tablas vacías y 3 columnas siempre NULL (`sql/43`). Descripciones `COMMENT ON` en todo `marts` (`sql/44`) y ruff como único formateador.

## 2026-11

- **11-01** — `graphify-out/` sale de git. Documentación condensada al estado vigente, con esta bitácora como único registro histórico. Se eliminó `docs/propuesta_escalabilidad_etl.md`: lo que seguía abierto pasó a las brechas del runbook.
- **11-01** — En la base reconstruida, los 21 plazos y las 1.902 cuentas habían quedado `AUTO_INGRESADO`: `sql/25` y `sql/27` solo confirmaban las filas existentes al migrar. Ahora el refresh confirma contra un universo curado (los sets de plazo de cada fuente y `seeds/cuenta_contable.csv`), igual que los cantones (`sql/45`).
- **11-01** — Los `download_id` de la SEPS de un año nuevo se leen del portal (antes había que agregarlos en código cada enero). Flag `--reprocesar` para recargar archivos ya cargados tras cambiar un parser o el crosswalk, sin borrar `meta.source_files` a mano (brechas B15 y B8).
