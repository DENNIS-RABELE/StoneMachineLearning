Get-ChildItem -Directory | Where-Object { $_.Name -in @("admin_portal", "bettor_service", "decision_service") } | ForEach-Object {

    $servicePath = $_.FullName
    $manageFile = Join-Path $servicePath "manage.py"

    if (Test-Path $manageFile) {

        Write-Host "Initializing $($_.Name)..."

        Set-Location $servicePath

        pipenv install psycopg[binary] redis celery djangorestframework drf-spectacular "channels[daphne]" channels-redis PyJWT httpx

        # Run migrations for all configured databases (merged-service setup).
        pipenv run python manage.py migrate --noinput

        if ($_.Name -eq "bettor_service") {
            pipenv run python manage.py migrate --noinput --database=demomoney
            pipenv run python manage.py migrate --noinput --database=betdata
            pipenv run python manage.py migrate --noinput --database=analytics
        }

        if ($_.Name -eq "decision_service") {
            pipenv run python manage.py migrate --noinput --database=odds
            pipenv run python manage.py migrate --noinput --database=unity
        }

        Set-Location ..
    }
}
