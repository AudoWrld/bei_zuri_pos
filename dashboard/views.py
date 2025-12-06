from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, Count, F
from django.utils import timezone
from sales.models import Sale, Return
from products.models import Product
from payments.models import Debt
from users.models import User
from delivery.models import Delivery


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

    total_sales = Sale.objects.aggregate(total=Sum("final_amount"))["total"] or 0
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

    today = timezone.now().date()

    today_sales = Sale.objects.filter(
        cashier=request.user, completed_at__date=today
    ).aggregate(total=Sum("final_amount"), count=Count("id"))

    recent_sales = (
        Sale.objects.filter(cashier=request.user, completed_at__isnull=False)
        .select_related()
        .order_by("-completed_at")[:10]
    )

    month_start = today.replace(day=1)
    month_sales = Sale.objects.filter(
        cashier=request.user, completed_at__date__gte=month_start
    ).aggregate(total=Sum("final_amount"), count=Count("id"))

    pending_returns = Return.objects.filter(
        cashier=request.user, created_at__date=today
    ).count()

    avg_transaction = 0
    if today_sales.get("count") and today_sales.get("count") > 0:
        avg_transaction = today_sales.get("total", 0) / today_sales.get("count", 1)

    context = {
        "user": request.user,
        "today_sales": today_sales,
        "recent_sales": recent_sales,
        "month_sales": month_sales,
        "pending_returns": pending_returns,
        "avg_transaction": avg_transaction,
    }
    return render(request, "dashboard/cashier_dashboard.html", context)


@login_required(login_url="login_view")
def supervisor_dashboard(request):
    if not request.user.is_supervisor():
        messages.error(request, "Access denied")
        return redirect("dashboard")

    today = timezone.now().date()
    week_ago = today - timezone.timedelta(days=7)
    month_start = today.replace(day=1)

    # Sales statistics
    today_sales = Sale.objects.filter(completed_at__date=today).aggregate(
        total=Sum("final_amount"), count=Count("id")
    )
    week_sales = Sale.objects.filter(completed_at__date__gte=week_ago).aggregate(
        total=Sum("final_amount"), count=Count("id")
    )
    month_sales = Sale.objects.filter(completed_at__date__gte=month_start).aggregate(
        total=Sum("final_amount"), count=Count("id")
    )

    # Returns statistics
    today_returns = Return.objects.filter(created_at__date=today).count()
    week_returns = Return.objects.filter(created_at__date__gte=week_ago).count()

    # Delivery statistics
    pending_deliveries = Delivery.objects.filter(status='pending').count()
    active_deliveries = Delivery.objects.filter(status__in=['assigned', 'in_transit']).count()
    completed_deliveries_today = Delivery.objects.filter(
        status='delivered', delivered_at__date=today
    ).count()

    # Inventory alerts
    low_stock_count = Product.objects.filter(
        is_active=True, quantity__lte=F("low_stock_threshold")
    ).count()
    out_of_stock_count = Product.objects.filter(is_active=True, quantity=0).count()

    # User statistics
    active_users = User.objects.filter(is_active=True).count()
    delivery_guys_count = User.objects.filter(role=User.DELIVERY_GUY, is_active=True).count()
    cashiers_count = User.objects.filter(role=User.CASHIER, is_active=True).count()

    # Recent activities
    recent_sales = Sale.objects.select_related('cashier').order_by('-completed_at')[:5]
    recent_deliveries = Delivery.objects.select_related('delivery_guy', 'sale').order_by('-created_at')[:5]

    # Top selling products today
    top_products_today = (
        Product.objects.filter(
            saleitem__sale__completed_at__date=today,
            is_active=True
        )
        .annotate(sold_quantity=Sum('saleitem__quantity'))
        .order_by('-sold_quantity')[:5]
    )

    context = {
        "user": request.user,
        "today_sales": today_sales,
        "week_sales": week_sales,
        "month_sales": month_sales,
        "today_returns": today_returns,
        "week_returns": week_returns,
        "pending_deliveries": pending_deliveries,
        "active_deliveries": active_deliveries,
        "completed_deliveries_today": completed_deliveries_today,
        "low_stock_count": low_stock_count,
        "out_of_stock_count": out_of_stock_count,
        "active_users": active_users,
        "delivery_guys_count": delivery_guys_count,
        "cashiers_count": cashiers_count,
        "recent_sales": recent_sales,
        "recent_deliveries": recent_deliveries,
        "top_products_today": top_products_today,
    }
    return render(request, "dashboard/supervisor_dashboard.html", context)


@login_required(login_url="login_view")
def delivery_dashboard(request):
    if not request.user.is_delivery_guy():
        messages.error(request, "Access denied")
        return redirect("dashboard")

    assigned_deliveries = (
        Delivery.objects.filter(
            delivery_guy=request.user, status__in=["assigned", "in_transit"]
        )
        .select_related("sale")
        .order_by("-assigned_at")
    )

    total_deliveries = Delivery.objects.filter(delivery_guy=request.user).count()
    pending_deliveries = Delivery.objects.filter(
        delivery_guy=request.user, status="assigned"
    ).count()
    in_transit_deliveries = Delivery.objects.filter(
        delivery_guy=request.user, status="in_transit"
    ).count()
    completed_count = Delivery.objects.filter(
        delivery_guy=request.user, status="delivered"
    ).count()

    context = {
        "user": request.user,
        "assigned_deliveries": assigned_deliveries,
        "stats": {
            "total": total_deliveries,
            "pending": pending_deliveries,
            "in_transit": in_transit_deliveries,
            "completed": completed_count,
        },
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


def splash_view(request):
    return render(request, "splash.html")
