from django.urls import path
from . import views

app_name = "products"
urlpatterns = [
    path("", views.product_list, name="product_list"),
    path("add/", views.add_product, name="add_product"),
    path("update/<slug:slug>/", views.update_product, name="update_product"),
    path("toggle_active/<slug:slug>/", views.toggle_active, name="toggle_active"),
    path("add_stock/<int:pk>/", views.add_stock, name="add_stock"),
    path("categories/", views.category_list, name="category_list"),
    path("categories/add/", views.add_category, name="add_category"),
    path("categories/update/<int:pk>/", views.update_category, name="update_category"),
    path("brands/", views.brand_list, name="brand_list"),
    path("brands/add/", views.add_brand, name="add_brand"),
    path("brands/update/<int:pk>/", views.update_brand, name="update_brand"),
    path("movements/", views.stock_movements, name="stock_movements"),
    path("<slug:slug>/", views.product_detail, name="product_detail"),

]
 