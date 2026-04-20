FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIPENV_VENV_IN_PROJECT=0

WORKDIR /app

RUN pip install --no-cache-dir pipenv

COPY serverside/microservices/admin_portal/Pipfile serverside/microservices/admin_portal/Pipfile.lock ./
RUN pipenv install --system --deploy

COPY serverside/microservices/admin_portal/ ./
COPY docker/render/ /app/docker/render/

RUN chmod +x /app/docker/render/start_admin_portal.sh

CMD ["sh", "/app/docker/render/start_admin_portal.sh"]
