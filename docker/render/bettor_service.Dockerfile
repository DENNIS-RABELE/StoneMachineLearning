FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIPENV_VENV_IN_PROJECT=0

WORKDIR /app

RUN pip install --no-cache-dir pipenv

COPY serverside/microservices/bettor_service/Pipfile serverside/microservices/bettor_service/Pipfile.lock ./
RUN pipenv install --system --deploy

COPY serverside/microservices/bettor_service/ ./
COPY serverside/microservices/bettor_analytics_service/ /bettor_analytics_service/
COPY serverside/microservices/bettors_bet_data_service/ /bettors_bet_data_service/
COPY docker/render/ /app/docker/render/

RUN chmod +x /app/docker/render/start_bettor_service.sh

CMD ["sh", "/app/docker/render/start_bettor_service.sh"]
