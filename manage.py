#!/usr/bin/env python  # Shebang line to use the system's Python interpreter
"""Django's command-line utility for administrative tasks."""
import os  # Import os module for environment variable management
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "neo_share.settings")  # Set default settings module if not already set
# Ensures DJANGO_SETTINGS_MODULE is 'neo_share.settings' before imports
import sys  # Import sys module for command-line arguments


def main():  # Define the main function to run administrative tasks
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'neo_share.settings')  # Set settings module again (redundant but ensures consistency)
    try:  # Begin try block to import Django management tools
        from django.core.management import execute_from_command_line  # Import function to execute Django commands
    except ImportError as exc:  # Catch ImportError if Django isn’t available
        raise ImportError(  # Raise a detailed ImportError with troubleshooting tips
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc  # Chain the original exception for debugging
    execute_from_command_line(sys.argv)  # Execute Django command-line tasks with provided arguments
    # sys.argv contains command-line arguments (e.g., ['manage.py', 'runserver'])


if __name__ == '__main__':  # Check if the script is run directly (not imported)
    main()  # Call the main function to start the utility