FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN addgroup --system bidsentry && adduser --system --ingroup bidsentry --no-create-home bidsentry
WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY bidsentry/ ./bidsentry/
COPY web/ ./web/
COPY config/ ./config/
COPY data/ ./data/
COPY langflow/ ./langflow/
COPY bob/ ./bob/
COPY index.html server.py .env.example ./

# Audit log, session secret and job database live in one writable volume.
RUN mkdir -p /app/var && chown -R bidsentry:bidsentry /app/var
ENV AUDIT_LOG_PATH=/app/var/audit_log.jsonl
VOLUME ["/app/var"]
USER bidsentry

# A container must listen on 0.0.0.0 to be reachable through port mapping. On a
# non-loopback host the server refuses to start without BIDSENTRY_ACCESS_TOKEN and
# refuses role logins without PINs, so run it like this:
#   docker run -p 8000:8000 -v bidsentry-data:/app/var \
#     -e BIDSENTRY_ACCESS_TOKEN=<random> -e BIDSENTRY_POKJA_PIN=<pin> -e BIDSENTRY_VENDOR_PIN=<pin> \
#     -e BIDSENTRY_SESSION_SECRET=<random> bidsentry
ENV HOST=0.0.0.0
ENV PORT=8000
ENV LANGFLOW_URL=http://host.docker.internal:7860
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health')" || exit 1
ENTRYPOINT ["python", "server.py"]
