# Multi-stage build for React frontend
# syntax=docker/dockerfile:1
FROM --platform=linux/amd64 node:20-alpine as builder

WORKDIR /app

# Build-time arguments — pass with --build-arg when running docker build.
# Cloud Build substitutes these from the cloudbuild.yaml substitutions block.
ARG VITE_API_BASE_URL
ARG VITE_GOOGLE_MAPS_API_KEY
ARG GEMINI_API_KEY

# Expose args as env vars so Vite picks them up during build
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
ENV VITE_GOOGLE_MAPS_API_KEY=$VITE_GOOGLE_MAPS_API_KEY
ENV GEMINI_API_KEY=$GEMINI_API_KEY

# Copy package files
COPY package*.json ./

# Install dependencies (including dev dependencies for build)
RUN npm install

# Copy source code
COPY . .

# Build the application
RUN npm run build

# Production stage with nginx
FROM --platform=linux/amd64 nginx:alpine

# nginx.conf has `listen ${PORT};` — we substitute that ONE token at start
# time via envsubst (whitelisted so nginx-native variables like $uri are
# left untouched). Templated config is staged at a non-conf.d path so it
# doesn't get parsed before substitution.
COPY nginx.conf /etc/nginx/templates/default.conf.template

# Copy built files from builder
COPY --from=builder /app/dist /usr/share/nginx/html

# Cloud Run sets PORT at runtime; default to 8080 for local docker run.
ENV PORT=8080
EXPOSE 8080

# Health check — must use the same $PORT.
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget --quiet --tries=1 --spider "http://127.0.0.1:${PORT}/health" || exit 1

# Substitute ${PORT} into the nginx config, then exec nginx in the foreground.
# `envsubst '$PORT'` whitelist prevents accidental substitution of $uri etc.
CMD sh -c "envsubst '\$PORT' < /etc/nginx/templates/default.conf.template > /etc/nginx/conf.d/default.conf && exec nginx -g 'daemon off;'"
