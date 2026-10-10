"""Migraciones de esquema con registro de lo aplicado (2026-10-09).

Antes no había forma de saber qué `sql/NN_*.sql` tenía aplicada una base, y volver a
correr todo `sql/` sobre una base con datos los borra (varias migraciones hacen TRUNCATE).
Ahora `meta.schema_migrations` guarda cada archivo aplicado con su sha256, y
`benchmark-bancos migrate` aplica solo los pendientes, en orden y uno por uno.

- `sql/00_roles_db.sql` no se aplica desde acá: crea el rol y la base, necesita
  superusuario y se corre una sola vez al instalar (o lo hace docker-compose).
- Una base que ya tenía las migraciones aplicadas por fuera (docker-compose/CI aplican
  todo `sql/` con psql, y las bases anteriores a este cambio) tiene esquema pero el
  registro vacío. Para no adivinar, cada migración reciente declara una SONDA
  (`SONDAS`): una consulta que es verdadera si el efecto de esa migración ya está en la
  base. El "nivel" de la base es la última migración N tal que todas las sondas hasta N
  pasan. Con el registro vacío:
    * si el nivel es la última migración (base al día, el caso de docker-compose/CI),
      `migrate` hace el baseline solo y sigue;
    * si no, se detiene y pide `--baseline`, que marca como aplicadas solo las
      migraciones hasta el nivel verificado; las siguientes quedan pendientes y las
      aplica el `migrate` siguiente.
  Toda migración nueva debe agregar su sonda, salvo las de datos idempotentes listadas
  en `_SIN_SONDA` (lo exige tests/test_orquestacion.py).
- Si un archivo ya aplicado cambió (sha256 distinto), avisa con WARNING y no lo vuelve a
  correr: las migraciones no son re-ejecutables por diseño. Si el cambio fue a propósito
  y no altera el resultado (p. ej. la portabilidad del rol en 2026-10-09),
  `--aceptar-cambios` actualiza el sha256 registrado.
"""

import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path

import psycopg

from benchmark_bancos.config import PROJECT_ROOT

log = logging.getLogger(__name__)

SQL_DIR = PROJECT_ROOT / "sql"
_EXCLUIDAS = {"00_roles_db.sql"}

_MESES_ES = (
    "ARRAY['Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto',"
    "'Septiembre','Octubre','Noviembre','Diciembre']"
)

# archivo -> consulta booleana: verdadera si la base ya tiene el efecto de esa migración
# (y sigue siéndolo después de las siguientes). Solo desde sql/28: una base anterior no
# se puede ubicar con seguridad y hay que revisarla a mano.
SONDAS: dict[str, str] = {
    "28_bce_canton_grain.sql": """SELECT EXISTS (SELECT FROM information_schema.columns
        WHERE table_schema = 'marts' AND table_name = 'fact_colocaciones_cartera'
          AND column_name = 'canton_id')""",
    "29_dim_banco_tipo_segundo_piso.sql": """SELECT EXISTS (SELECT FROM pg_constraint
        WHERE connamespace = 'marts'::regnamespace AND contype = 'c'
          AND pg_get_constraintdef(oid) LIKE '%ENTIDAD DE SEGUNDO PISO%')""",
    "31_staging_natural_key_provincia.sql": """SELECT to_regclass(
        'staging.staging_cartera_natural_key_v2') IS NOT NULL""",
    "33_drop_raw_jsonb_meta_source_files.sql": """SELECT to_regnamespace('raw') IS NULL
        AND to_regclass('meta.source_files') IS NOT NULL""",
    "34_cdc_por_columnas_refresh_incremental.sql": """SELECT
        to_regclass('meta.refresh_watermark') IS NOT NULL
        AND NOT EXISTS (SELECT FROM information_schema.columns
            WHERE table_schema = 'staging' AND column_name = 'row_hash')""",
    "36_codigos_inec.sql": """SELECT EXISTS (SELECT FROM information_schema.columns
        WHERE table_schema = 'marts' AND table_name = 'dim_canton'
          AND column_name = 'codigo_inec')""",
    "37_dim_entidad.sql": "SELECT to_regclass('marts.dim_entidad') IS NOT NULL",
    "38_schema_migrations.sql": (
        "SELECT to_regclass('meta.schema_migrations') IS NOT NULL"
    ),
    "39_vw_conciliacion_saldos_balance.sql": (
        "SELECT to_regclass('marts.vw_conciliacion_resumen') IS NOT NULL"
    ),
    "40_dim_fecha_nombre_mes_es.sql": (
        "SELECT NOT EXISTS (SELECT FROM marts.dim_fecha "
        f"WHERE nombre_mes IS DISTINCT FROM ({_MESES_ES})[mes])"
    ),
    "41_segmento_entidad_homologado.sql": """SELECT EXISTS (
            SELECT FROM marts.dim_segmento_entidad WHERE tipo_segmento = 'NO REPORTA AL BCE')
        AND NOT EXISTS (
            SELECT FROM marts.dim_segmento_entidad WHERE tipo_segmento = 'MUTUALISTAS')""",
}

