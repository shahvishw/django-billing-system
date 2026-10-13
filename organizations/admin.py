from django.contrib import admin

from .models import Membership, Organization


class MembershipInline(admin.TabularInline):
    model = Membership
    extra = 1
    fields = ('user', 'login_username', 'role', 'is_active')


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'is_active',
        'created_at',
    )
    list_filter = ('is_active',)
    search_fields = ('name',)
    inlines = (MembershipInline,)


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = (
        'user',
        'login_username',
        'organization',
        'role',
        'is_active',
        'created_at',
    )
    list_filter = (
        'role',
        'is_active',
    )
    search_fields = (
        'login_username',
        'user__username',
        'organization__name',
    )
    list_select_related = (
        'user',
        'organization',
    )
