from django.contrib import admin
from .models import Email2FACode


@admin.register(Email2FACode)
class Email2FACodeAdmin(admin.ModelAdmin):
    list_display = ('user', 'code', 'created_at')
    readonly_fields = ('user', 'code', 'created_at')
    ordering = ('-created_at',)
