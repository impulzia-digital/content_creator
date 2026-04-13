from django.urls import path
from apps.brands import views

app_name = "brands"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("brands/", views.brand_list, name="brand_list"),
    path("brands/<slug:slug>/switch/", views.brand_switch, name="brand_switch"),
]
