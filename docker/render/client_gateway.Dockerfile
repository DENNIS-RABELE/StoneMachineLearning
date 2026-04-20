FROM node:20-bookworm-slim

ENV NODE_ENV=production

WORKDIR /app

COPY clientside/package*.json ./
RUN if [ -f package-lock.json ]; then npm ci --omit=dev --no-audit --no-fund; else npm install --omit=dev --no-audit --no-fund; fi

COPY clientside/ ./

CMD ["npm", "start"]
