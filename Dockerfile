FROM python:3.11-slim

WORKDIR /app

RUN groupadd -r -g 1000 appgroup && useradd -r -u 1000 -g appgroup -d /app -s /sbin/nologin appuser

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY start.py ./start.py

RUN chown -R appuser:appgroup /app

# Create snapshot directory — will be overlaid by bind mount at runtime
RUN mkdir -p /data/snapshots && touch /data/symbol_overrides.json && chown -R appuser:appgroup /data

EXPOSE 8000

USER appuser

CMD ["python", "/app/start.py"]
