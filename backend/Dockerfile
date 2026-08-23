# Pin the base-image manifest for reproducible production builds. Update it
# only through the documented, tested image refresh procedure.
FROM python:3.13-slim@sha256:ffb752e139c0a19692a43af8d8523b274222dd68eebad5d583b45c2201c6e30a

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin appuser
COPY alembic.ini ./
COPY migrations ./migrations
COPY app ./app
RUN chown -R appuser:appuser /app
USER appuser
EXPOSE 8000
CMD ["sh", "-c", "python -m app.cli db wait --timeout 60 && python -m app.cli db upgrade && uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-access-log"]
