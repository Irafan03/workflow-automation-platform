# ─────────────────────────────────────────────────────────────
# Stage dev : Vite dev server avec hot-reload
# ─────────────────────────────────────────────────────────────
FROM node:20-alpine AS dev

WORKDIR /app

ENV NODE_ENV=development

# Installe les dépendances en exploitant le cache Docker
COPY package.json package-lock.json ./
RUN npm ci

# Copie le code source
COPY . .

EXPOSE 3000

HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=3 \
    CMD wget -qO- http://localhost:3000 || exit 1

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]

# ─────────────────────────────────────────────────────────────
# Stage build : construit l'artefact de production
# ─────────────────────────────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

# ─────────────────────────────────────────────────────────────
# Stage prod : nginx sert les fichiers statiques
# ─────────────────────────────────────────────────────────────
FROM nginx:1.27-alpine AS prod

COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
