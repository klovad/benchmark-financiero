# Registra (o reemplaza) la tarea programada de Windows que corre scripts\actualizar.ps1.
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\registrar_tarea.ps1 [-Dia Monday] [-Hora 07:30]
#
# - Semanal: el BCE publica tsp/tsa cada semana; CAPCOL, Boletín, SEPS y TasasHistorico son
#   mensuales y se recogen en la corrida siguiente a su publicación (las descargas son
#   condicionales o no recargan lo ya cargado, así que correr seguido es barato).
# - Corre con el usuario actual y solo cuando la sesión está iniciada (no guarda
#   contraseña). Si la PC estaba apagada a la hora programada, corre al encenderla.
# - Para quitarla: Unregister-ScheduledTask -TaskName 'benchmark-bancos actualizar'

param(
    [string]$Dia = 'Monday',
    [string]$Hora = '07:30'
)

$ErrorActionPreference = 'Stop'
$script = Join-Path $PSScriptRoot 'actualizar.ps1'
$raiz = Split-Path -Parent $PSScriptRoot

$accion = New-ScheduledTaskAction -Execute 'powershell.exe' `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$script`"" `
    -WorkingDirectory $raiz
$disparador = New-ScheduledTaskTrigger -Weekly -DaysOfWeek $Dia -At $Hora
$ajustes = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopIfGoingOnBatteries `
    -AllowStartIfOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 3) `
    -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName 'benchmark-bancos actualizar' `
    -Description 'Actualización incremental semanal de benchmark-bancos (BCE, CAPCOL, Boletín, TasasHistorico, SEPS). Log en logs\.' `
    -Action $accion -Trigger $disparador -Settings $ajustes -Force | Out-Null

Get-ScheduledTask -TaskName 'benchmark-bancos actualizar' |
    Select-Object TaskName, State, @{n = 'Proxima'; e = { ($_ | Get-ScheduledTaskInfo).NextRunTime } }
