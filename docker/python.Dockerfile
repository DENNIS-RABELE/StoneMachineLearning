# syntax=docker/dockerfile:1.7
FROM python:3.14-slim

ARG SERVICE_DIR

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIPENV_VENV_IN_PROJECT=0

WORKDIR /app

RUN pip install --no-cache-dir pipenv

COPY ${SERVICE_DIR}/Pipfile ${SERVICE_DIR}/Pipfile.lock ./
RUN pipenv install --system --deploy

COPY ${SERVICE_DIR}/ ./

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
