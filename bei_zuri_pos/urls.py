from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from dashboard.views import splash_view

urlpatterns = [
    path("admin/", admin.site.urls),
    path("select2/", include("django_select2.urls")),
    path("", include("users.urls")),
    path("", include("dashboard.urls")),
    path("products/", include("products.urls")),
    path("sales/", include("sales.urls")),
    path("payments/", include("payments.urls")),
    path("settings/", include("settings.urls")),
    path("inventory/", include("inventory.urls")),
    path("customers/", include("customers.urls")),
    path("delivery/", include("delivery.urls")),
    path("splash/", splash_view, name="splash"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
