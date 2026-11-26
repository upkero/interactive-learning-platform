FROM node:22-bookworm AS build
WORKDIR /app
RUN corepack enable && corepack prepare pnpm@9.15.9 --activate
COPY pnpm-workspace.yaml pnpm-lock.yaml ./
COPY primitives/package.json primitives/package.json
COPY widget-host/package.json widget-host/package.json
RUN pnpm install --frozen-lockfile
COPY primitives/src primitives/src
COPY widget-host widget-host
RUN pnpm --filter widget-host build

FROM nginx:1.27-alpine
COPY --from=build /app/widget-host/dist /usr/share/nginx/html
COPY widget-host/nginx.conf /etc/nginx/conf.d/default.conf
