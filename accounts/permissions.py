from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied

PERMISSIONS = (
    "import_data",
    "add_transaction",
    "edit_transaction",
    "verify_ambiguous",
    "publish_manual",
    "soft_delete",
    "restore",
    "bulk_soft_delete",
    "bulk_restore",
    "export_internal",
)


def is_super(user):
    return user.is_authenticated and user.is_active and user.is_superuser


def is_operator(user):
    return (
        user.is_authenticated
        and user.is_active
        and (is_super(user) or user.groups.filter(name="ADMIN_STAFF").exists())
    )


def require_permission(user, codename=None):
    if not is_operator(user) or (codename and not user.has_perm(f"cashflow.{codename}")):
        raise PermissionDenied("Anda tidak memiliki izin untuk tindakan ini.")


def operator_required(permission=None, super_only=False):
    def decorator(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            require_permission(request.user, permission)
            if super_only and not is_super(request.user):
                raise PermissionDenied("Hanya Super Admin yang diizinkan.")
            return view(request, *args, **kwargs)

        return wrapped

    return decorator
