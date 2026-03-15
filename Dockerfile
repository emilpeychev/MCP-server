FROM python:3.11-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1
COPY app/requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt
RUN apt-get update && \
    apt-get install -y curl ca-certificates && \
    curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash && \
    groupadd -r appuser && useradd -r -g appuser appuser && \
    mkdir -p /app/data && chown appuser:appuser /app/data && \
    rm -rf /var/lib/apt/lists/*
COPY --chown=appuser:appuser app/ ./app
USER appuser
EXPOSE 8081
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8081", "--log-level", "info"]