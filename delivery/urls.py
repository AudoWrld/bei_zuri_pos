from django.urls import path
from . import views

app_name = "delivery"

urlpatterns = [
    path("", views.delivery_home, name="delivery_home"),
]