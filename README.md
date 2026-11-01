# Benchmark de cartera, depósitos y tasas — sistema financiero del Ecuador

ETL que integra cartera, depósitos, tasas de interés y estados financieros del sistema
financiero del Ecuador (bancos privados y públicos, cooperativas de ahorro y crédito y
mutualistas) en un único esquema estrella conformado en Postgres, listo para análisis y
BI. 5 fuentes oficiales:

- [Portal CAPCOL](https://www.superbancos.gob.ec/estadisticas/portalestudios/capcol-bancos/) (Superbancos): cartera y depósitos de bancos privados y de [Banca Pública](https://www.superbancos.gob.ec/estadisticas/portalestudios/capcol-instituciones-publicas/), mensual.
- [Tasas de interés del BCE](https://contenido.bce.fin.ec/documentos/Estadisticas/SectorMonFin/TasasInteres/): tasas activas y pasivas por entidad (semanal) y techos y referenciales regulatorios (mensual).
- [Boletín Financiero Mensual](https://www.superbancos.gob.ec/estadisticas/portalestudios/bancos/) (Superbancos): balance y estado de resultados de bancos privados, mensual.
- [Estadísticas SEPS](https://estadisticas.seps.gob.ec/index.php/estadisticas-sfps/): cartera, depósitos y estados financieros de cooperativas (S1-S3) y mutualistas, mensual.

> **Las tablas de hechos mezclan sectores.** Cualquier total, participación o ranking
> debe filtrar o agrupar por `dim_entidad.tipo_entidad`.

## Documentación

| Tema | Documento |
|---|---|
| Instalar, operar, programar, respaldar y verificar | [`docs/despliegue_y_orquestacion.md`](docs/despliegue_y_orquestacion.md) (runbook) |
| Diseño: flujo, esquema estrella, catálogos conformados, CDC, portabilidad de motor | [`docs/architecture.md`](docs/architecture.md) |
| Cada tabla y columna de `marts` | [`docs/data_dictionary.md`](docs/data_dictionary.md); también como `COMMENT ON` en la base |
| Estructura real de cada fuente y sus diferencias de criterio | [`docs/fuentes_datos.md`](docs/fuentes_datos.md) |
| Linaje campo a campo, archivo → staging → marts | [`docs/linaje_datos.md`](docs/linaje_datos.md) |
| Responsables, reglas de calidad y huecos conocidos | [`docs/gobernanza_datos.md`](docs/gobernanza_datos.md) |
| Qué hacer cuando falla un matching de identidad | [`docs/mantenimiento_catalogos.md`](docs/mantenimiento_catalogos.md) |
| Cuentas contables, indicadores del Boletín y del Excel de referencia | [`docs/glosario_cuentas.md`](docs/glosario_cuentas.md), [`docs/metricas_financieras.md`](docs/metricas_financieras.md), [`docs/indicadores_excel_bcos_coop.md`](docs/indicadores_excel_bcos_coop.md) |
| Por qué cada cosa es como es | [`docs/historial.md`](docs/historial.md) |

## Quickstart

Detalle por sistema operativo, con o sin Docker y para otro Postgres, en el runbook (§2-§4).

```powershell
# 1. Entorno (uv: https://docs.astral.sh/uv/). Sin uv: `pip install -e .` en un venv.
uv sync
uv run playwright install chromium

# 2. Variables de entorno (las leen el ETL y docker-compose.yml; crearlo antes del paso 3)
copy .env.example .env    # ajustar credenciales; rol y base pueden tener cualquier nombre

# 3a. Base en Docker: Postgres 17 con todo sql/ aplicado; `migrate` verifica y registra
docker compose up -d
uv run benchmark-bancos migrate

# 3b. Postgres ya instalado: sql/00 como superusuario y el resto con `migrate`
& "C:\Program Files\PostgreSQL\17\bin\psql.exe" -h localhost -U postgres -d postgres `
    -v app_user=bp_etl -v app_db=benchmark_cartera_depositos -v app_password=changeme `
    -f sql/00_roles_db.sql
uv run benchmark-bancos migrate

# Después de cada `git pull`
uv run benchmark-bancos migrate --status

# 4. Primera carga completa (~70 min descargando todo; respeta el orden BCE → CAPCOL)
uv run benchmark-bancos actualizar --years 2021 2022 2023 2024 2025 2026

# 5. Operación recurrente: lo nuevo de las 5 fuentes, año en curso.
#    Códigos de salida: 0 OK, 1 error, 2 terminó con errores (ver log), 75 otra corrida en curso.
uv run benchmark-bancos actualizar
uv run benchmark-bancos actualizar --fuentes bce seps   # solo algunas

# 6. Programarla (Windows, semanal, lunes 07:30; en Linux/macOS: scripts/actualizar.sh + cron)
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\registrar_tarea.ps1
```

Para analizar sin escribir en la base existe un rol de solo lectura
(`sql/admin/rol_lectura.sql`, runbook §3.4). Sin Postgres, `data/samples/` trae una muestra
de `marts.*` en Parquet (últimos 13 meses).

## Estructura

```
main.py               punto de entrada: `uv run main.py <etapa>` (delega en benchmark_bancos.cli)
pyproject.toml        dependencias (uv), script `benchmark-bancos`, config de ruff/pytest
uv.lock               versiones exactas (local y CI)
src/benchmark_bancos/
  cli.py              línea de comandos (`uv run benchmark-bancos <etapa>`)
  pipeline.py         orquestación por fuente: load_years, load_bce, load_boletin, load_seps...
  orquestacion.py     etapa `actualizar`, bloqueo contra corridas simultáneas, códigos de salida
  migrate.py          etapa `migrate`: aplica sql/ pendientes, sondas y baseline
  conciliacion.py     etapa `conciliar`: saldos contra contabilidad
  config/             settings.py (entorno), sources.py (URLs, ids de descarga), domain.py (vocabulario)
  extract/            Playwright (Superbancos) y descarga directa (BCE, SEPS), con reintentos
  transform/          parsers por fuente + *_matching.py (identidad, resuelta antes de staging)
  load/               load_postgres.py: COPY a staging con CDC por columnas + refresh incremental de marts
  seeds/              banco_maestro.csv, banco_crosswalk.csv, canton_provincia.csv, cuenta_contable.csv
sql/                  00 (rol y base) + 01..NN migraciones; sql/admin/ (superusuario, fuera de migrate)
docker-compose.yml    Postgres 17 reproducible, credenciales desde .env
docs/                 ver "Documentación"
tests/                unit (sin base) e integración (Postgres real)
scripts/              actualizar.ps1/.sh, registrar_tarea.ps1; compute_indicadores_excel.py,
                      export_sample_parquet.py
data/raw/             archivos descargados: fuente de verdad (no versionado)
data/samples/         muestra de marts.* en Parquet (versionada)
```

## Tests y CI

```powershell
uv run pytest -m "not integration"   # unit: parsers, matching, utilidades; sin base ni red
uv run pytest -m integration          # contra un Postgres migrado (fixture db_conn)
uv run pytest                          # ambos
```

Los tests de integración cubren las regresiones que costaron datos: unicidad NULL-safe,
cantones homónimos, el pivote de cartera, CDC sin updates espurios, el refresh incremental,
la publicación que reemplaza a la anterior, el auto-ingreso two-tier, la mecánica COPY y
tabla temporal, y los metadatos de `marts`. `db_conn` siempre hace rollback; los pocos
tests que prueban `ON COMMIT DROP` comitean y se limpian solos, y su helper de limpieza no
debe reutilizarse en otros tests.

CI (`.github/workflows/`, instalación con `uv sync --locked`):
- `lint.yml`: `ruff check` y `ruff format --check`.
- `test.yml`: unit, más integración sobre `postgres:17` desde cero con un rol distinto de
  `bp_etl` (aplica `sql/*.sql` con psql y exige que `migrate` quede en 0 pendientes).

Los scrapers no corren en la CI: dependen de sitios de terceros.

## Alcance de los datos

Cobertura al 2026-11-01. La vigente sale de `SELECT min(fecha_id), max(fecha_id)` por tabla.

| Fuente | Entidades | Cobertura |
|---|---|---|
| CAPCOL | 33 bancos privados + BanEcuador, CFN y BdE | 2021-01 a 2026-09 |
| BCE tsp/tsa | sistema completo (~444 entidades) | semanal, 2008-01 a 2026-10 |
| BCE `TasasHistorico` | nivel sistema | 2009-07 a 2026-09 (antes, fuera de alcance) |
| Boletín Financiero | bancos privados | 2021-01 a 2026-09 |
| SEPS | cooperativas S1-S3, mutualistas, 2 de segundo piso | 2021-01 a 2026-08 |

- **Cartera** por segmento normativo y estado (por vencer, no devenga, vencida);
  **depósitos** por categoría y plazo. Ambos por cantón, con códigos INEC.
- **Tasas** activas por 26 sub-segmentos y pasivas por categoría, por plazo y cantón.
  Antes de agregar, ponderar por monto.
- **Balance y PyG** con el Catálogo Único de Cuentas, en USD (el Boletín reporta en miles).
- `dim_entidad`: 36 entidades curadas y ~408 auto-registradas por RUC.
- **Diferencias de criterio**, para leer antes de comparar (`docs/fuentes_datos.md` §4.0):
  - la cartera de las mutualistas incluye la vendida al fideicomiso;
  - el consumo de las cooperativas emisoras de tarjetas excluye las tarjetas;
  - los depósitos de CAPCOL quedan ~0,7% por debajo del Boletín.

## Estado

Las 5 fuentes están cargadas y se actualizan solas cada semana. Cada corrida concilia los
saldos contra la contabilidad. Todo `marts` está documentado en la base. La instalación
desde cero está probada en la CI y en una reconstrucción completa. Cronología en
`docs/historial.md`.

**Pendientes opcionales**:
- Aviso activo si falla la corrida semanal.
- Tarea de Windows sin sesión iniciada.
- SEPS segmentos 4 y 5 (reporte trimestral).
- `RK`/`INDICADORES` del Boletín como tablas.
- Probar contra un Postgres gestionado real.
- Retomar Power BI (retirado del repo; recuperable desde el historial de git).

Brechas técnicas abiertas en el runbook, §11.
