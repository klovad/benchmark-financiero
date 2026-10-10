-- dim_fecha.nombre_mes en español sin depender del servidor (2026-10-09).
--
-- refresh_marts() llenaba nombre_mes con TO_CHAR(fecha, 'TMMonth'), que usa el lc_time
-- del servidor: en un Postgres en inglés (p. ej. la imagen postgres:17 estándar o un
-- servicio gestionado) salía 'January'. Desde esta fecha load_postgres.py usa una lista fija
-- en español. Esta migración corrige las filas ya cargadas en servidores con otro idioma;
-- en uno en español no cambia nada.

UPDATE marts.dim_fecha
SET nombre_mes = (ARRAY['Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio',
                        'Agosto','Septiembre','Octubre','Noviembre','Diciembre'])[mes]
WHERE nombre_mes IS DISTINCT FROM
      (ARRAY['Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio',
             'Agosto','Septiembre','Octubre','Noviembre','Diciembre'])[mes];
