from django.urls import path
from apps.content import views

app_name = "content"

urlpatterns = [
    path("briefs/", views.brief_list, name="brief_list"),
    path("briefs/new/", views.brief_create, name="brief_create"),
    path("briefs/<uuid:brief_id>/", views.brief_detail, name="brief_detail"),
    path("briefs/<uuid:brief_id>/generate/", views.brief_generate, name="brief_generate"),
    path("variants/<uuid:variant_id>/select/", views.variant_select, name="variant_select"),
]
