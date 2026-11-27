FROM node:22-alpine AS build
WORKDIR /app
RUN npm install --global --no-audit --no-fund pnpm@9.15.9

COPY pnpm-workspace.yaml pnpm-lock.yaml ./
COPY frontend/package.json frontend/package.json
COPY primitives/package.json primitives/package.json
RUN pnpm --filter grasp-frontend... install --frozen-lockfile

COPY frontend frontend
COPY primitives/src primitives/src

ARG API_INTERNAL_URL=http://api:8000
ENV API_INTERNAL_URL=${API_INTERNAL_URL}
ENV NEXT_TELEMETRY_DISABLED=1
RUN mkdir -p frontend/public && NEXT_STANDALONE=1 pnpm --filter grasp-frontend build

FROM node:22-alpine AS runtime
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV HOSTNAME=0.0.0.0
ENV PORT=3000

COPY --from=build --chown=node:node /app/frontend/.next/standalone ./
COPY --from=build --chown=node:node /app/frontend/.next/static ./frontend/.next/static
COPY --from=build --chown=node:node /app/frontend/public ./frontend/public

USER node
EXPOSE 3000
CMD ["node", "frontend/server.js"]
