FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# The configuration boundary validates the whole environment before any management command runs,
# so collectstatic needs a complete one. These values are throwaways for a command that reads no
# business value and writes no URL into what it collects; the runtime environment is the real one.
RUN DJANGO_SECRET_KEY=build-time-placeholder \
    DJANGO_ALLOWED_HOSTS=127.0.0.1 \
    DEADLINER_ALERT_THRESHOLDS=30,7,0 \
    DEADLINER_WHATSAPP_NUMBER=550000000000 \
    DEADLINER_MESSAGE_TEMPLATE="{client}" \
    DEADLINER_SECRET_PATH_SEGMENT=build-time-placeholder \
    DEADLINER_TIMEZONE=UTC \
    python manage.py collectstatic --noinput

# The SQLite file lives on a volume mounted at /data (foundation section 8).
RUN useradd --create-home app && mkdir -p /data && chown app:app /data
USER app

EXPOSE 8000
CMD ["gunicorn", "deadliner.wsgi", "--bind", "0.0.0.0:8000"]
