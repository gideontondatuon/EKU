from datetime import date
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from cashflow.models import CashflowTransaction
from cashflow.services import model_fingerprint, validate_transaction
from core.models import Bank, Denomination, ServiceRegion
from core.services import audit, changed, lock_settings


class Command(BaseCommand):
    help = "Seed sintetis terpisah. Dilarang di production; tidak memublikasikan otomatis dalam mode MANUAL."

    def add_arguments(self, parser):
        parser.add_argument("--confirm-dummy", action="store_true")
        parser.add_argument("--username")

    @transaction.atomic
    def handle(self, *args, **options):
        if settings.ENVIRONMENT == "production" or not options["confirm_dummy"]:
            raise CommandError("Hanya nonproduction, wajib --confirm-dummy.")
        users = get_user_model().objects.filter(is_superuser=True, is_active=True)
        if options["username"]:
            users = users.filter(username=options["username"])
        actor = users.first()
        if not actor:
            raise CommandError("Buat Super Admin terlebih dahulu menggunakan bootstrap_admin.")
        lock_settings()
        if CashflowTransaction.objects.filter(dataset="SYNTHETIC-SEED").exists():
            self.stdout.write("Seed sudah ada; tidak membuat ulang atau memulihkan arsip.")
            return
        bank, _ = Bank.objects.get_or_create(
            code="DEMO-BANK", defaults={"name": "BANK SINTETIS DEMO"}
        )
        denom, _ = Denomination.objects.get_or_create(
            code="DEMO100",
            defaults={
                "value": 100000,
                "verified": True,
                "source_note": "DATA DUMMY sintetis untuk pengujian",
            },
        )
        regions = [
            ServiceRegion.objects.get_or_create(
                code=f"DEMO-{n}", defaults={"name": name, "kind": kind}
            )[0]
            for n, name, kind in [
                ("MANADO", "Manado (demo sintetis)", "MANADO"),
                ("SKM", "Kas Titipan (demo sintetis)", "SKM"),
            ]
        ]
        count = 0
        for year in (2023, 2024, 2025):
            for month in range(1, 13):
                for region_index, region in enumerate(regions):
                    for direction in ("DEPOSIT", "WITHDRAWAL"):
                        pieces = (
                            (year - 2020) * 100
                            + month * 20
                            + region_index * 40
                            + (80 if direction == "WITHDRAWAL" else 0)
                        )
                        amount = Decimal(pieces) * denom.value
                        tx = CashflowTransaction(
                            transaction_date=date(year, month, 15),
                            bank=bank,
                            region=region,
                            denomination=denom,
                            money_type="ULE",
                            transaction_type=direction,
                            account="DEMO",
                            inflow_amount=amount if direction == "DEPOSIT" else 0,
                            outflow_amount=amount if direction == "WITHDRAWAL" else 0,
                            pieces=pieces,
                            dataset="SYNTHETIC-SEED",
                            is_demo=True,
                            created_by=actor,
                            updated_by=actor,
                            provenance={"source": "DATA DUMMY — rumus fixture, bukan estimasi"},
                        )
                        tx.fingerprint = model_fingerprint(tx)
                        validate_transaction(tx)
                        tx.save()
                        count += 1
        audit(actor, "SEED_SYNTHETIC", after={"count": count, "source": "DATA DUMMY"})
        changed(actor)
        self.stdout.write(self.style.SUCCESS(f"{count} transaksi DATA DUMMY dibuat."))
