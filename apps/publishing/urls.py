from django.urls import path
from apps.publishing import views

app_name = "publishing"

urlpatterns = [
    path("publishing/", views.schedule_list, name="schedule_list"),
    path("publishing/<uuid:variant_id>/schedule/", views.schedule_create, name="schedule_create"),
    path("publishing/<uuid:schedule_id>/cancel/", views.schedule_cancel, name="schedule_cancel"),
]
