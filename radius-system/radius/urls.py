from django.urls import path
from . import views

urlpatterns = [
    path("dashboard/", views.dashboard, name="dashboard"),
    # NAS
    path("routers/", views.nas_list, name="nas_list"),
    path("routers/add/", views.nas_add, name="nas_add"),
    path("routers/<int:pk>/delete/", views.nas_delete, name="nas_delete"),
    path("routers/<int:pk>/config/", views.mikrotik_config, name="mikrotik_config"),
    # Profiles
    path("profiles/", views.profile_list, name="profile_list"),
    path("profiles/add/", views.profile_add, name="profile_add"),
    path("profiles/<int:pk>/edit/", views.profile_edit, name="profile_edit"),
    path("profiles/<int:pk>/delete/", views.profile_delete, name="profile_delete"),
    # Vouchers
    path("vouchers/generate/", views.voucher_generate, name="voucher_generate"),
    path("vouchers/batches/", views.batch_list, name="batch_list"),
    path("vouchers/batches/<uuid:uuid>/", views.batch_detail, name="batch_detail"),
    path("vouchers/batches/<uuid:uuid>/delete/", views.batch_delete, name="batch_delete"),
    path("vouchers/batches/<uuid:uuid>/csv/", views.export_csv, name="export_csv"),
    path("vouchers/batches/<uuid:uuid>/pdf/", views.export_pdf, name="export_pdf"),
    path("vouchers/<int:pk>/disable/", views.voucher_disable, name="voucher_disable"),
    # Sessions
    path("sessions/", views.sessions_view, name="sessions"),
]
