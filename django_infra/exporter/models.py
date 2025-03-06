import dataclasses
import time
from functools import cached_property

from django.db import models
from django.db.models import TextChoices

from django_infra.db.models import UpdatableModel


class QueryExportManager(models.Manager): ...


class ExportState(TextChoices):
    SCHEDULED = "scheduled", "Scheduled"
    PROCESSING = "processing", "Processing"
    SUCCESS = "success", "Success"
    FAIL = "fail", "Fail"


@dataclasses.dataclass
class ExportMetadata:
    start_time: float = dataclasses.field(default_factory=time.time)
    file_size: int = 0
    job_time: float = 0.0
    progress_percent: int = 0
    row_count: int = 0
    error_log: str = ""

    def update_progress(self, processed: int, total: int):
        self.row_count = processed
        self.progress_percent = int(processed * 100 / total) if total else 0

    def finalize(self, file_size: int, processed: int):
        self.job_time = time.time() - self.start_time
        self.file_size = file_size
        self.row_count = processed
        self.progress_percent = 100

    @property
    def data(self) -> dict:
        return dataclasses.asdict(self)


class QueryExport(UpdatableModel):

    id = models.CharField(
        max_length=64,
        unique=True,
        primary_key=True,
    )
    state = models.CharField(max_length=16, choices=ExportState.choices)

    metadata = models.JSONField()

    file = models.FileField()
    format = models.CharField(
        max_length=16,
    )
    # Assign the custom manager
    objects = QueryExportManager()

    @cached_property
    def export_metadata(self) -> ExportMetadata:
        return ExportMetadata(**self.metadata)
