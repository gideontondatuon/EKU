from django.urls import path

from accounts import views as auth_views
from dashboard import views

urlpatterns = [
    path("", views.public_home, name="public"),
    path("api/public/cashflow/", views.public_api, name="public_api"),
    path("export/<str:fmt>/", views.export_view, name="public_export"),
    path("health/", auth_views.health, name="health"),
    path("admin/login/", auth_views.login_view, name="login"),
    path("admin/logout/", auth_views.logout_view, name="logout"),
    path("admin/", views.admin_home, name="admin_home"),
    path("admin/transactions/", views.transactions, name="transactions"),
    path("admin/transactions/new/", views.transaction_form, name="transaction_new"),
    path("admin/transactions/<uuid:pk>/edit/", views.transaction_form, name="transaction_edit"),
    path("admin/archive/", views.transactions, {"archive": True}, name="archive"),
    path("admin/imports/", views.imports_home, name="imports"),
    path("admin/imports/<uuid:pk>/", views.import_detail, name="import_detail"),
    path("admin/imports/<uuid:pk>/quality/", views.import_quality, name="import_quality"),
    path("admin/review/", views.review_home, name="review"),
    path("admin/review/<uuid:pk>/", views.review_detail, name="review_detail"),
    path("admin/publications/", views.publications_home, name="publications"),
    path("admin/users/", views.users_view, name="users"),
    path("admin/users/<int:pk>/", views.users_view, name="user_edit"),
    path("admin/audit/", views.audit_view, name="audit"),
    path("admin/reset-data/", views.reset_data_view, name="reset_data"),
    path("admin/settings/", views.settings_view, name="settings"),
    path("admin/masters/", views.masters_view, name="masters"),
    path("admin/estimates/", views.estimates_view, name="estimates"),
    path("admin/export/<str:fmt>/", views.export_view, {"internal": True}, name="internal_export"),
]
