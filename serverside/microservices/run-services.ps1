$servicePorts = @{
    "decision_service" = 9000
    "bettor_service" = 9002
    "admin_portal" = 9006
}

Get-ChildItem -Directory | Where-Object { $_.Name -in @("admin_portal", "bettor_service", "decision_service") } | ForEach-Object {
    $servicePath = $_.FullName
    $manageFile = Join-Path $servicePath "manage.py"

    if (Test-Path $manageFile) {
        $serviceName = $_.Name
        $port = $servicePorts[$serviceName]
        if (-not $port) {
            $port = 8000
        }

        Write-Host "Starting $serviceName on port $port..."

        Start-Process powershell -ArgumentList "-NoExit -Command cd '$servicePath'; pipenv run python manage.py runserver 127.0.0.1:$port"
    }
}
