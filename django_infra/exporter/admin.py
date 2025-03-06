from django.contrib import admin

from .models import QueryExport


@admin.register(QueryExport)
class ExporterAdmin(admin.ModelAdmin):
    list_display = ("id",)
    list_filter = ("state",)
    search_fields = ("id",)
