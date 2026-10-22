from django.db import migrations


def seed_roles(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    for name in ["SUPER_ADMIN", "ADMIN_STAFF"]:
        Group.objects.get_or_create(name=name)


class Migration(migrations.Migration):
    dependencies = [("accounts", "0001_initial")]
    operations = [migrations.RunPython(seed_roles, migrations.RunPython.noop)]
