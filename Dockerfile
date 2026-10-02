FROM python:3.11-slim

# Match the host user that owns mounted ~/.kube and ~/.aws (default 1000) so read-only mounts are readable.
ARG APP_UID=1000
ARG APP_GID=1000

WORKDIR /app
ENV PYTHONUNBUFFERED=1
COPY app/requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir awscli
# Graphify CLI: powers the graphify_* MCP tools (query/path/explain against graphify-out/graph.json).
RUN pip install --no-cache-dir graphifyy==0.9.73
RUN apt-get update && \
    apt-get install -y curl ca-certificates && \
    curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash && \
    curl -fsSL -o /usr/local/bin/kubectl "https://dl.k8s.io/release/$(curl -fsSL https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl" && \
    chmod +x /usr/local/bin/kubectl && \
    groupadd -g ${APP_GID} appuser && useradd -u ${APP_UID} -g appuser -m -d /home/appuser appuser && \
    mkdir -p /app/data /home/appuser/.kube && \
    chown -R appuser:appuser /app/data /home/appuser && \
    rm -rf /var/lib/apt/lists/*
COPY --chown=appuser:appuser app/ ./app
USER appuser
EXPOSE 8081
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8081", "--log-level", "info"]