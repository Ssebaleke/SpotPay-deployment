FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    cron \
  && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY . /app

# Create a wrapper that exports env vars before running manage.py
RUN echo '#!/bin/sh' > /usr/local/bin/django-cron && \
    echo 'export $(cat /proc/1/environ | tr "\0" "\n" | grep -v "^$")' >> /usr/local/bin/django-cron && \
    echo 'cd /app && exec /usr/local/bin/python3 manage.py "$@"' >> /usr/local/bin/django-cron && \
    chmod +x /usr/local/bin/django-cron

EXPOSE 8000

CMD ["gunicorn", "Billing.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "120"]
