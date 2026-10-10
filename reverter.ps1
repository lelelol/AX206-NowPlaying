# Requer admin. Restaura o preset original do AIDA64 (backup de 2026-10-10) e reabre.
$b = "$env:USERPROFILE\Documents\AIDA64-backup-AX206-2026-10-10"
$d = 'C:\Program Files\FinalWire\AIDA64 Business'
Stop-Process -Name aida64 -Force -ErrorAction SilentlyContinue
Start-Sleep 3
Copy-Item "$b\aida64.ini", "$b\aida64.customvars.ini" $d -Force
$dev = (Get-PnpDevice -PresentOnly | Where-Object InstanceId -like 'USB\VID_1908&PID_0102*').InstanceId
if ($dev) { pnputil /restart-device $dev | Out-Null; Start-Sleep 4 }
schtasks /run /tn 'AIDA64 AutoStart' | Out-Null
"Preset original restaurado."
