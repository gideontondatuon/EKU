import hashlib
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.db import connection, transaction
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.services import audit

from .models import LoginAttempt
from .permissions import is_operator, operator_required


def consume_limit(key, limit=5, seconds=900):
    now = timezone.now()
    digest = hashlib.sha256(key.encode()).hexdigest()
    with transaction.atomic():
        item, _ = LoginAttempt.objects.get_or_create(key=digest, defaults={"window_start": now})
        item = LoginAttempt.objects.select_for_update().get(pk=item.pk)
        if item.window_start < now - timedelta(seconds=seconds):
            item.attempts, item.window_start = 0, now
        item.attempts += 1
        item.save(update_fields=["attempts", "window_start"])
        return item.attempts <= limit


def login_view(request):
    form = AuthenticationForm(request, data=request.POST or None)
    if request.method == "POST":
        username = request.POST.get("username", "").strip().lower()
        ip = request.META.get("REMOTE_ADDR", "unknown")
        allowed_ip = consume_limit("login-ip:" + ip, limit=30)
        allowed_user = consume_limit("login-user:" + username)
        if not allowed_ip or not allowed_user:
            audit(None, "LOGIN_RATE_LIMITED")
            return render(
                request,
                "login.html",
                {"form": form, "error": "Terlalu banyak percobaan. Coba lagi setelah 15 menit."},
                status=429,
            )
        if form.is_valid() and is_operator(form.get_user()):
            login(request, form.get_user())
            audit(form.get_user(), "LOGIN_SUCCESS")
            return redirect("/admin/")
        audit(None, "LOGIN_FAILURE")
        messages.error(request, "Username/email atau kata sandi tidak cocok.")
    return render(request, "login.html", {"form": form, "page_title": "Masuk Admin"})


@require_POST
def logout_view(request):
    if request.user.is_authenticated:
        audit(request.user, "LOGOUT")
    logout(request)
    return redirect("/")


@operator_required()
def admin_home(request):
    return HttpResponse("Dashboard Admin PUR — lingkungan siap.")


def health(request):
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
    return HttpResponse("ok", content_type="text/plain")
