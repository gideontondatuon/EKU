import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

pytestmark = pytest.mark.django_db


def test_public_and_health(client):
    assert client.get("/").status_code == 200
    assert client.get("/health/").content == b"ok"
    assert client.get("/admin/").status_code == 302


def test_auth_username_email(client):
    user = get_user_model().objects.create_user(
        "staff", "staff@example.test", "Valid-Example-Password1"
    )
    group, _ = Group.objects.get_or_create(name="ADMIN_STAFF")
    user.groups.add(group)
    response = client.post(
        "/admin/login/", {"username": "STAFF@example.test", "password": "Valid-Example-Password1"}
    )
    assert response.status_code == 302
    assert client.get("/admin/").status_code == 200
    assert client.get("/admin/logout/").status_code == 405
    assert client.post("/admin/logout/").status_code == 302


def test_headers_and_csrf(client):
    from django.test import Client

    assert "script-src 'self'" in client.get("/")["Content-Security-Policy"]
    assert Client(enforce_csrf_checks=True).post("/admin/login/", {}).status_code == 403


def test_rate_limit(client):
    for _ in range(5):
        client.post("/admin/login/", {"username": "no-user", "password": "wrong"})
    assert (
        client.post("/admin/login/", {"username": "no-user", "password": "wrong"}).status_code
        == 429
    )
