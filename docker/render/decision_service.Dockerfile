FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIPENV_VENV_IN_PROJECT=0

WORKDIR /app

RUN pip install --no-cache-dir pipenv

COPY serverside/microservices/decision_service/Pipfile serverside/microservices/decision_service/Pipfile.lock ./
RUN pipenv install --system --deploy

COPY serverside/microservices/decision_service/ ./
COPY serverside/microservices/odds_generator_service/ /odds_generator_service/
COPY serverside/microservices/unity_gameplay_service/ /unity_gameplay_service/
COPY docker/render/ /app/docker/render/

RUN chmod +x /app/docker/render/start_decision_service.sh /app/docker/render/start_decision_worker.sh /app/docker/render/start_decision_beat.sh

CMD ["sh", "/app/docker/render/start_decision_service.sh"]
