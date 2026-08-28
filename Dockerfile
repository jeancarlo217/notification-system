FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# The SQLite file lives on a volume mounted at /data (foundation section 8).
RUN useradd --create-home app && mkdir -p /data && chown app:app /data
USER app

EXPOSE 8000
CMD ["gunicorn", "deadliner.wsgi", "--bind", "0.0.0.0:8000"]
