from django.contrib import admin

from .models import QueryExport


@admin.register(QueryExport)
class ExporterAdmin(admin.ModelAdmin):
    list_display = (
        "id",

    )
    list_filter = ("state",)
    search_fields = ("id",)
    actions = ["cancel"]

    @admin.action(description="Activate selected feature flags")
    def cancel(self, request, queryset):
        queryset.update(active=True)
