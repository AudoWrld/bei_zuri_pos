from django.urls import path
from . import views

app_name = "payments"

urlpatterns = [
    path('initiate-payment/', views.initiate_payment_view, name='initiate_payment'),
    path('check-payment-status/', views.check_payment_status, name='check_payment_status'),
    path('callback/', views.payment_callback, name='payment_callback'),
    path('list/', views.payment_list, name='payment_list'),
    path('debt/', views.debt_list, name='debt_list'),
]
