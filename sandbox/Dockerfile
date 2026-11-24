FROM node:22-bookworm AS build
WORKDIR /app
RUN corepack enable && corepack prepare pnpm@9.15.9 --activate
COPY pnpm-workspace.yaml pnpm-lock.yaml ./
COPY primitives/package.json primitives/package.json
COPY widget-host/package.json widget-host/package.json
COPY sandbox/package.json sandbox/package.json
RUN pnpm install --frozen-lockfile
COPY primitives/src primitives/src
COPY widget-host widget-host
COPY sandbox sandbox
RUN pnpm --filter widget-host build && pnpm --filter sandbox build

# Keep the browser package and the image on exactly the same Playwright release.
FROM mcr.microsoft.com/playwright:v1.65.0-noble
WORKDIR /app
COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/sandbox/node_modules ./sandbox/node_modules
COPY --from=build /app/sandbox/dist ./sandbox/dist
COPY --from=build /app/sandbox/package.json ./sandbox/package.json
COPY --from=build /app/widget-host/dist ./widget-host/dist
COPY --from=build /app/primitives ./primitives
ENV NODE_ENV=production HOME=/tmp
USER pwuser
EXPOSE 3001
CMD ["node", "sandbox/dist/main.js"]
