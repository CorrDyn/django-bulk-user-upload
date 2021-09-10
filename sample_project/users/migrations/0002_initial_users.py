from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import migrations


def add_initial_user(apps, schema_editor):
    User = get_user_model()

    _ = User.objects.create_superuser(
        username=settings.INITIAL_ADMIN_USERNAME,
        email=settings.INITIAL_ADMIN_EMAIL,
        password=settings.INITIAL_ADMIN_PASSWORD
    )


def remove_initial_user(apps, schema_editor):
    User = get_user_model()
    User.objects.filter(email=settings.INITIAL_ADMIN_EMAIL).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [migrations.RunPython(add_initial_user, remove_initial_user)]
