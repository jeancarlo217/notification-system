"""The maintenance door of foundation section 6, over the reference tables a human edits.

The catalogue and the people are seeded once by a migration and grow through these screens
(ADR 0005, ADR 0006). The employee-facing product is the form and the list, never this site.
"""

from typing import TYPE_CHECKING

from django.contrib import admin

from core.models import CatalogService, ServiceCategory, Submitter

if TYPE_CHECKING:
    ServiceCategoryModelAdmin = admin.ModelAdmin[ServiceCategory]
    CatalogServiceModelAdmin = admin.ModelAdmin[CatalogService]
    SubmitterModelAdmin = admin.ModelAdmin[Submitter]
else:
    # The stubs make ModelAdmin generic; the runtime class is not subscriptable.
    ServiceCategoryModelAdmin = admin.ModelAdmin
    CatalogServiceModelAdmin = admin.ModelAdmin
    SubmitterModelAdmin = admin.ModelAdmin


@admin.register(ServiceCategory)
class ServiceCategoryAdmin(ServiceCategoryModelAdmin):
    list_display = ("name", "position", "is_active")
    list_editable = ("position", "is_active")
    ordering = ("position", "name")
    search_fields = ("name",)


@admin.register(CatalogService)
class CatalogServiceAdmin(CatalogServiceModelAdmin):
    list_display = ("name", "category", "position", "is_active")
    list_editable = ("position", "is_active")
    list_filter = ("category", "is_active")
    list_select_related = ("category",)
    ordering = ("category__position", "position")
    search_fields = ("name",)


@admin.register(Submitter)
class SubmitterAdmin(SubmitterModelAdmin):
    list_display = ("display_name", "normalized_name", "is_active", "created_at")
    list_filter = ("is_active",)
    ordering = ("display_name",)
    # The model derives the key from the name on every write (I8), so an input for it would
    # accept what an administrator types and then discard it.
    readonly_fields = ("normalized_name", "created_at")
    search_fields = ("display_name", "normalized_name")
