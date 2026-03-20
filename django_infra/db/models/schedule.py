from __future__ import annotations

import abc
import datetime
import logging
from functools import partial
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from django_infra.db.querysets.schedule import ScheduleQuerySet

import pytz
from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import DateTimeRangeField, RangeOperators
from django.contrib.postgres.indexes import GistIndex
from django.db import models as dm
from django.db.models import TextChoices
from django.db.models.expressions import BaseExpression, Case, Ref, Value, When
from django.db.models.lookups import Exact, In

logger = logging.getLogger(__name__)


class ScheduleCode(TextChoices):
    # date is between start date (inclusive) and end date (exclusive)
    ACTIVE = "ACTIVE", "Active"
    # date is before start date
    FUTURE = "FUTURE", "Inactive Pre"
    # date is after end date
    EXPIRED = "EXPIRED", "Inactive Post"


class LookupOverrideMixin:
    lookup_overrides: dict[str, type] = {}

    def get_lookup(self, lookup_name):
        lookup = self.lookup_overrides.get(lookup_name)
        if lookup is not None:
            return lookup
        return super().get_lookup(lookup_name)

    @classmethod
    def unwrap_lhs(cls, lhs):
        if isinstance(lhs, cls):
            return lhs
        if isinstance(lhs, Ref) and isinstance(lhs.source, cls):
            return lhs.source
        return None

    @staticmethod
    def extract_rhs_values(rhs):
        if hasattr(rhs, "value"):
            values = rhs.value
            if isinstance(values, (list, tuple, set)):
                return list(values)
            return [values]
        if isinstance(rhs, (list, tuple, set)):
            return list(rhs)
        if not isinstance(rhs, BaseExpression):
            return [rhs]
        logger.info(
            "ScheduleCodeCase: rhs values unavailable (type=%s)", type(rhs).__name__
        )
        return None


class ScheduleCodeCase(LookupOverrideMixin, Case):
    """
    Custom Case expression for ScheduleCode that optimizes WHERE clause filtering.

    When used in SELECT (annotation), it returns the normal CASE expression.
    When used in WHERE (filtering), it converts to efficient date comparisons.
    """

    class Exact(Exact):
        def as_sql(self, compiler, connection):
            expr = ScheduleCodeCase.unwrap_lhs(self.lhs)
            if expr is None:
                logger.info(
                    "ScheduleCodeCase.Exact: not selected (lhs not ScheduleCodeCase)"
                )
                return super().as_sql(compiler, connection)
            values = ScheduleCodeCase.extract_rhs_values(self.rhs)
            if not values:
                logger.info(
                    "ScheduleCodeCase.Exact: not selected (rhs values unavailable)"
                )
                return super().as_sql(compiler, connection)
            q = expr.build_q(values[0])
            if not q:
                logger.info(
                    "ScheduleCodeCase.Exact: not selected (empty Q for %r)", values[0]
                )
                return super().as_sql(compiler, connection)
            where = q.resolve_expression(
                compiler.query, allow_joins=True, reuse=None, summarize=False
            )
            logger.info("ScheduleCodeCase.Exact: selected (optimized)")
            return compiler.compile(where)

    class In(In):
        def as_sql(self, compiler, connection):
            expr = ScheduleCodeCase.unwrap_lhs(self.lhs)
            if expr is None:
                logger.info(
                    "ScheduleCodeCase.In: not selected (lhs not ScheduleCodeCase)"
                )
                return super().as_sql(compiler, connection)
            values = ScheduleCodeCase.extract_rhs_values(self.rhs)
            if not values:
                logger.info(
                    "ScheduleCodeCase.In: not selected (rhs values unavailable)"
                )
                return super().as_sql(compiler, connection)
            combined_q = dm.Q()
            for value in values:
                q = expr.build_q(value)
                if q:
                    combined_q |= q
            if not combined_q:
                logger.info(
                    "ScheduleCodeCase.In: not selected (empty Q for %r)", values
                )
                return super().as_sql(compiler, connection)
            where = combined_q.resolve_expression(
                compiler.query, allow_joins=True, reuse=None, summarize=False
            )
            logger.info("ScheduleCodeCase.In: selected (optimized)")
            return compiler.compile(where)

    lookup_overrides = {"exact": Exact, "in": In}

    def __init__(
        self,
        *args,
        start_ref: str = "start_date",
        end_ref: str = "end_date",
        current_date=None,
        **kwargs,
    ):
        from django.utils import timezone

        current_date = current_date or timezone.now()
        self.start_ref = start_ref
        self.end_ref = end_ref
        self.current_date = current_date

        if not args:
            args = (
                When(
                    dm.Q(**{f"{start_ref}__lte": current_date})
                    & dm.Q(**{f"{end_ref}__gt": current_date}),
                    then=Value(ScheduleCode.ACTIVE.value),
                ),
                When(
                    **{f"{start_ref}__gt": current_date},
                    then=Value(ScheduleCode.FUTURE.value),
                ),
            )
            kwargs.setdefault("default", Value(ScheduleCode.EXPIRED.value))

        kwargs.setdefault("output_field", dm.CharField())
        super().__init__(*args, **kwargs)

    def build_q(self, code_value):
        """Build Q object for a given schedule code value."""
        if code_value == ScheduleCode.ACTIVE.value:
            # start_date <= current_date < end_date
            return dm.Q(**{f"{self.start_ref}__lte": self.current_date}) & dm.Q(
                **{f"{self.end_ref}__gt": self.current_date}
            )
        if code_value == ScheduleCode.FUTURE.value:
            # start_date > current_date
            return dm.Q(**{f"{self.start_ref}__gt": self.current_date})
        if code_value == ScheduleCode.EXPIRED.value:
            # end_date <= current_date
            return dm.Q(**{f"{self.end_ref}__lte": self.current_date})
        # Unknown code, return empty Q
        return dm.Q()


