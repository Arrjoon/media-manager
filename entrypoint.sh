#!/bin/sh
while ! nc -z db 5432; do
  echo "Waiting for postgres..."
  sleep 1
done
echo "Running migrations..."


python manage.py migrate


echo "Starting Django server..."
python manage.py runserver 0.0.0.0:8000
echo "Postgres is up - executing command"