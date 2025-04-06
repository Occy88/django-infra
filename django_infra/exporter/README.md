# Django Infra: Exporter (generic annotated queryset export)

## Overview

The `django-infra/exporter` app provides a reusable Django component for efficiently exporting potentially large annotated querysets to downloadable files (currently CSV). It tracks the export process, stores metadata (progress, timings, errors), and offers an API and Django Admin integration for monitoring.

## Features

*   **Efficient Queryset Export:** Handles large datasets by iterating through the queryset in chunks, minimizing memory usage.
*   **Status Tracking:** Exports progress through distinct states: `Scheduled`, `Processing`, `Success`, `Fail`.
*   **Metadata Storage:** Records start time, job duration, file size, row count, progress percentage, and any errors encountered during the export.
*   **File Storage Integration:** Uses Django's default file storage backend to save the exported files.
*   **CSV Format Support:** Currently supports exporting data to CSV files. (Extensible for other formats).
*   **API Endpoints:** Provides RESTful API endpoints (list, retrieve) for managing and monitoring exports using Django REST Framework. Includes filtering capabilities.
*   **Django Admin Integration:** Allows viewing and filtering export records directly from the Django Admin interface.
*   **Unique Export IDs:** Generates unique, informative IDs for each export job.

## Requirements

*   Python (Check `django-infra` compatibility, likely 3.8+)
*   Django (Check `django-infra` compatibility, likely 3.2+)
*   Django REST Framework
*   Other `django-infra` core components (e.g., `django_infra.db.models.UpdatableModel`, `django_infra.api`)

## Installation

1.  **Ensure `django-infra` is installed** or included in your project. If it's a package:
    ```bash
    pip install django-infra # Or the specific package name if different
    ```
2.  **Add `django_infra.exporter` to your `INSTALLED_APPS`** in your Django project's `settings.py`:
    ```python
    # settings.py
    INSTALLED_APPS = [
        # ... other apps
        'rest_framework',
        'django_infra.exporter',
        # ... other apps
    ]
    ```
3.  **Include the exporter's API URLs** in your project's `urls.py`:
    ```python
    # urls.py
    from django.urls import path, include

    urlpatterns = [
        # ... other urls
        path('api/exports/', include('django_infra.exporter.urls', namespace='exporter')),
        # ... other urls (like admin)
    ]
    ```
    *Note: You can choose any path prefix instead of `api/exports/`.*
4.  **Run Django migrations** to create the necessary database tables:
    ```bash
    python manage.py makemigrations exporter
    python manage.py migrate
    ```

## Configuration

*   **File Storage:** The exporter uses Django's `DEFAULT_FILE_STORAGE` setting. Ensure your storage backend (e.g., `FileSystemStorage`, S3 Boto3 Storage) is configured correctly in `settings.py`. The exported files will be saved relative to your `MEDIA_ROOT` (for `FileSystemStorage`) or in your configured bucket/location for cloud storage.
    ```python
    # settings.py (Example using default FileSystemStorage)
    MEDIA_URL = '/media/'
    MEDIA_ROOT = BASE_DIR / 'media' # Or your preferred location

    DEFAULT_FILE_STORAGE = 'django.core.files.storage.FileSystemStorage'
    ```

## Usage

### 1. Triggering an Export

Exports are initiated by calling the `export_queryset` function, typically from within a Django view, management command, or background task.

```python
# Example: In a Django view or task
from django.contrib.auth.models import User
from django_infra.exporter.export import export_queryset

def trigger_user_export(request):
    # 1. Define your queryset
    queryset = User.objects.filter(is_active=True).annotate(my_field=Value(True))

    # 2. Specify the fields (database column names) you want to export
    fields_to_export = ['id', 'username', 'email', 'first_name', 'last_name', 'date_joined','my_field']

    # 3. (Optional) Define a custom file path within your storage
    # If None, it defaults to 'exports/{ModelName}-{Timestamp}-{Random}.csv'
    # file_path = f"custom/user_exports/{timezone.now().strftime('%Y%m%d')}.csv"

    try:
        # 4. Call the export function
        # IMPORTANT: This runs SYNCHRONOUSLY. Run it in a background task (Celery, RQ, etc.)
        # for any non-trivial export to avoid blocking your web server process.
        export_job = export_queryset(qs=queryset, values=fields_to_export) # file_path=file_path

        # 5. You get back the QueryExport model instance
        print(f"Export {export_job.id} scheduled/processing.")
        # You might redirect the user or return the ID for status checking

    except ValueError as e:
        # Handle errors like duplicate file path or unsupported format
        print(f"Error starting export: {e}")
    except Exception as e:
        # Handle other potential errors during the export process
        # Note: export_queryset internally logs errors to the QueryExport metadata
        print(f"An unexpected error occurred: {e}")

    # ... return response ...
