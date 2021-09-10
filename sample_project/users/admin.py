from django.contrib.admin import register
from django.contrib.auth import get_user_model

from bulk_user_upload.admin import BulkUploadUserAdmin

User = get_user_model()


@register(User)
class CustomUserAdmin(BulkUploadUserAdmin):
    list_display = ["username", "email", "is_staff", "is_superuser", "is_active"]
    list_filter = ("is_staff", "is_superuser", "is_active", "groups")
    ordering = ("-is_active", "username", "email",)

    add_fieldsets = (
        (
            None,
            {
                "fields": (
                    "username",
                    "email",
                    "name",
                    "password1",
                    "password2",
                ),
            },
        ),
    )
    fieldsets = (
        (
            None, {
                "fields": (
                    "username",
                )
            }
        ),
        (
            None,
            {
                "fields": (
                    "email",
                    "password",
                )
            },
        ),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "user_permissions",
                    "groups",
                ),
            },
        ),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
