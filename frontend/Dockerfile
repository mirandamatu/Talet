FROM node:20-alpine AS build

WORKDIR /app
COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

FROM nginx:1.27-alpine

RUN apk add --no-cache gettext

COPY nginx.conf.template /etc/nginx/templates/default.conf.template
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN sed -i 's/\r$//' /docker-entrypoint.sh /etc/nginx/templates/default.conf.template \
    && chmod +x /docker-entrypoint.sh

COPY --from=build /app/dist /usr/share/nginx/html

ENV BACKEND_PROXY_BASE=http://backend:8000
ENV BACKEND_PROXY_HOST=backend:8000

EXPOSE 80
ENTRYPOINT ["/bin/sh", "/docker-entrypoint.sh"]
