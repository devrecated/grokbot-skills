# Build context: examples/ (see compose.yaml)
FROM node:20-slim AS build
WORKDIR /app/deploy-ssh
COPY deploy-ssh/package.json deploy-ssh/tsconfig.json ./
RUN npm install
COPY package.json worker.ts /app/
COPY deploy-ssh/server.ts ./
RUN npm run build

FROM node:20-slim
WORKDIR /app
COPY --from=build /app/deploy-ssh/dist ./dist
COPY --from=build /app/package.json ./dist/package.json
ENV NODE_ENV=production
USER node
CMD ["node", "dist/deploy-ssh/server.js"]