_DDL_REGISTRO = """
CREATE SCHEMA IF NOT EXISTS meta;
CREATE TABLE IF NOT EXISTS meta.schema_migrations (
    archivo     text PRIMARY KEY,
    sha256      text NOT NULL,
    aplicada_en timestamptz NOT NULL DEFAULT now(),
    modo        text NOT NULL DEFAULT 'aplicada'
                CHECK (modo IN ('aplicada', 'baseline'))
);
"""


class MigracionError(RuntimeError):
    pass


def nivel_verificado(conn: psycopg.Connection, archivos: list[Path]) -> str | None:
    """Última migración N tal que todas las sondas hasta N pasan (None si ni la primera
    pasa). Las sondas se evalúan en orden y se corta en la primera que falla."""
    nivel = None
    with conn.cursor() as cur:
        for p in archivos:
            sonda = SONDAS.get(p.name)
            if sonda is None:
                continue
            try:
                cur.execute(sonda)
                ok = bool(cur.fetchone()[0])
            except psycopg.Error:
                ok = False
            if not ok:
                break
            nivel = p.name
    return nivel


@dataclass
class Estado:
    aplicadas: dict[str, str]  # archivo -> sha256 registrado
    pendientes: list[Path]
    modificadas: list[str]  # aplicadas cuyo archivo cambió después
    esquema_existente: bool


def _sha256(path: Path) -> str:
    # Finales de línea normalizados: git deja los .sql con CRLF en Windows y LF en Linux,
    # y la misma migración no debe verse "cambiada" según desde qué máquina se migre.
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def archivos_migracion(sql_dir: Path = SQL_DIR) -> list[Path]:
    return sorted(p for p in sql_dir.glob("*.sql") if p.name not in _EXCLUIDAS)


def estado(
    conn: psycopg.Connection, sql_dir: Path = SQL_DIR, crear_registro: bool = True
) -> Estado:
    """Con `crear_registro=False` (usado por `--status`) no escribe nada: si el registro
    no existe todavía, lo trata como vacío."""
    with conn.cursor() as cur:
        if crear_registro:
            cur.execute(_DDL_REGISTRO)
        cur.execute("SELECT to_regclass('meta.schema_migrations') IS NOT NULL")
        if cur.fetchone()[0]:
            cur.execute("SELECT archivo, sha256 FROM meta.schema_migrations")
            aplicadas = dict(cur.fetchall())
        else:
            aplicadas = {}
        cur.execute("SELECT to_regclass('meta.source_files') IS NOT NULL")
        esquema_existente = cur.fetchone()[0]
    archivos = archivos_migracion(sql_dir)
    return Estado(
        aplicadas=aplicadas,
        pendientes=[p for p in archivos if p.name not in aplicadas],
        modificadas=[
            p.name
            for p in archivos
            if p.name in aplicadas and aplicadas[p.name] != _sha256(p)
        ],
        esquema_existente=esquema_existente,
    )


