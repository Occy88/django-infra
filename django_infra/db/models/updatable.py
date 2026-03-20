from django.db import DEFAULT_DB_ALIAS
from django.db import models as dm


class UpdatableModel(dm.Model):
    """A model mixin providing an efficient update mechanism.

    This mixin allows updating multiple fields in a single call. It supports:
      - Direct database updates via the queryset (bypassing ORM signals) when
        `bypass_orm` is True.
      - Instance updates with signal triggering when `commit` is True.

    Examples:
        inst = UpdatableModel()
        inst.update(field='new_val', field_2='other_val')
        inst.update(field='new_val', field_2='other_val', bypass_orm=True)
        inst.update(field='new_val', field_2='other_val', commit=False)
    """

    class Meta:
        abstract = True

    def update(
        self,
        bypass_orm=False,
        commit=True,
        databases: list = None,
        **fields,
    ) -> None:
        """Update one or more fields on the model instance.

        Parameters:
            bypass_orm (bool): If True, performs a direct database update via queryset
                               without triggering ORM signals.
            commit (bool): If True, saves changes to the database after updating the instance.
                           If False, updates the instance without saving to the database.
            databases (list, optional): A list of database aliases to use when bypassing the ORM.
            **fields: Field names and their new values.

        Raises:
            RuntimeError: If databases are specified without setting bypass_orm to True.
        """
        if databases and not bypass_orm:
            raise RuntimeError(
                "Please set bypass_orm to True when specifying databases"
            )
        if bypass_orm:
            if databases:
                for db in databases or list():
                    self.__class__.objects.using(db).filter(pk=self.pk).update(**fields)
                return
            self.__class__.objects.filter(pk=self.pk).update(**fields)
            return
        modified_fields = []

        for field, new_value in fields.items():
            current_value = getattr(self, field)

            if current_value != new_value:
                setattr(self, field, new_value)
                if commit:
                    modified_fields.append(field)

        if modified_fields:
            self.save(update_fields=modified_fields)

    def save(self, *args, commit=True, **kwargs):
        """Save the model instance.

        If commit is False, triggers the pre-save signal without writing to the database.
        Otherwise, performs a standard save.
        """
        if not commit:
            dm.signals.pre_save.send(
                sender=type(self),
                instance=self,
                raw=False,
                using=kwargs.get("using", DEFAULT_DB_ALIAS),
                update_fields=kwargs.get("update_fields"),
            )
            return
        super().save(*args, **kwargs)
