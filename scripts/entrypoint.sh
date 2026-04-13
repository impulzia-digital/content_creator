#!/bin/bash
set -e

echo "⏳ Waiting for PostgreSQL..."
while ! pg_isready -h "${DB_HOST:-db}" -p "${DB_PORT:-5432}" -U "${DB_USER:-postgres}" -q 2>/dev/null; do
    sleep 1
done
echo "✅ PostgreSQL ready."

echo "🔄 Running migrations..."
python manage.py migrate --noinput

if [ "$SERVICE_ROLE" = "web" ]; then
    echo "📦 Collecting static files..."
    python manage.py collectstatic --noinput
fi

echo "🚀 Starting: $@"
exec "$@"
