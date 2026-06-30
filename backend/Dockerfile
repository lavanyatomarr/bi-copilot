FROM python:3.12-slim

WORKDIR /app

# libpq-dev + gcc are needed to build psycopg2 (the Postgres driver)
RUN apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
# --reload restarts the server automatically when you edit code (dev convenience)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
