# Requer admin. Fecha o AIDA64, monta a tela unica (layout original + player) e reabre.
Stop-Process -Name aida64 -Force -ErrorAction SilentlyContinue
Start-Sleep 3
& 'C:\Python314\python.exe' "$PSScriptRoot\patch_layout.py"
$dev = (Get-PnpDevice -PresentOnly | Where-Object InstanceId -like 'USB\VID_1908&PID_0102*').InstanceId
if ($dev) { pnputil /restart-device $dev | Out-Null; Start-Sleep 4 }
schtasks /run /tn 'AIDA64 AutoStart' | Out-Null
