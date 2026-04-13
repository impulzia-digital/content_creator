from django.urls import path
from apps.approvals import views

app_name = "approvals"

urlpatterns = [
    path("approvals/", views.approval_list, name="approval_list"),
    path("approvals/<uuid:approval_id>/decide/", views.approval_decide, name="approval_decide"),
]
