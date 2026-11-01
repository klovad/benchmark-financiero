# Gobernanza de datos

Quién responde por el dato, cómo se clasifica, qué garantías de calidad existen (todas
verificadas en código) y qué huecos se conocen. Enlaza a la referencia de cada pieza en
vez de repetirla. La historia de cada decisión está en `docs/historial.md`.

## Mapa de la documentación

| Pregunta | Documento |
|---|---|
| ¿Cómo se relacionan las tablas? (estructura, diagrama ER, CDC) | `docs/architecture.md` |
| ¿Qué significa cada campo? (grano, nulabilidad) | `docs/data_dictionary.md` y los `COMMENT ON` de la base (`sql/44`) |
| ¿De dónde vino cada campo? | `docs/linaje_datos.md` |
| ¿Cómo es cada fuente? | `docs/fuentes_datos.md` |
| ¿Qué hago si falla un matching o aparece un `AUTO_INGRESADO`? | `docs/mantenimiento_catalogos.md` |
| ¿Cómo instalo, opero y programo? | `docs/despliegue_y_orquestacion.md` |
| Reglas, responsables y huecos | este documento |

## Responsabilidad y clasificación

- **Responsable (steward)**: Kevin Flores, autor y responsable único. Sin equipo ni flujo
  formal de aprobación: el control son el código, los tests y la CI.
- **Clasificación**: **público** en todas las capas. Las 5 fuentes son estadísticas
  oficiales abiertas (Superbancos, BCE, SEPS). Sin datos personales: el grano más fino es
  entidad × cantón × producto × fecha. Solo las credenciales (`.env`, no versionado) son
  sensibles.
- **Acceso**: el ETL escribe con el rol de la aplicación (dueño de los esquemas); el
  análisis lee con el rol de solo lectura (`marts_lectura` / `analista`, solo `marts`,
  sesiones `read_only`), creado por `sql/admin/rol_lectura.sql` + `sql/42`. Ver
  `docs/despliegue_y_orquestacion.md` §3.4.
- **Retención**: sin purga. El valor está en el histórico completo. Los archivos de
  `data/raw/**` se conservan como fuente de verdad para reprocesar; staging y marts se
  actualizan en el lugar vía CDC.

## Catálogo de metadatos

### Aterrizaje: archivos + `meta`

| Objeto | Qué guarda | Rol |
|---|---|---|
| `data/raw/**` (disco, no versionado) | Archivos tal como se descargaron | Fuente de verdad: reprocesarlos reconstruye staging y marts |
| `meta.source_files` | `(source_file PK, source_hash, report_type, loaded_at)` | Idempotencia: un archivo con el mismo sha256 no se reprocesa |
| `meta.refresh_watermark` | `(proceso PK, hasta)` | Marca de agua del refresh incremental de marts |
| `meta.schema_migrations` | migraciones aplicadas y su checksum | Lo usa `migrate` |

### `staging`: tipada, identidad ya resuelta, CDC por columnas

| Tabla | Llave natural | Identidad aplicada |
|---|---|---|
| `staging.cartera` | `(fecha, tipo_entidad, banco, provincia, canton, tipo_credito, estado_cartera)`, NULL-safe | `banco_codigo` por crosswalk (CAPCOL) o RUC (SEPS) |
| `staging.depositos` | `(fecha, tipo_entidad, banco, provincia, canton, tipo_deposito)`, NULL-safe | + `categoria_deposito`/`plazo_dias_*` (`categoria_deposito_matching.py`) |
| `staging.bce_tasas_pasivas` / `bce_tasas_activas` | `(fecha, banco_codigo, categoría o segmento, plazo, provincia, canton)` | `resolver_entidad_bce()`, `bce_plazo_matching.py`, `resolver_canton_bce()` |
| `staging.tasas_referenciales` | `(fecha, seccion, dimension_valor, plazo, metrica)` | alias hacia los nombres de los catálogos (`linaje_datos.md`) |
| `staging.boletin_balance` / `boletin_pyg` | `(fecha, banco_codigo, codigo)` | crosswalk (Boletín) o `BCE_<ruc>` (EEFF SEPS) |
| `staging.banco_maestro` | `banco_codigo` | 36 curadas desde `seeds/banco_maestro.csv`; el resto auto-registrado por RUC desde BCE y SEPS |

En CAPCOL y SEPS, cada archivo **reemplaza su alcance** (tipo de entidad × mes × tipo de
crédito en cartera; tipo de entidad × mes en depósitos). Una republicación con nombres
cambiados no deja filas viejas al lado de las nuevas.

### `marts`: esquema estrella conformado

Columnas, grano y advertencias: `docs/data_dictionary.md` y los comentarios de la propia
base. Volúmenes vigentes: `SELECT count(*)` o el catálogo del repo de análisis. No se
mantienen cifras a mano.

