# Pin both build and runtime manifests; see docs/operations.md before updating.
FROM node:22-alpine@sha256:c610fcdfb1d5b4740dd70c284ed3cb16bb857e0f7166196e36a5501df7a3aa32 AS build
ARG VITE_AUTH_REQUIRED=false
ARG VITE_API_URL=http://127.0.0.1:8000/api/v1
ENV VITE_AUTH_REQUIRED=${VITE_AUTH_REQUIRED}
ENV VITE_API_URL=${VITE_API_URL}
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY tsconfig.json vite.config.ts index.html ./
COPY src ./src
RUN npm run build

FROM nginx:1.27-alpine@sha256:65645c7bb6a0661892a8b03b89d0743208a18dd2f3f17a54ef4b76fb8e2f2a10
ARG NGINX_CONF=nginx.conf
COPY nginx.base.conf /etc/nginx/nginx.conf
COPY ${NGINX_CONF} /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
