"""
Development settings for br_tracker.
Use: DJANGO_SETTINGS_MODULE=br_tracker.settings.dev
"""
from .base import *
from decouple import config

DEBUG = True
ALLOWED_HOSTS = ['*']  # Termux needs * for 0.0.0.0

# Disable HTTPS redirect in dev - Termux doesn't have SSL
SECURE_SSL_REDIRECT = False

# Django Debug Toolbar - only in dev
INSTALLED_APPS += ['debug_toolbar']
MIDDLEWARE = ['debug_toolbar.middleware.DebugToolbarMiddleware'] + MIDDLEWARE
INTERNAL_IPS = ['127.0.0.1', 'localhost']

# Email to console in dev
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Show all SQL queries in dev
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {'class': 'logging.StreamHandler'},
    },
    'loggers': {
        'django.db.backends': {
            'handlers': ['console'],
            'level': 'DEBUG',
        },
    },
}
