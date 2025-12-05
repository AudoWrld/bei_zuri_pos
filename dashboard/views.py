from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum
from sales.models import Sale, Return
from products.models import Product
from payments.models import Debt
from users.models import User


@login_required(login_url="login_view")
def dashboard(request):
    user = request.user

    if user.is_admin():
        return redirect("admin_dashboard")
    elif user.is_cashier():
        return redirect("cashier_dashboard")
    elif user.is_supervisor():
        return redirect("supervisor_dashboard")
    elif user.is_delivery_guy():
        return redirect("delivery_dashboard")
    else:
        return redirect("customer_dashboard")


@login_required(login_url="login_view")
def admin_dashboard(request):
    if not request.user.is_admin():
        messages.error(request, "Access denied")
        return redirect("dashboard")

    total_sales = Sale.objects.aggregate(total=Sum('final_amount'))['total'] or 0
    sales_count = Sale.objects.count()
    total_profit = total_sales
    returns_count = Return.objects.count()
    unpaid_debts_count = Debt.objects.filter(status="unpaid").count()
    products_count = Product.objects.count()
    delivery_guys_count = User.objects.filter(role=User.DELIVERY_GUY).count()
    customers_count = User.objects.filter(role=User.CUSTOMER).count()

    context = {
        "user": request.user,
        "total_sales": total_sales,
        "sales_count": sales_count,
        "total_profit": total_profit,
        "returns_count": returns_count,
        "unpaid_debts_count": unpaid_debts_count,
        "products_count": products_count,
        "delivery_guys_count": delivery_guys_count,
        "customers_count": customers_count,
    }
    return render(request, "dashboard/admin_dashboard.html", context)


@login_required(login_url="login_view")
def cashier_dashboard(request):
    if not request.user.is_cashier():
        messages.error(request, "Access denied")
        return redirect("dashboard")

    context = {
        "user": request.user,
    }
    return render(request, "dashboard/cashier_dashboard.html", context)


@login_required(login_url="login_view")
def supervisor_dashboard(request):
    if not request.user.is_supervisor():
        messages.error(request, "Access denied")
        return redirect("dashboard")

    context = {
        "user": request.user,
    }
    return render(request, "dashboard/supervisor_dashboard.html", context)


@login_required(login_url="login_view")
def delivery_dashboard(request):
    if not request.user.is_delivery_guy():
        messages.error(request, "Access denied")
        return redirect("dashboard")

    context = {
        "user": request.user,
    }
    return render(request, "dashboard/delivery_dashboard.html", context)


@login_required(login_url="login_view")
def customer_dashboard(request):
    if not request.user.is_customer():
        messages.error(request, "Access denied")
        return redirect("dashboard")

    context = {
        "user": request.user,
    }
    return render(request, "dashboard/customer_dashboard.html", context)
