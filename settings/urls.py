from django.urls import path
from . import views

app_name = "settings"

urlpatterns = [
    path("", views.settings_home, name="settings_home"),
    path("printer/", views.printer_settings, name="printer_settings"),
    path("users/", views.user_list, name="user_list"),
    path("users/create/", views.create_user, name="create_user"),
    path("users/<int:user_id>/update/", views.update_user, name="update_user"),
    path("users/<int:user_id>/change-password/", views.change_password, name="change_password"),
    path("users/<int:user_id>/delete/", views.delete_user, name="delete_user"),
]
