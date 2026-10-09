"""Migraciones de esquema con registro de lo aplicado (2026-10-09).

Antes no había forma de saber qué `sql/NN_*.sql` tenía aplicada una base, y volver a
correr todo `sql/` sobre una base con datos los borra (varias migraciones hacen TRUNCATE).
Ahora `meta.schema_migrations` guarda cada archivo aplicado con su sha256, y
`benchmark-bancos migrate` aplica solo los pendientes, en orden y uno por uno.

- `sql/00_roles_db.sql` no se aplica desde acá: crea el rol y la base, necesita
  superusuario y se corre una sola vez al instalar (o lo hace docker-compose).
- Una base que ya tenía las migraciones aplicadas por fuera (docker-compose/CI aplican
  todo `sql/` con psql, y las bases anteriores a este cambio) tiene esquema pero el
  registro vacío: `migrate` se niega a adivinar y pide `--baseline`, que marca como
  aplicados todos los archivos actuales sin ejecutarlos.
- Si un archivo ya aplicado cambió (sha256 distinto), avisa con WARNING y no lo vuelve a
  correr: las migraciones no son re-ejecutables por diseño.
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


@dataclass
class Estado:
    aplicadas: dict[str, str]  # archivo -> sha256 registrado
    pendientes: list[Path]
    modificadas: list[str]  # aplicadas cuyo archivo cambió después
    esquema_existente: bool


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
) -> list[str]:
    """Aplica las migraciones pendientes. `conn` debe estar en autocommit: cada archivo
    maneja su propia transacción (varios traen BEGIN/COMMIT o bloques DO). Devuelve los
    nombres aplicados (o marcados, con `baseline`)."""
    if not conn.autocommit:
        raise MigracionError("migrar() necesita una conexión en autocommit")
    est = estado(conn, sql_dir, crear_registro=not solo_estado)
    for nombre in est.modificadas:
        log.warning(
            "Migración ya aplicada cuyo archivo cambió después: %s (no se re-ejecuta)",
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

    if baseline:
        with conn.cursor() as cur:
            for p in est.pendientes:
                cur.execute(
                    "INSERT INTO meta.schema_migrations (archivo, sha256, modo) "
                    "VALUES (%s, %s, 'baseline')",
                    (p.name, _sha256(p)),
                )
        log.info(
            "Baseline: %d migraciones marcadas como aplicadas sin ejecutarlas",
            len(est.pendientes),
        )
        return [p.name for p in est.pendientes]

    if not est.aplicadas and est.esquema_existente:
        raise MigracionError(
            "La base ya tiene esquema pero meta.schema_migrations está vacío (migraciones "
            "aplicadas por fuera, p. ej. docker-compose o una base anterior a este "
            "registro). Si la base está al día con sql/, correr "
            "`benchmark-bancos migrate --baseline`; si no, aplicar a mano lo que falte "
            "primero."
        )

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
