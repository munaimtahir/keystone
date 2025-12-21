FROM node:20-alpine AS build
ARG VITE_API_BASE=/keystone
ARG VITE_BASE=/
ENV VITE_API_BASE=$VITE_API_BASE
ENV VITE_BASE=$VITE_BASE
WORKDIR /src
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /src/dist/ /usr/share/nginx/html/
EXPOSE 80
