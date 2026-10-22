from django.conf import settings

from accounts.permissions import PERMISSIONS, is_operator
from imports.models import ImportRow


def site_context(request):
    # Never expose the internal identity in public templates.
    internal = request.path.startswith("/admin/")
    return {
        "internal": internal,
        "bi_logo_static_path": settings.BI_LOGO_STATIC_PATH,
        "pending_count": ImportRow.objects.filter(status="NEEDS_REVIEW").count()
        if internal
        and is_operator(request.user)
        and request.user.has_perm("cashflow.verify_ambiguous")
        else 0,
        "permissions": [
            p
            for p in PERMISSIONS
            if internal and is_operator(request.user) and request.user.has_perm(f"cashflow.{p}")
        ],
    }
