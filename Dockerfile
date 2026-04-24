FROM python:3.11-slim

WORKDIR /app

RUN groupadd -r appgroup && useradd -r -g appgroup -d /app -s /sbin/nologin appuser

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY start.py ./start.py

RUN mkdir -p /data/snapshots \
    && chown -R appuser:appgroup /app /data

USER appuser

EXPOSE 8000

CMD ["python", "/app/start.py"]
