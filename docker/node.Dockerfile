# syntax=docker/dockerfile:1.7
FROM node:20-bookworm-slim

ARG SERVICE_DIR

ENV NODE_ENV=production

WORKDIR /app

COPY ${SERVICE_DIR}/package*.json ./
RUN if [ -f package-lock.json ]; then npm ci --omit=dev --no-audit --no-fund; else npm install --omit=dev --no-audit --no-fund; fi

COPY ${SERVICE_DIR}/ ./

CMD ["npm", "start"]
