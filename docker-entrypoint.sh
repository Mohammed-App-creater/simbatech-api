#!/bin/sh
# Waits for the database, applies migrations, seeds the catalog, then serves the API.
set -e

until python manage.py migrate --noinput; do
  echo "Database not ready yet, retrying in 3s..."
  sleep 3
done

python manage.py seed --if-empty
python manage.py collectstatic --noinput >/dev/null

if [ "${DEBUG:-1}" = "1" ]; then
  exec python manage.py runserver 0.0.0.0:8000
else
  exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers "${WEB_CONCURRENCY:-3}"
fi
