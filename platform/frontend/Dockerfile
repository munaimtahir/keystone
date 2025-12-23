# Keystone Frontend - React UI
FROM node:20-alpine AS build

WORKDIR /app

# Build arguments for API base URL
ARG VITE_API_BASE=
ENV VITE_API_BASE=$VITE_API_BASE

# Install dependencies
COPY package*.json ./
RUN npm install

# Copy source and build
COPY . .
RUN npm run build

# Production image with nginx
FROM nginx:1.27-alpine

# Copy nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy built files
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
