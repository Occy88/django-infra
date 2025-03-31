import logging
import time

from django.db import connection


def bulk_update_queryset(*, qs, annotation_field_pairs, batch_size=100_000):
    """
    Updates queryset fields based on annotations in bulk using a PostgreSQL set update.
    This function avoids offset-based slicing by batching based on primary keys.
    It ensures deterministic and performant execution by progressively iterating
    over primary key ranges.

    Args:
        qs (QuerySet): Base queryset to update.
        annotation_field_pairs (list[tuple[str, str]]): List of tuples pairing annotation names
                                                        with the fields to update.
        batch_size (int, optional): Number of rows per batch. Defaults to 100,000.

    Usage example:
        >>> bulk_update_queryset(
                qs=MyModel.objects.filter(field__isnull=True),
                annotation_field_pairs=[('_annotation', 'field')]
            )
    """
    qs = qs.order_by(qs.model._meta.pk.name)
    model = qs.model
    pk_name = model._meta.pk.name
    total = qs.count()
    start_time = time.time()
    updated = 0

    annotation_keys = [ann for ann, field in annotation_field_pairs]

    last_pk = None
    while True:
        batch_filter = {f"{pk_name}__gt": last_pk} if last_pk else {}
        batch_qs = qs.filter(**batch_filter).values(pk_name, *annotation_keys)[
            :batch_size
        ]
        compiler = batch_qs.query.get_compiler(using="default")
        sub_sql, sub_params = compiler.as_sql()
        set_clause = ", ".join(
            f"{field} = sub.{ann}" for ann, field in annotation_field_pairs
        )

        sql = (
            f"WITH batch AS ({sub_sql}) "
            f"UPDATE {model._meta.db_table} AS t SET {set_clause} "
            f"FROM batch AS sub "
            f"WHERE t.{pk_name} = sub.{pk_name} "
            f"RETURNING t.{pk_name}"
        )

        with connection.cursor() as cursor:
            cursor.execute(sql, sub_params)
            rows = cursor.fetchall()
            batch_updated = len(rows)

        if batch_updated == 0:
            break

        updated += batch_updated
        last_pk = rows[-1][0]  # last pk from returned rows
        elapsed = time.time() - start_time
        rate = updated / elapsed if elapsed > 0 else 0
        logging.info(
            f"Updated {updated} of {total} ({updated / total * 100:.2f}%) - elapsed {elapsed:.2f}s - {rate:.2f} rows/s"
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
