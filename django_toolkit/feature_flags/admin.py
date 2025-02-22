from django.contrib import admin

from .models import FeatureFlag


@admin.register(FeatureFlag)
class FeatureFlagAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "active",
        "value",
    )
    list_filter = ("active",)
    search_fields = ("id",)
    actions = ["activate_flags", "deactivate_flags"]

    @admin.action(description="Activate selected feature flags")
    def activate_flags(self, request, queryset):
        queryset.update(active=True)

    @admin.action(description="Deactivate selected feature flags")
    def deactivate_flags(self, request, queryset):
        queryset.update(active=False)
