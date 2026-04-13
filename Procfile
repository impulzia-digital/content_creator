web: gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 3 --timeout 120
worker: celery -A config worker -l info -Q default,generation,publishing -c 2
beat: celery -A config beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
