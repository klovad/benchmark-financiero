# Actualización incremental programada (Windows). Uso:
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\actualizar.ps1 [-Fuentes bce,seps]
#
# Corre `benchmark-bancos actualizar` desde la raíz del proyecto, deja el log de la corrida
# en logs\actualizar_AAAAMMDD_HHMMSS.log (UTF-8), borra logs de más de 90 días y termina
# con el mismo código que el CLI: 0 OK, 1 error que cortó la corrida, 2 terminó con
# errores (ver log), 75 había otra corrida en curso. Pensado para el Programador de
# tareas: registrar con scripts\registrar_tarea.ps1 (ver docs/despliegue_y_orquestacion.md §7).

param(
    [string[]]$Fuentes = @()
)

$ErrorActionPreference = 'Stop'
$raiz = Split-Path -Parent $PSScriptRoot
Set-Location $raiz
$env:PYTHONUTF8 = '1'

$uv = (Get-Command uv -ErrorAction SilentlyContinue).Source
if (-not $uv) { $uv = Join-Path $env:USERPROFILE '.local\bin\uv.exe' }
if (-not (Test-Path $uv)) { Write-Error "No se encontró uv (ni en PATH ni en $uv)"; exit 1 }

$logs = Join-Path $raiz 'logs'
New-Item -ItemType Directory -Force $logs | Out-Null
$log = Join-Path $logs ("actualizar_{0}.log" -f (Get-Date -Format 'yyyyMMdd_HHmmss'))

$argumentos = @('run', '--no-sync', 'benchmark-bancos', 'actualizar', '--log-file', $log)
if ($Fuentes.Count -gt 0) { $argumentos += @('--fuentes') + $Fuentes }

# El log va a $log; la consola se descarta. Con 'Stop', PowerShell 5.1 convierte cada
# línea que el ejecutable escribe en stderr (ahí va el logging) en un error y corta el
# script con código 1 aunque la corrida haya terminado bien.
$ErrorActionPreference = 'Continue'
& $uv @argumentos *> $null
$codigo = $LASTEXITCODE
$ErrorActionPreference = 'Stop'

Get-ChildItem $logs -Filter 'actualizar_*.log' |
    Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-90) } |
    Remove-Item -Force

exit $codigo