| Tabla | Rol | Cadencia |
|---|---|---|
| `dim_fecha` | Conformada, grano día | derivada |
| `dim_entidad` | Conformada; `estado_validacion`: 36 `CONFIRMADO` (curadas) + ~408 `AUTO_INGRESADO` (por RUC) | — |
| `dim_canton` → `dim_provincia` | Conformada, two-tier, códigos INEC | — |
| `dim_segmento_credito` → `dim_subsegmento_credito` | Catálogo cerrado: 7 segmentos normativos y 26 sub-segmentos BCE | sembrado |
| `dim_segmento_entidad` | Catálogo cerrado, 14 valores (incluye `NO REPORTA AL BCE`) | sembrado |
| `dim_categoria_deposito` | Catálogo cerrado, 13 valores | sembrado |
| `dim_plazo` | Two-tier por rango de días; `CONFIRMADO` = universo curado de cada fuente (`sql/45`) | — |
| `dim_cuenta_contable` | Catálogo Único de Cuentas, two-tier; `CONFIRMADO` = `seeds/cuenta_contable.csv` (`sql/45`) | descubierto del Boletín y del EEFF |
| `fact_saldo_cartera`, `fact_saldo_depositos` | Saldos CAPCOL + SEPS | mensual |
| `fact_captaciones_depositos`, `fact_colocaciones_cartera` | BCE tsp/tsa, sistema completo, grano cantón | semanal |
| `fact_tasas_referenciales_*` (4) | BCE `TasasHistorico`, nivel sistema | mensual |
| `fact_balance`, `fact_pyg` | Boletín (bancos privados) + EEFF SEPS, sin saldos en cero | mensual |

**Las tablas de hechos mezclan sectores**: cualquier total, participación o ranking filtra
o agrupa por `dim_entidad.tipo_entidad`.

## Reglas de calidad de datos

1. **Identidad curada, nunca inventada.** Un valor crudo no reconocido lanza una excepción
   propia (`BancoNoResueltoError`, `CategoriaNoResueltaError`, `SegmentoNoResueltoError`,
   `PlazoNoResueltoError`, `CantonNoResueltoError`) en vez de crear una fila silenciosa.
   Hay dos regímenes:
   - **Fail-fast absoluto** en los catálogos regulatorios cerrados: segmentos de crédito,
     categorías de depósito y segmento de entidad. Un nombre regulatorio nuevo necesita
     revisión humana.
   - **Two-tier** en los catálogos finitos pero abiertos: `dim_plazo`, `dim_canton`,
     `dim_cuenta_contable` y las entidades no curadas de `dim_entidad`. Lo malformado
     aborta (rango de plazo inválido, provincia irresoluble, RUC inválido); lo bien
     formado pero desconocido entra `AUTO_INGRESADO` para revisión, sin detener la carga.
2. **Universos validados en BCE.** Segmentos (26), categorías y plazos de tsp y tsa se
   validan contra cada fila antes de escribir a staging.
3. **Llaves NULL-safe.** Toda columna nullable que entra en un `UNIQUE` o `ON CONFLICT`
   usa `COALESCE(col, sentinela)`. Postgres trata `NULL <> NULL` y duplicaba filas
   (`sql/10`, `sql/23`, `sql/24`).
4. **CDC verificado.** Una segunda corrida sin datos nuevos no cambia ninguna fila (el
   guard compara columnas). Se verificó en las 5 fuentes y lo cubren tests de integración.
5. **Staging = marts.** Conteos y saldos coinciden por fuente; el refresh borra los hechos
   de saldo que staging ya no respalda.
6. **Duplicados dentro de un archivo fallan.** La carga por COPY + tabla temporal levanta
   `CardinalityViolation` en vez de quedarse con la última fila.
7. **Fórmulas verificadas contra el valor oficial.** Los indicadores del Boletín se
   recalcularon desde `fact_balance` y coinciden a 6 decimales con lo publicado
   (`docs/metricas_financieras.md`).
8. **RUC validado** antes de auto-registrar una entidad (`validar_ruc_estructura()`): 13
   dígitos, provincia 01-24, tercer dígito 9 o 6 y verificador módulo 11 (algoritmo SRI).
   Un RUC inválido lanza `RucInvalidoError`. No es curación: es una barrera sobre la llave.
9. **Saldos conciliados contra contabilidad, automático.** `sql/39` +
   `benchmark-bancos conciliar` (también al final de cada `actualizar`) comparan los
   saldos por cantón sumados por entidad contra `14 − 1499` (cartera) y `21` (depósitos),
   en los últimos 3 cortes. Umbrales por tipo:
   - cooperativas: mediana ±0,5% y al menos 85-90% de las entidades dentro de ±2%;
   - mutualistas: depósitos ±0,5% (la cartera no se evalúa, por el fideicomiso);
   - bancos privados: cartera ±1% y depósitos ±2%.

   Un mes fuera de umbral es ERROR y la corrida termina con código 2. El histórico
   completo está dentro de umbral.
