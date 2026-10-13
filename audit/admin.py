from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = (
        'created_at',
        'organization',
        'actor',
        'action',
        'target_type',
        'target_id',
    )
    list_filter = (
        'action',
        'organization',
    )
    search_fields = (
        'description',
        'actor__username',
        'organization__name',
        'target_id',
    )
    list_select_related = (
        'organization',
        'actor',
    )
    readonly_fields = (
        'organization',
        'actor',
        'action',
        'target_type',
        'target_id',
        'description',
        'created_at',
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
