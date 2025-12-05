from django.urls import path
from . import views

app_name = "inventory"
urlpatterns = [
    path("", views.inventory_home, name="inventory_home"),
    path("low-stock/", views.low_stock_products, name="low_stock_products"),
]
