FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
RUN useradd --create-home --uid 10001 app && mkdir -p /data/uploads && chown app:app /data/uploads
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY alembic.ini docker-entrypoint.sh ./
# Windows checkouts may turn LF into CRLF, which breaks shell scripts: normalise, and don't rely on the exec bit.
RUN sed -i 's/\r$//' docker-entrypoint.sh
COPY app ./app
COPY migrations ./migrations
ENV ENVIRONMENT=production UPLOAD_DIR=/data/uploads
USER app
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=5 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/ready',timeout=4).status==200 else 1)"
ENTRYPOINT ["sh", "./docker-entrypoint.sh"]
