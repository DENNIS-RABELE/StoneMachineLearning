# Docker Setup

This repo now runs locally as a smaller Docker Compose stack that matches the current architecture:

- `postgres`
- `redis`
- `admin_portal`
- `bettor_service`
- `decision_service`
- `decision_worker`
- `decision_beat`
- `client_gateway`

## Architecture Notes

- `client_gateway` is the monolithic Node client service.
- `admin_portal` is a standalone Django service.
- `bettor_service` includes the merged bettor apps, analytics app, and bet-data app.
- `decision_service` includes the merged decision apps, odds generator app, and unity gameplay app.
- `decision_worker` runs Celery worker tasks for `decision_service`.
- `decision_beat` runs Celery beat for `decision_service`.

## First Run

From repo root:

```powershell
Copy-Item .env.docker.example .env -Force
docker compose down -v --remove-orphans
docker compose up --build
```

For detached mode:

```powershell
docker compose up --build -d
```

## Lightweight Dev Stack

The dev compose file now mirrors the same service layout:

```powershell
docker compose -f docker-compose.dev.yml up --build
```

## Main Endpoints

- Admin portal: `http://localhost:9006`
- Bettor service: `http://localhost:9002`
- Decision service: `http://localhost:9000`
- Client gateway: `http://localhost:3000`

## Common Commands

Start:

```powershell
docker compose up --build
```

Detached:

```powershell
docker compose up --build -d
```

Logs:

```powershell
docker compose logs -f
```

Focused logs:

```powershell
docker compose logs -f admin_portal bettor_service decision_service decision_worker decision_beat client_gateway
```

List containers:

```powershell
docker compose ps
```

Stop:

```powershell
docker compose down
```

Reset database state:

```powershell
docker compose down -v
```

## Notes

- Postgres still initializes all required logical databases from `docker/postgres/init/01-create-databases.sql`.
- `bettor_service` runs migrations for:
  - default
  - `demomoney`
  - `betdata`
  - `analytics`
- `decision_service` runs migrations for:
  - default
  - `odds`
  - `unity`
- `decision_service` uses `daphne` because it exposes ASGI/websocket behavior.
- The current round duration default in Docker is `200` seconds (`3 minutes 20 seconds`).
