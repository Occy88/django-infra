from django.db import models as dm, DEFAULT_DB_ALIAS


class UpdatableModel(dm.Model):
    """Add `update` on model to have orm-like experience & extra leverage over update.
    The purpose of `UpdatableMixin` is to reduce boilerplate/common complexity
    associated with updating an instance of a model.

    The 99% usecase of this model is as follows:
    - bypass_orm: True says use queryset to update instead of instance to avoid
    triggering signals.
    - update: allows for multi-field setting just like you would with a queryset
    without having to call save.

    Examples
    ---------
    >>> inst=UpdatableMixin()
    >>> inst.update(field='new_val',field_2='other_val') # will update db just like
    with save().
    >>> inst.update(field='new_val',field_2='other_val',bypass_orm=True) # will use
    manager to update db & won't trigger save signal.
    >>> inst.update(field='new_val',field_2='other_val',commit=False) # won't update
    db but will trigger save signal.


    This addresses things such as:
    - Updating an instance without triggering signals via `bypass_orm` flag
        (although this should be named `use_orm` instead)
    - updating multiple fields on an instance with or without committing it to the
    database.
    whilst still triggering signals.

    Debt to address:
    Make triggering signals explicit on save (when commit=False) i.e. don't just
    imply that it's happening.
    Rename `bypass_orm` to `use_queryset` instead.
    perhaps some optimization on the update function (for loop) if necessary.


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
        """Update fields of a model's instance, triggering signals
        Parameters
        ----------
        bypass_orm: exec update as SQL_UPDATE bypassing ORM features such as signals
        fields

        Returns
        -------
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
        # Call the save method of the parent class (or mixins) to ensure all logic is
        # executed
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
