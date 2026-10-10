# Requer admin. Fecha o AIDA64, reinicia o USB do AX206 e reabre o AIDA64.
Stop-Process -Name aida64 -Force -ErrorAction SilentlyContinue
Start-Sleep 3
$dev = (Get-PnpDevice -PresentOnly | Where-Object InstanceId -like 'USB\VID_1908&PID_0102*').InstanceId
if ($dev) { pnputil /restart-device $dev | Out-Null; Start-Sleep 4 }
schtasks /run /tn 'AIDA64 AutoStart' | Out-Null
