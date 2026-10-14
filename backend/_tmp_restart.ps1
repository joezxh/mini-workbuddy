$ErrorActionPreference = "SilentlyContinue"

# 结束占用 8000 的进程
$pids = (netstat -ano -p tcp | Select-String ':8000\s' ) -replace '\s+', ' ' | ForEach-Object { ($_ -split ' ')[-1] } | Sort-Object -Unique
foreach ($p in $pids) {
    if ($p -match '^\d+$') {
        Write-Host "kill $p"
        taskkill /PID $p /F | Out-Null
    }
}
Start-Sleep -Seconds 2

$dir = 'd:\projects\MinWorkBuddy\backend'
$py = Join-Path $dir '.venv\Scripts\python.exe'
$out = 'd:\projects\MinWorkBuddy\logs\_tmp_backend.log'
$err = 'd:\projects\MinWorkBuddy\logs\_tmp_backend.err.log'
Remove-Item $out, $err -ErrorAction SilentlyContinue

Start-Process -FilePath $py `
  -ArgumentList '-m', 'uvicorn', 'app.main:app', '--host', '0.0.0.0', '--port', '8000' `
  -WorkingDirectory $dir -WindowStyle Hidden `
  -RedirectStandardOutput $out -RedirectStandardError $err

Write-Host "restarted"
