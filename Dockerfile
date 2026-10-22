FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /app

RUN groupadd --gid 10001 eku \
    && useradd --uid 10001 --gid eku --create-home --shell /usr/sbin/nologin eku
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY --chown=eku:eku . .
RUN mkdir -p /app/.private/uploads /app/staticfiles \
    && chown -R eku:eku /app/.private /app/staticfiles \
    && chmod 700 /app/.private /app/.private/uploads
USER eku
RUN DJANGO_ENV=development python manage.py collectstatic --noinput

CMD ["sh", "-c", "python manage.py migrate --noinput && gunicorn config.wsgi:application --config deploy/gunicorn.conf.py"]
