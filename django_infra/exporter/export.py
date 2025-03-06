import csv
import datetime
import io
import os

from django.core.files.storage import FileSystemStorage, default_storage
from django.db.models import QuerySet
from django.utils.crypto import get_random_string

from django_infra.exporter.models import ExportMetadata, ExportState, QueryExport

EXPORT_BATCH_SIZE = 10_000


def generate_export_id(qs: QuerySet) -> str:
    cls_name = qs.model.__name__
    now = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    unique_component = get_random_string(6)
    return f"{cls_name}-{now}-{unique_component}"


def handle_csv(fields, rows, file_obj):
    if not hasattr(file_obj, "encoding"):
        file_obj = io.TextIOWrapper(file_obj, encoding="utf-8", newline="")
    writer = csv.writer(file_obj)
    writer.writerow(fields)
    for row in rows:
        writer.writerow(row)
    file_obj.flush()


def export_queryset(qs: QuerySet, values: list, file_path: str = None) -> QueryExport:
    export_id = generate_export_id(qs)
    file_path = file_path or f"exports/{export_id}.csv"
    ext = os.path.splitext(file_path)[1].lower().lstrip(".")
    if not ext:
        raise ValueError("File extension missing")
    if default_storage.exists(file_path):
        raise ValueError("File already exists")

    export = QueryExport.objects.create(
        id=export_id,
        state=ExportState.SCHEDULED,
        metadata=ExportMetadata().data,
        format=ext,
    )
    try:
        export.update(state=ExportState.PROCESSING)
        total = qs.count()
        processed = 0

        def row_generator():
            nonlocal processed
            for row in qs.values_list(*values).iterator(chunk_size=EXPORT_BATCH_SIZE):
                processed += 1
                yield row
                if processed % EXPORT_BATCH_SIZE == 0 and total:
                    export.export_metadata.update_progress(processed, total)
                    export.update(metadata=export.export_metadata.data)

        handler = {"csv": handle_csv}.get(ext)
        if handler is None:
            raise ValueError("Unsupported format")

        if isinstance(default_storage, FileSystemStorage):
            os.makedirs(os.path.dirname(file_path), exist_ok=True)

        with default_storage.open(file_path, "wb") as f:
            handler(values, row_generator(), f)

        file_size = default_storage.size(file_path)
        export.export_metadata.finalize(file_size, processed)
        export.update(state=ExportState.SUCCESS, metadata=export.export_metadata.data)
    except Exception as e:
        export.export_metadata.error_log = str(e)
        export.update(state=ExportState.FAIL, metadata=export.export_metadata.data)
        raise
    return export
