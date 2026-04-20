#!/bin/sh
set -eu

if [ "${BOOTSTRAP_RENDER_DATABASES:-0}" = "1" ]; then
  python docker/render/bootstrap_postgres.py
fi
if [ "${RUN_DB_MIGRATIONS:-1}" = "1" ]; then
  python manage.py migrate --noinput
  python manage.py migrate --noinput --database=odds
  python manage.py migrate --noinput --database=unity
fi
if [ "${RUN_COLLECTSTATIC:-1}" = "1" ]; then
  python manage.py collectstatic --noinput
fi
exec daphne -b 0.0.0.0 -p ${PORT:-10000} decision_service.asgi:application
