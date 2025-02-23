import os
import uuid

import pytest
from django.core.files.storage import default_storage
from django.db import models as dm
from model_bakery import baker

from django_infra.exporter.export import export_queryset
from tests.test_exporter.models import ExportRelatedTestModel, ExportTestModel


@pytest.fixture
def export_temp_file():
    # Create a temporary CSV file name using NamedTemporaryFile
    file_name=os.path.join(os.path.dirname(__file__),f"{uuid.uuid4()}.csv")
    try:
        yield file_name
    finally:
        try:
            os.remove(file_name)
        except OSError:
            pass
@pytest.fixture
def export_data_factory(db):
    def create_records(num=1, field1="test_value", related_value="related_value"):
        relateds = baker.make(ExportRelatedTestModel, field2=related_value, _quantity=num)
        models_created = baker.make(ExportTestModel, field1=field1, _quantity=num)
        for model, related in zip(models_created, relateds):
            model.related_model = related
            model.save()
    return create_records

def test_export_with_annotated_related_field(export_data_factory, export_temp_file):
    export_data_factory(num=1)
    qs = ExportTestModel.objects.annotate(annotated_field=dm.F("related_model__field2"))
    values = ["field1", "annotated_field"]
    export_obj = export_queryset(qs, values, file_path=export_temp_file)
    assert export_obj.state.lower() == "success"
    with default_storage.open(export_temp_file, "rb") as f:
        content = f.read().decode("utf-8")
        assert "field1" in content
        assert "annotated_field" in content
        assert "test_value" in content
        assert "related_value" in content

def test_export_batching_progress(export_data_factory, export_temp_file, monkeypatch):
    record_count = 10
    export_data_factory(num=record_count)
    qs = ExportTestModel.objects.all()
    values = ["field1"]
    # Force batching by setting a low batch size.
    monkeypatch.setattr("django_infra.exporter.export.EXPORT_BATCH_SIZE", 5)
    export_obj = export_queryset(qs, values, file_path=export_temp_file)
    export_obj.refresh_from_db()

    assert export_obj.export_metadata.row_count == record_count
    assert export_obj.state.lower() == "success"

def test_export_file_exists_failure(export_data_factory, export_temp_file):
    export_data_factory(num=1)
    qs = ExportTestModel.objects.all()
    values = ["field1"]
    # First export creates the file.
    export_queryset(qs, values, file_path=export_temp_file)
    # Second export should fail.
    with pytest.raises(ValueError, match="File already exists"):
        export_queryset(qs, values, file_path=export_temp_file)

def test_export_unsupported_format(export_data_factory):
    export_data_factory(num=1)
    qs = ExportTestModel.objects.all()
    values = ["field1"]
    with pytest.raises(ValueError, match="File extension missing"):
        export_queryset(qs, values, file_path="export")
    with pytest.raises(ValueError, match="Unsupported format"):
        export_queryset(qs, values, file_path="export.txt")

def test_export_failure_during_processing(monkeypatch, export_data_factory, export_temp_file):
    def failing_handle_csv(fields, rows, file_obj):
        raise Exception("Simulated processing error")
    monkeypatch.setattr("django_infra.exporter.export.handle_csv", failing_handle_csv)
    export_data_factory(num=1)
    qs = ExportTestModel.objects.all()
    values = ["field1"]
    with pytest.raises(Exception, match="Simulated processing error"):
        export_queryset(qs, values, file_path=export_temp_file)
