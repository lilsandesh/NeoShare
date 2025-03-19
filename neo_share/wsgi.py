"""
WSGI config for neo_share project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.1/howto/deployment/wsgi/
"""

import os  # Import os module for environment variable management

from django.core.wsgi import get_wsgi_application  # Import function to get the WSGI application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'neo_share.settings')  # Set default settings module if not already set
# Ensures DJANGO_SETTINGS_MODULE is 'neo_share.settings' in the environment

application = get_wsgi_application()  # Create the WSGI application callable
# 'application' is the entry point for WSGI servers (e.g., Gunicorn) to handle HTTP requests