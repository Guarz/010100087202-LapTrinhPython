release: python manage.py migrate --no-input
web: uvicorn core.asgi:application --host 0.0.0.0 --port $PORT
worker: celery -A core worker -B -l info
