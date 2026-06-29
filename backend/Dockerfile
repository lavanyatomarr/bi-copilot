FROM python:3.12-slim

WORKDIR /app

# No apt-get needed: psycopg2-binary ships precompiled wheels, so no compiler required.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]