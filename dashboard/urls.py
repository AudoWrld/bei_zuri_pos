from django.urls import path
from . import views

urlpatterns = [
    path("dashboard/", views.dashboard, name="dashboard"),
    path("admin-dashboard/", views.admin_dashboard, name="admin_dashboard"),
    path("cashier-dashboard/", views.cashier_dashboard, name="cashier_dashboard"),
    path(
        "supervisor-dashboard/", views.supervisor_dashboard, name="supervisor_dashboard"
    ),
    path("delivery-dashboard/", views.delivery_dashboard, name="delivery_dashboard"),
    path("customer-dashboard/", views.customer_dashboard, name="customer_dashboard"),
]