def migrar(
    conn: psycopg.Connection,
    sql_dir: Path = SQL_DIR,
    baseline: bool = False,
    solo_estado: bool = False,
    aceptar_cambios: bool = False,
) -> list[str]:
    """Aplica las migraciones pendientes. `conn` debe estar en autocommit: cada archivo
    maneja su propia transacción (varios traen BEGIN/COMMIT o bloques DO). Devuelve los
    nombres aplicados (o marcados, con `baseline`)."""
    if not conn.autocommit:
        raise MigracionError("migrar() necesita una conexión en autocommit")
    est = estado(conn, sql_dir, crear_registro=not solo_estado)
    if aceptar_cambios and est.modificadas:
        with conn.cursor() as cur:
            for nombre in est.modificadas:
                cur.execute(
                    "UPDATE meta.schema_migrations SET sha256 = %s WHERE archivo = %s",
                    (_sha256(sql_dir / nombre), nombre),
                )
        log.info(
            "sha256 actualizado (cambios aceptados, no se re-ejecutan): %s",
            ", ".join(est.modificadas),
        )
        est.modificadas = []
    for nombre in est.modificadas:
        log.warning(
            "Migración ya aplicada cuyo archivo cambió después: %s (no se re-ejecuta; "
            "si el cambio fue a propósito, `migrate --aceptar-cambios`)",
            nombre,
        )

    if solo_estado:
        if not est.aplicadas and est.esquema_existente:
            log.warning(
                "La base tiene esquema pero el registro de migraciones está vacío: "
                "`migrate` pedirá `--baseline` (ver docs/despliegue_y_orquestacion.md §3)"
            )
        log.info(
            "Migraciones: %d aplicadas, %d pendientes%s",
            len(est.aplicadas),
            len(est.pendientes),
            (
                (": " + ", ".join(p.name for p in est.pendientes))
                if est.pendientes
                else ""
            ),
        )
        return []

    if baseline or (not est.aplicadas and est.esquema_existente):
        archivos = archivos_migracion(sql_dir)
        nivel = nivel_verificado(conn, archivos)
        if nivel is None:
            raise MigracionError(
                "No se pudo verificar el nivel de la base: ni la sonda de "
                f"{next(iter(SONDAS))} pasa. Es anterior a 2026-09 o no es una base de "
                "este proyecto; revisarla a mano (docs/despliegue_y_orquestacion.md §3)."
            )
        al_dia = nivel == archivos[-1].name
        if not baseline and not al_dia:
            raise MigracionError(
                "La base ya tiene esquema pero meta.schema_migrations está vacío, y su "
                f"nivel verificado es {nivel} (no la última migración). Correr "
                "`benchmark-bancos migrate --baseline` para registrar hasta ese nivel y "
                "luego `migrate` para aplicar el resto."
            )
        hasta = [p for p in est.pendientes if p.name <= nivel]
        with conn.cursor() as cur:
            for p in hasta:
                cur.execute(
                    "INSERT INTO meta.schema_migrations (archivo, sha256, modo) "
                    "VALUES (%s, %s, 'baseline')",
                    (p.name, _sha256(p)),
                )
        log.info(
            "Baseline%s: %d migraciones registradas sin ejecutarlas (nivel verificado: %s)",
            "" if baseline else " automático (base al día)",
            len(hasta),
            nivel,
        )
        if baseline:
            restantes = [p.name for p in est.pendientes if p.name > nivel]
            if restantes:
                log.info(
                    "Quedan pendientes para el próximo `migrate`: %s",
                    ", ".join(restantes),
                )
            return [p.name for p in hasta]
        est = estado(conn, sql_dir)

    aplicadas = []
    for p in est.pendientes:
        log.info("Aplicando %s", p.name)
        conn.add_notice_handler(_log_notice)
        try:
            with conn.cursor() as cur:
                cur.execute(p.read_text(encoding="utf-8"))
                cur.execute(
                    "INSERT INTO meta.schema_migrations (archivo, sha256) VALUES (%s, %s)",
                    (p.name, _sha256(p)),
                )
        except psycopg.Error as e:
            raise MigracionError(
                f"Falló {p.name}: {e}. Las anteriores quedaron aplicadas y registradas; "
                "corregir y volver a correr `migrate`."
            ) from e
        finally:
            conn.remove_notice_handler(_log_notice)
        aplicadas.append(p.name)
    log.info(
        "Migraciones: %d aplicadas en esta corrida%s",
        len(aplicadas),
        (" (" + ", ".join(aplicadas) + ")") if aplicadas else ", base al día",
    )
    return aplicadas


def _log_notice(diag) -> None:
    # Los "... already exists / does not exist, skipping" de los IF [NOT] EXISTS son
    # ruido esperado; los RAISE NOTICE propios de las migraciones (p. ej. sql/36 pidiendo
    # reprocesar el BCE) sí se muestran.
    mensaje = diag.message_primary or ""
    nivel = logging.DEBUG if mensaje.endswith(", skipping") else logging.INFO
    log.log(nivel, "NOTICE: %s", mensaje)
