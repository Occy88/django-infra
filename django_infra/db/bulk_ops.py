import time

from django.db import connection
from django.db import models as dm


def bulk_update_queryset(
    *,
    qs: dm.QuerySet,
    annotation_field_pairs: list[tuple[str, str]],
    batch_size=100_000,
):
    """Updates queryset fields based on annotations in bulk using postgres set.
    This is helpful for situations that require batching as subquery updates
    do not allow this.
    Examples:
        >>> bulk_update_queryset(qs=qs,annotation_field_pairs=[('_my_field',
        >>> 'my_field'),('_my_custom_annotation','my_other_field')])
    """
    qs = qs.order_by(qs.model._meta.pk.name)
    model = qs.model
    pk_name = model._meta.pk.name
    total = qs.count()
    start_time = time.time()
    updated = 0

    annotation_keys = [ann for ann, field in annotation_field_pairs]

    while updated < total:
        batch_start = time.time()
        batch_qs = qs[updated : updated + batch_size].values(pk_name, *annotation_keys)
        compiler = batch_qs.query.get_compiler(using="default")
        sub_sql, sub_params = compiler.as_sql()
        set_clause = ", ".join(
            f"{field} = sub.{ann}" for ann, field in annotation_field_pairs
        )
        sql = (
            f"UPDATE {model._meta.db_table} AS t SET {set_clause} "
            f"FROM ({sub_sql}) AS sub "
            f"WHERE t.{pk_name} = sub.{pk_name}"
        )
        with connection.cursor() as cursor:
            cursor.execute(sql, sub_params)
        updated += batch_size
        batch_elapsed = time.time() - batch_start
        elapsed = time.time() - start_time
        print(
            f"Updated ({min(updated, total)/total*100:.2f}%) - rate {updated/elapsed:.2f}/s - batch {batch_elapsed:.2f}s time: {elapsed:.2f}s"
        )


# def annotate_defaults(qs, model_cls, provided_fields):
#     defaults = {}
#     for field in model_cls._meta.fields:
#         if field.name in provided_fields:
#             continue
#         if not field.null:
#             if getattr(field, "auto_now", False) or getattr(
#                 field, "auto_now_add", False
#             ):
#                 defaults["_" + field.name] = dm.functions.Now()
#             elif field.default is not dm.fields.NOT_PROVIDED:
#                 default = field.default() if callable(field.default) else field.default
#                 defaults["_" + field.name] = dm.Value(default, output_field=field)
#     if defaults:
#         qs = qs.annotate(**defaults)
#     return qs, list(defaults.keys())
#
#
# def bulk_create_from_annotations(model_cls, qsfrom, fto, ffrom, batch_size=100_000):
#     """avg 20674.36 rows/s"""
#     # Create annotation keys with '_' prefix to avoid field conflicts.
#     provided_anns = ["_" + field for field in fto]
#     mapping = {ann: dm.F(src) for ann, src in zip(provided_anns, ffrom)}
#     qs = qsfrom.annotate(**mapping)
#
#     qs, default_anns = annotate_defaults(qs, model_cls, provided_fields=fto)
#     all_anns = provided_anns + default_anns
#     target_cols = fto + [ann[1:] for ann in default_anns]
#
#     qs = qs.values(*all_anns)
#     total = qsfrom.count()
#     start_time = time.time()
#     inserted = 0
#     elapsed = start_time
#     while inserted < total:
#         batch_start_time = time.time()
#         batch_qs = qs[inserted : inserted + batch_size]
#         compiler = batch_qs.query.get_compiler(using="default")
#         sub_sql, sub_params = compiler.as_sql()
#         sql = (
#             f"INSERT INTO {model_cls._meta.db_table} ({', '.join(target_cols)}) "
#             f"SELECT {', '.join(all_anns)} FROM ({sub_sql}) AS sub"
#         )
#         with connection.cursor() as cursor:
#             cursor.execute(sql, sub_params)
#         inserted += batch_size
#         batch_time = time.time() - batch_start_time
#         elapsed = time.time() - start_time
#         print(
#             f"Inserted ({(inserted / total) * 100:.2f}%) - rate {inserted/elapsed:.2f}/s - batch {batch_time} time: {elapsed:.2f}s "
#         )
