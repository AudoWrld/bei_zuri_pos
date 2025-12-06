from django.urls import path
from . import views

app_name = "delivery"

urlpatterns = [
    path("", views.delivery_home, name="delivery_home"),
    path("history/", views.delivery_history, name="delivery_history"),
    path("<int:delivery_id>/", views.delivery_detail, name="delivery_detail"),
]