10. **Metadatos en la base.** Toda tabla, vista y columna de `marts` tiene `COMMENT ON` en
    español (grano, unidad, advertencias), visible desde cualquier cliente. Una migración
    que agrega un objeto o una columna trae su comentario; `tests/test_metadatos.py` falla
    y nombra lo que falte.

Suite: `uv run pytest` (unit sin base; `-m integration` contra Postgres migrado). La CI
corre ambos sobre `postgres:17` desde cero. El número de tests lo da
`pytest --collect-only -q`.

## Huecos de gobernanza conocidos

Decisiones de alcance o limitaciones reales de la fuente: no son bugs silenciosos, pero
quien analice tiene que conocerlas.

| Hueco | Detalle | Referencia |
|---|---|---|
| Cartera de mutualistas incluye la vendida al fideicomiso | +34% a +45% sobre `14 − 1499`. Para contabilidad usar `14 − 1499 + 7401{70,75}` | `fuentes_datos.md` §4.0 |
| Consumo de cooperativas emisoras excluye tarjetas | JEP -13,3%, OSCUS -10,0%, Policía -8,4% contra EEFF; los bancos sí las incluyen | `fuentes_datos.md` §4.0 |
| CAPCOL depósitos no cubre 5 sub-cuentas de `21` | Ejecución presupuestaria, encaje, cheques certificados y de emergencia, otros depósitos. Explican ~48% del faltante (CAPCOL ~0,7% por debajo del Boletín) | `glosario_cuentas.md` §3 |
| 4 bancos con desvío de 2-6% entre CAPCOL y el Boletín en ventanas acotadas | AMIBANK (2023), ATLANTIDA (2025-26), PACIFICO (2022-24), FINCA (2022-12); siempre CAPCOL por debajo. Sin causa investigada | `metricas_financieras.md` |
| Entidades que comparten RUC | 7 pares (cooperativa o financiera que pasa a banco con el mismo RUC). No se fusionan: el cambio de forma legal es real | `marts.vw_entidad_ruc_colisiones` (`sql/22`) |
| PRODUBANCO y PROMERICA | RUC distintos, mismo grupo: Promerica (antes M.M. Jaramillo Arteaga) se fusionó en Produbanco en 2014-10. Solo aparecen juntos en BCE (2009-02 a 2014-10). No tratarlos como competidores en series largas | `dim_entidad` |
| ~408 entidades auto-registradas sin curar | Nombre y tipo tal cual los da el BCE. Curarlas pasa a ser necesario si aparece una colisión de RUC entre dos auto-registradas | `banco_matching.py::resolver_entidad_bce` |
| Republicación que hace desaparecer a una entidad de un mes | El refresh incremental borra huérfanos solo dentro de los (fecha, entidad) recalculados; si una entidad sale entera de un mes, su hecho solo se borra con `refresh --full` | `despliegue_y_orquestacion.md` §4 |
| `dim_cuenta_contable.grupo_met` no es partición | Un código puede caer en 2 o más grupos de `MET`; se guarda el primero | `metricas_financieras.md` |
| EEFF SEPS sin ceros | Un "0 explícito" exige `COALESCE` sobre un `LEFT JOIN` | `data_dictionary.md` |
| Alcance | Boletín y CAPCOL desde 2021; `TasasHistorico` desde 2009-07; SEPS sin segmentos 4-5 ni bases TSV sin RUC; `RK`/`INDICADORES` del Boletín no se cargan | `fuentes_datos.md` |

## Gestión de cambios de esquema

1. Cada cambio va en un `sql/NN_descripcion.sql` nuevo, nunca editando uno aplicado
   (`migrate` lo detecta por checksum). Procedimiento en `docs/despliegue_y_orquestacion.md` §3.2.1.
2. Un valor nuevo de catálogo entra primero al seed o al set validado en Python
   (`seeds/*.csv`, `SEGMENTOS_VALIDOS`, `CATEGORIAS_VALIDAS`). Nunca se relaja una
   validación para dejarlo pasar.
3. Columna nullable en llave natural → `COALESCE` desde el inicio (regla 3).
4. Objeto o columna nuevos en `marts` → su `COMMENT ON` en la misma migración (regla 10).
5. En el mismo cambio se actualizan `docs/data_dictionary.md`, `docs/linaje_datos.md` y el
   diagrama ER de `docs/architecture.md` si corresponde, más una línea en `docs/historial.md`.

Runbook de catálogos (qué tocar cuando algo no resuelve): `docs/mantenimiento_catalogos.md`.
