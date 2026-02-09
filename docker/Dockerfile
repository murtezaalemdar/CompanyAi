# Kurumsal AI Asistanı - Dockerfile

FROM python:3.11-slim

# Çalışma dizini
WORKDIR /app

# Sistem bağımlılıkları
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Python bağımlılıkları
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Uygulama kodları
COPY app/ ./app/

# Environment
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Port
EXPOSE 8000

# Başlatma komutu
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
