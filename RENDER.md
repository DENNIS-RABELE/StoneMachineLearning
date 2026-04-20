# Render Deployment

This repo can now be deployed to Render with the included [`render.yaml`](./render.yaml) Blueprint.

## What It Deploys

- `stoney-admin-portal`
- `stoney-bettor-service`
- `stoney-decision-service`
- `stoney-decision-worker`
- `stoney-decision-beat`
- `stoney-client-gateway`
- managed Postgres: `stoney-postgres`
- managed Key Value: `stoney-redis`

## Important Architecture Note

The app uses multiple logical PostgreSQL databases:

- `ADMINPORTAL`
- `DECISIONAPP`
- `UNITYGAMEPLAY`
- `BETTORS`
- `BETTORANALYTICS`
- `CLIENTBETDATA`
- `ODDSGENERATOR`
- `DEMOMONEY`

Render provisions a single managed Postgres instance in this setup. On startup, the Python services run [`docker/render/bootstrap_postgres.py`](./docker/render/bootstrap_postgres.py) to create those logical databases inside that instance if they do not already exist.

## Deploy Steps

1. Push this repo to GitHub.
2. In Render, create a new Blueprint and point it at the repo.
3. Render will read `render.yaml` and propose the services.
4. Fill in all env vars marked with `sync: false`, especially:
   - `SECRET_KEY`
   - `SSO_SECRET`
   - `SSO_CANONICAL_HOST`
   - `CLIENT_GATEWAY_PUBLIC_URL`
   - `CORS_ORIGIN` if you need cross-origin browser access
5. Deploy the Blueprint.

## Assumptions

- Render Blueprint supports `fromDatabase` properties for `host`, `port`, `user`, `password`, and `database`.
- Render Blueprint supports `fromService` properties such as `hostport` and `connectionString`.
- Render Key Value is used as the Redis-compatible backend.
- `decision_service` is served with `daphne` because it exposes websocket behavior through ASGI.
- Celery worker and Celery beat are deployed as separate Render worker services.
- The deployed round duration default is `200` seconds (`3 minutes 20 seconds`).

## First Things To Check After Deploy

1. Open the admin portal service URL first.
2. Confirm both `stoney-decision-worker` and `stoney-decision-beat` are healthy.
3. Open the client gateway URL and test:
   - registration/login
   - live game endpoints
   - stats/dashboard pages
4. If a service cannot reach another service, confirm the generated private-network `hostport` values in Blueprint env vars.
