#!/bin/sh

# Exit immediately if a command exits with a non-zero status
set -e

# Wait for database availability
python wait_for_db.py

echo "Applying database migrations..."
python manage.py makemigrations accounts profiles
python manage.py migrate

echo "Collecting static files..."
python manage.py collectstatic --no-input

# Execute the main command
exec "$@"
