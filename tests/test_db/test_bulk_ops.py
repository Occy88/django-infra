import pytest
from model_bakery import baker

from django_toolkit.db.bulk_ops import bulk_update_queryset
from tests.test_db.models import BulkOpsTestModel, Customer, Product, Order, OrderItem

from django.db import models as dm, connections, transaction


@pytest.fixture(scope="class")
def bulk_ops_test_data(django_db_setup, django_db_blocker):
    with django_db_blocker  .unblock():
        baker.make(BulkOpsTestModel, value=1, _quantity=10)
    yield
    with django_db_blocker.unblock():
        BulkOpsTestModel.objects.all().delete()

@pytest.fixture(scope="class", autouse=True)
def db_cleanup(django_db_setup, django_db_blocker):
    with django_db_blocker.unblock():
        sid = transaction.savepoint()
    yield
    with django_db_blocker.unblock():
        transaction.savepoint_rollback(sid)

@pytest.fixture(scope="class")
def order_test_data(django_db_setup, django_db_blocker):
    with django_db_blocker.unblock():
        customer = baker.make(Customer, name="Test Customer")
        prod1 = baker.make(Product, name="Product 1", price=10.00)
        prod2 = baker.make(Product, name="Product 2", price=20.00)
        for i in range(10):
            order = baker.make(Order, customer=customer)
            baker.make(OrderItem, order=order, product=prod1, quantity=i + 1)
            baker.make(OrderItem, order=order, product=prod2, quantity=10 - i)
    yield

@pytest.fixture(scope="class")
def performance_test_data(django_db_setup, django_db_blocker):
    with django_db_blocker.unblock():
        customer = baker.make(Customer, name="Perf Test Customer")
        product = baker.make(Product, name="Perf Product", price=9.99)
        orders = baker.make(Order, customer=customer, _quantity=1_000_000)
        order_items = [baker.prepare(OrderItem, order=order, product=product, quantity=1) for order in orders]
        OrderItem.objects.bulk_create(order_items, batch_size=10000)
    yield


@pytest.mark.django_db
class TestBulkUpdatePerformance:
    @pytest.mark.skip(reason='slow')
    def test_bulk_update_order_total_performance(self, performance_test_data):
        qs = Order.objects.with_computed_total()
        bulk_update_queryset(
            qs=qs,
            annotation_field_pairs=[("computed_total_annotation", "computed_total")],
        )
        sample = Order.objects.first()
        expected = sum(item.quantity * item.product.price for item in sample.orderitem.all())
        assert sample.computed_total == expected

@pytest.mark.django_db
class TestBulkUpdateOrderTotals:
    def test_bulk_update_order_total_small(self, order_test_data):
        order_totals = OrderItem.objects.filter(order=dm.OuterRef('pk')).annotate(
            line_total=dm.ExpressionWrapper(
                dm.F('quantity') * dm.F('product__price'),
                output_field=dm.DecimalField(max_digits=12, decimal_places=2)
            )
        ).values('order').annotate(total=dm.Sum('line_total')).values('total')

        Order.objects.update(
            computed_total=dm.Subquery(
                order_totals,
                output_field=dm.DecimalField(max_digits=12, decimal_places=2)
            )
        )
        # bulk_update_queryset(
        #     qs=qs,
        #     annotation_field_pairs=[("computed_total_annotation", "computed_total")],
        # )
        for order in Order.objects.all():
            expected = sum(item.quantity * item.product.price for item in order.orderitem.all())
            assert order.computed_total == expected

@pytest.mark.django_db
class TestBulkUpdateQueryset:
    def test_bulk_update(self, bulk_ops_test_data):
        qs = BulkOpsTestModel.objects.all().annotate(_value_plus_ten=dm.F("value") + 10)
        bulk_update_queryset(
            qs=qs,
            annotation_field_pairs=[("_value_plus_ten", "updated_value")],
        )
        for obj in BulkOpsTestModel.objects.order_by("id"):
            assert obj.updated_value == obj.value + 10

        Order.objects.all().update()



