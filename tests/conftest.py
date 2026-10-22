from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission

from core.models import Bank, Denomination, ServiceRegion, SystemSettings


@pytest.fixture
def superuser(db):
    user = get_user_model().objects.create_superuser(
        "superadmin", "super@example.test", "Test-Only-StrongPassword42"
    )
    user.groups.add(Group.objects.get_or_create(name="SUPER_ADMIN")[0])
    return user


@pytest.fixture
def staff(db):
    user = get_user_model().objects.create_user(
        "staff", "staff@example.test", "Test-Only-StrongPassword42"
    )
    user.groups.add(Group.objects.get_or_create(name="ADMIN_STAFF")[0])
    return user


@pytest.fixture
def grant():
    def fn(user, *permissions):
        user.user_permissions.add(
            *Permission.objects.filter(content_type__app_label="cashflow", codename__in=permissions)
        )
        for attr in ("_perm_cache", "_user_perm_cache", "_group_perm_cache"):
            if hasattr(user, attr):
                delattr(user, attr)
        return user

    return fn


@pytest.fixture
def tx_data(db):
    return {
        "transaction_date": "2025-09-15",
        "bank": Bank.objects.create(code="SYNTH", name="BANK SINTETIS RAHASIA"),
        "region": ServiceRegion.objects.create(code="MANADO", name="Manado KPwBI", kind="MANADO"),
        "denomination": Denomination.objects.create(code="SYN100", value=100000, verified=True),
        "money_type": "ULE",
        "transaction_type": "DEPOSIT",
        "account": "0000123456789",
        "inflow_amount": Decimal("1000000"),
        "outflow_amount": Decimal(0),
        "pieces": 10,
        "is_demo": True,
    }


@pytest.fixture
def settings_record(db):
    return SystemSettings.load()
