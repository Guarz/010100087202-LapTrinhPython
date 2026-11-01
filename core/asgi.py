"""
ASGI config for core project.

Django phục vụ toàn bộ website; FastAPI (API phụ trợ) được gắn tại /api/v2.
Chạy: uvicorn core.asgi:application

For more information on this file, see
https://docs.djangoproject.com/en/6.1/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

django_application = get_asgi_application()

try:
    from fastapi import FastAPI
    from planner.fastapi_app import api
except ImportError:  # FastAPI là tùy chọn
    application = django_application
else:
    application = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    application.mount('/api/v2', api)
    application.mount('/', django_application)
