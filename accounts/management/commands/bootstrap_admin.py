import os

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.services import audit


class Command(BaseCommand):
    help = "Buat Super Admin dari EKU_ADMIN_USERNAME, EKU_ADMIN_EMAIL, EKU_ADMIN_PASSWORD. Tidak mencetak password."

    @transaction.atomic
    def handle(self, *args, **options):
        username, email, password = [
            os.getenv(k, "")
            for k in ("EKU_ADMIN_USERNAME", "EKU_ADMIN_EMAIL", "EKU_ADMIN_PASSWORD")
        ]
        if not all((username, email, password)):
            raise CommandError("Isi ketiga environment variable EKU_ADMIN_USERNAME/EMAIL/PASSWORD.")
        if get_user_model().objects.filter(username__iexact=username).exists():
            raise CommandError(
                "Akun sudah ada; password tidak diubah. Gunakan prosedur reset terpisah."
            )
        user = get_user_model()(username=username, email=email, is_superuser=True, is_staff=True)
        validate_password(password, user)
        user.set_password(password)
        user.full_clean()
        user.save()
        group, _ = Group.objects.get_or_create(name="SUPER_ADMIN")
        user.groups.add(group)
        audit(user, "USER_BOOTSTRAP", user, after={"role": "SUPER_ADMIN"})
        self.stdout.write(self.style.SUCCESS("Super Admin berhasil dibuat."))
