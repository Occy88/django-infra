from django.db import models as dm

from django_rocket.db.models import UpdatableModel


class UpdatableTestModel(UpdatableModel):
    field1 = dm.CharField(max_length=100, default="", blank=True)
    field2 = dm.CharField(max_length=100, default="", blank=True)

    class Meta:
        app_label = __package__.replace(".", "_")


# -------------- BULK OPS MODELS ----------------------
class BulkOpsTestModel(UpdatableModel):
    value = dm.IntegerField(default=0)
    updated_value = dm.IntegerField(null=True)

    class Meta:
        app_label = __package__.replace(".", "_")


# A somewhat complex scenario for testing bulk operations.


class Customer(UpdatableModel):
    name = dm.CharField(max_length=100)

    class Meta:
        app_label = __package__.replace(".", "_")


class Product(UpdatableModel):
    name = dm.CharField(max_length=100)
    price = dm.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        app_label = __package__.replace(".", "_")


class OrderQuerySet(dm.QuerySet):
    def with_computed_total(self):
        return self.annotate(
            computed_total_annotation=dm.Sum(
                dm.ExpressionWrapper(
                    dm.F("orderitem__quantity") * dm.F("orderitem__product__price"),
                    output_field=dm.DecimalField(max_digits=12, decimal_places=2),
                )
            )
        )


class OrderManager(dm.Manager):
    def get_queryset(self):
        return OrderQuerySet(self.model, using=self._db)

    def with_computed_total(self):
        return self.get_queryset().with_computed_total()


class Order(UpdatableModel):
    customer = dm.ForeignKey(Customer, on_delete=dm.CASCADE, related_name="orders")
    computed_total = dm.DecimalField(max_digits=12, decimal_places=2, null=True)
    created_at = dm.DateTimeField(auto_now_add=True)

    objects = OrderManager()

    class Meta:
        app_label = __package__.replace(".", "_")


class OrderItem(UpdatableModel):
    order = dm.ForeignKey(Order, on_delete=dm.CASCADE, related_name="orderitem")
    product = dm.ForeignKey(Product, on_delete=dm.CASCADE)
    quantity = dm.IntegerField()

    class Meta:
        app_label = __package__.replace(".", "_")
