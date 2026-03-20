from __future__ import annotations

import datetime

from django.contrib.postgres.fields import DateTimeRangeField
from django.db import models as dm
from django.db.models.expressions import RawSQL
from django.utils import timezone

from django_infra.db.models.schedule import (
    ScheduleCodeCase,
    nest_end_date,
    nest_period,
    nest_start_date,
)


class ScheduleQuerySet(dm.QuerySet):
    def filter(self, *args, **kwargs) -> ScheduleQuerySet:
        return super().filter(*args, **kwargs)

    @staticmethod
    def annotate_period(*, qs, start_ref="start_date", end_ref="end_date", to="period"):
        """
        Annotate the queryset with a `tstzrange` built from `start_ref` -> `end_ref`.
        If the start timestamp is after the end timestamp, return an *empty* range
        instead of letting Postgres raise an error.
        """

        range_expr = dm.Func(
            dm.F(start_ref),
            dm.F(end_ref),
            dm.Value("[)"),  # inclusive lower, exclusive upper
            function="tstzrange",
            output_field=DateTimeRangeField(),
        )

        empty_range = RawSQL(
            "%s::tstzrange",
            params=["empty"],
            output_field=DateTimeRangeField(),
        )

        annotated_range = dm.Case(
            dm.When(**{f"{start_ref}__lte": dm.F(end_ref)}, then=range_expr),
            default=empty_range,
        )

        return qs.annotate(**{to: annotated_range})

    @staticmethod
    def annotate_within_schedule(
        *,
        qs,
        date_time=None,
        schedule_ref: str = "",
        annotation_name="within_schedule",
    ):
        current_date = date_time or timezone.now()

        # Use start_date and end_date directly (faster than period field)
        start_ref = nest_start_date(ref=schedule_ref)
        end_ref = nest_end_date(ref=schedule_ref)

        # Use custom ScheduleCodeCase that optimizes filtering
        code_case = ScheduleCodeCase(
            start_ref=start_ref,
            end_ref=end_ref,
            current_date=current_date,
        )

        return qs.annotate(
            **{
                f"{annotation_name}_code": code_case,
                annotation_name: dm.ExpressionWrapper(
                    dm.Q(**{f"{start_ref}__lte": current_date})
                    & dm.Q(**{f"{end_ref}__gt": current_date}),
                    output_field=dm.BooleanField(),
                ),
            }
        )

    def with_within_schedule(self, date_time=None, annotation_name="within_schedule"):
        """Annotate self with a parameter stating if date is within schedule range."""
        return self.annotate_within_schedule(
            qs=self, date_time=date_time, annotation_name=annotation_name
        )


class PeriodScheduleQuerySet(ScheduleQuerySet):
    """Extended queryset for models with period field, adding overlap detection methods."""

    @staticmethod
    def annotate_has_overlap(*, qs, schedule_ref: str = "", partition_by: str = ""):
        period_ref = nest_period(ref=schedule_ref)

        subquery = qs.filter(
            ~dm.Q(pk=dm.OuterRef("pk")),
            **{f"{period_ref}__overlap": dm.OuterRef(period_ref)},
        )
        if partition_by:
            subquery = subquery.filter(**{partition_by: dm.OuterRef(partition_by)})

        return qs.annotate(has_overlap=dm.Exists(subquery))

    def with_has_overlap(self):
        return PeriodScheduleQuerySet.annotate_has_overlap(qs=self)

    @staticmethod
    def annotate_range_has_overlap(
        *,
        qs,
        start: str | datetime.datetime,
        end: str | datetime.datetime,
        schedule_ref: str = "",
        annotation_name: str = "range_has_overlap",
    ):
        period_ref = nest_period(ref=schedule_ref)
        overlap_key = f"{period_ref}__overlap"

        return qs.annotate(
            **{
                annotation_name: dm.Case(
                    dm.When(**{overlap_key: (start, end)}, then=dm.Value(True)),
                    default=dm.Value(False),
                    output_field=dm.BooleanField(),
                )
            }
        )

    def with_range_has_overlap(
        self, start: str | datetime.datetime, end: str | datetime.datetime
    ):
        """Annotate self with a parameter stating if date is within schedule range."""
        return self.annotate_range_has_overlap(qs=self, start=start, end=end)
