from django.urls import path
from . import views

app_name = "mikrotik"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("routers/", views.router_list, name="router_list"),
    path("routers/add/", views.router_add, name="router_add"),
    path("routers/<int:pk>/delete/", views.router_delete, name="router_delete"),
    path("routers/<int:pk>/test/", views.router_test, name="router_test"),
    path("profiles/", views.profile_list, name="profile_list"),
    path("profiles/add/", views.profile_add, name="profile_add"),
    path("profiles/<int:pk>/delete/", views.profile_delete, name="profile_delete"),
    path("generate/", views.generate, name="generate"),
    path("batches/", views.batch_list, name="batch_list"),
    path("batches/<uuid:uuid>/print/", views.batch_print, name="batch_print"),
    path("sessions/<int:router_pk>/", views.sessions, name="sessions"),
]
