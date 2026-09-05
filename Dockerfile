FROM node:18-alpine AS frontend-build
WORKDIR /app/frontend
COPY src/frontend/package*.json ./
RUN npm install
COPY src/frontend/ .
RUN npm run build

FROM python:3.11-slim
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

COPY src/backend/requirements.txt ./requirements.txt
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY src/backend ./src/backend
COPY --from=frontend-build /app/frontend/dist ./src/backend/static

WORKDIR /app/src/backend
EXPOSE 8000

CMD ["sh", "-c", "python main.py init-db && exec python main.py"]