MIN_DATE = datetime.datetime(1900, 1, 1, tzinfo=pytz.UTC)
MAX_DATE = datetime.datetime(9000, 1, 1, tzinfo=pytz.UTC)


def nest_field(*, ref: str, field_name: str):
    ref = f"{ref}__" if ref else ""
    ref = f"{ref}{field_name}"
    return ref


nest_start_date = partial(nest_field, field_name="start_date")
nest_end_date = partial(nest_field, field_name="end_date")
nest_period = partial(nest_field, field_name="period")


class ScheduleMixin(dm.Model):
    """Base mixin for models with start_date and end_date scheduling fields."""

    start_date = dm.DateTimeField(null=True, db_index=True)
    end_date = dm.DateTimeField(null=True, db_index=True)

    @property
    @abc.abstractmethod
    def objects(self) -> "ScheduleQuerySet":
        return NotImplemented

    @staticmethod
    def get_constraint_end_time_gt_start_time():
        return dm.CheckConstraint(
            condition=dm.Q(end_date__gt=dm.F("start_date")),
            name="%(class)s_end_after_start",
        )

    class Meta:
        abstract = True
        ordering = ["start_date", "end_date"]


class PeriodScheduleMixin(ScheduleMixin):
    """Extended schedule mixin that includes a generated period field for overlap detection."""

    period = dm.GeneratedField(
        expression=dm.Func(
            dm.F("start_date"),
            dm.F("end_date"),
            dm.Value("[)"),  # lower-inclusive / upper-exclusive
            function="tstzrange",
        ),
        output_field=DateTimeRangeField(),
        db_persist=True,  # materialised (required on Postgres)
        editable=False,
    )
    overlap_constraint_fields: tuple[str, ...] = ()

    @staticmethod
    def get_constraint_no_period_overlap_on_fields(field_names: list[str] = None):
        field_names = field_names or []
        return ExclusionConstraint(
            name="%(class)s_no_overlap_" + "_".join(field_names),
            expressions=[
                *[(f, "=") for f in field_names],
                ("period", RangeOperators.OVERLAPS),
            ],
            deferrable=dm.Deferrable.DEFERRED,
        )

    @staticmethod
    def get_default_indexes(
        prefix_fields: list[str] | None = None, class_name_abbr: str | None = None
    ) -> list[dm.Index]:
        """
        Return the 'standard' indexes for temporal-membership tables with period field.

        * `prefix_fields` - equality columns evaluated before the range test.
        * `class_name_abbr` - optional abbreviated class name for index names (to stay within 30-char limit)
        """
        prefix_fields = prefix_fields or []
        name_template = class_name_abbr if class_name_abbr else "%(class)s"

        #  Multi-column GiST on (<prefix ...>, period)
        gist_idx = GistIndex(
            fields=[*prefix_fields, "period"],
            name=f"{name_template}_gist_" + "_".join(prefix_fields + ["period"]),
        )

        # B-tree on upper(period) for 'ending soon' queries
        upper_idx = dm.Index(
            dm.Func(dm.F("period"), function="upper"),
            name=f"{name_template}_idx_period_upper",
        )

        # B-tree on lower(period) for expired lookups
        lower_idx = dm.Index(
            dm.Func(dm.F("period"), function="lower"),
            name=f"{name_template}_idx_period_lower",
        )

        return [gist_idx, upper_idx, lower_idx]

    class Meta:
        abstract = True
        ordering = ["start_date", "end_date"]
