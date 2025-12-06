from django.urls import path
from . import views
from sales.download_receipt import download_receipt

app_name = "sales"

urlpatterns = [
    path("new/", views.new_sale, name="new_sale"),
    path("printer-status/", views.printer_status, name="printer_status"),
    path("process/<int:sale_id>/", views.process_sale, name="process_sale"),
    path("reprint/<int:sale_id>/", views.reprint_receipt, name="reprint_receipt"),
    path("test_printer/", views.test_printer_view, name="test_printer"),
    path("history/", views.sales_history, name="history"),
    path("detail/<int:sale_id>/", views.sale_detail, name="sale_detail"),
    path("receipt/<int:sale_id>/", views.public_receipt, name="public_receipt"),
    path("analytics/", views.sale_analytics, name="analytics"),
    path("report/", views.sale_report, name="report"),
    path("trend/", views.sale_trend, name="trend"),
    path("download/<str:sale_number>/", download_receipt, name="download_receipt"),
    path("api/delivery-guys/", views.get_delivery_guys, name="get_delivery_guys"),
    path("return/", views.return_start, name="return_start"),
    path("return/<int:sale_id>/", views.return_process, name="return_process"),
    path("return/confirm/", views.return_confirm, name="return_confirm"),
    path("returns/history/", views.returns_history, name="returns_history"),
    path("return/<int:return_id>/detail/", views.return_detail, name="return_detail"),
    path(
        "return/search-product/", views.search_sale_product, name="search_sale_product"
    ),
]
