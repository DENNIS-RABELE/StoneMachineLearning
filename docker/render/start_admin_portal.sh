#!/bin/sh
set -eu

if [ "${BOOTSTRAP_RENDER_DATABASES:-0}" = "1" ]; then
  python docker/render/bootstrap_postgres.py
fi
if [ "${RUN_DB_MIGRATIONS:-1}" = "1" ]; then
  python manage.py migrate --noinput
fi
if [ "${RUN_COLLECTSTATIC:-1}" = "1" ]; then
  python manage.py collectstatic --noinput
fi
exec gunicorn admin_portal.wsgi:application --bind 0.0.0.0:${PORT:-10000} --workers ${WEB_CONCURRENCY:-1} --timeout ${GUNICORN_TIMEOUT:-120}
