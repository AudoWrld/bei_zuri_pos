from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Sum, F, Q, DecimalField
from django.db.models.functions import Coalesce
from django.core.paginator import Paginator
from django.utils import timezone
from products.models import Product, Category, Brand, StockMovement
from sales.models import Sale, SaleItem
from decimal import Decimal


@login_required
def inventory_home(request):
    if not request.user.can_manage_inventory():
        raise PermissionDenied("You do not have permission to view inventory.")

    today = timezone.now().date()
    today = timezone.now().date()

    total_products = Product.objects.filter(is_active=True).count()

    low_stock_count = Product.objects.filter(
        is_active=True, quantity__lte=F("low_stock_threshold")
    ).count()

    out_of_stock_count = Product.objects.filter(is_active=True, quantity=0).count()

    total_inventory_value = Product.objects.filter(is_active=True).aggregate(
        total=Coalesce(
            Sum(F("quantity") * F("cost_price"), output_field=DecimalField()),
            Decimal("0.00"),
        )
    )["total"]

    retail_sales = SaleItem.objects.filter(
        sale__sale_type="RETAIL", sale__completed_at__isnull=False
    ).select_related("product", "sale")

    wholesale_sales = SaleItem.objects.filter(
        sale__sale_type="WHOLESALE", sale__completed_at__isnull=False
    ).select_related("product", "sale")

    special_sales = SaleItem.objects.filter(
        sale__sale_type="SPECIAL", sale__completed_at__isnull=False
    ).select_related("product", "sale")

    retail_profit = Decimal("0.00")
    for item in retail_sales:
        profit_per_unit = item.product.selling_price - item.product.cost_price
        retail_profit += profit_per_unit * item.quantity

    wholesale_profit = Decimal("0.00")
    for item in wholesale_sales:
        wholesale_price = (
            item.product.wholesale_price
            if item.product.wholesale_price
            else item.product.selling_price
        )
        profit_per_unit = wholesale_price - item.product.cost_price
        wholesale_profit += profit_per_unit * item.quantity

    special_profit = Decimal("0.00")
    for item in special_sales:
        profit_per_unit = item.product.special_price - item.product.cost_price
        special_profit += profit_per_unit * item.quantity

    total_profit = retail_profit + wholesale_profit + special_profit

    daily_retail_sales = SaleItem.objects.filter(
        sale__sale_type="RETAIL", sale__completed_at__date=today
    ).select_related("product", "sale")

    daily_wholesale_sales = SaleItem.objects.filter(
        sale__sale_type="WHOLESALE", sale__completed_at__date=today
    ).select_related("product", "sale")

    daily_special_sales = SaleItem.objects.filter(
        sale__sale_type="SPECIAL", sale__completed_at__date=today
    ).select_related("product", "sale")

    daily_retail_profit = Decimal("0.00")
    for item in daily_retail_sales:
        profit_per_unit = item.product.selling_price - item.product.cost_price
        daily_retail_profit += profit_per_unit * item.quantity

    daily_wholesale_profit = Decimal("0.00")
    for item in daily_wholesale_sales:
        wholesale_price = (
            item.product.wholesale_price
            if item.product.wholesale_price
            else item.product.selling_price
        )
        profit_per_unit = wholesale_price - item.product.cost_price
        daily_wholesale_profit += profit_per_unit * item.quantity

    daily_special_profit = Decimal("0.00")
    for item in daily_special_sales:
        profit_per_unit = item.product.special_price - item.product.cost_price
        daily_special_profit += profit_per_unit * item.quantity

    daily_total_profit = (
        daily_retail_profit + daily_wholesale_profit + daily_special_profit
    )

    daily_sales_count = Sale.objects.filter(completed_at__date=today).count()
    daily_sales_revenue = Sale.objects.filter(completed_at__date=today).aggregate(
        total=Coalesce(Sum("final_amount"), Decimal("0.00"))
    )["total"]

    recent_stock_movements = StockMovement.objects.select_related("product").order_by(
        "-created_at"
    )[:10]

    top_selling_products = Product.objects.filter(
        is_active=True, sold_count__gt=0
    ).order_by("-sold_count")[:10]

    categories = Category.objects.filter(is_active=True).count()
    brands = Brand.objects.filter(is_active=True).count()

    context = {
        "total_products": total_products,
        "low_stock_count": low_stock_count,
        "out_of_stock_count": out_of_stock_count,
        "total_inventory_value": total_inventory_value,
        "retail_profit": retail_profit,
        "wholesale_profit": wholesale_profit,
        "special_profit": special_profit,
        "total_profit": total_profit,
        "daily_retail_profit": daily_retail_profit,
        "daily_wholesale_profit": daily_wholesale_profit,
        "daily_special_profit": daily_special_profit,
        "daily_total_profit": daily_total_profit,
        "daily_sales_count": daily_sales_count,
        "daily_sales_revenue": daily_sales_revenue,
        "recent_stock_movements": recent_stock_movements,
        "top_selling_products": top_selling_products,
        "categories_count": categories,
        "brands_count": brands,
    }

    return render(request, "inventory/inventory_home.html", context)


@login_required
def low_stock_products(request):
    if not request.user.can_manage_inventory():
        raise PermissionDenied("You do not have permission to view inventory.")

    products = Product.objects.filter(
        is_active=True, quantity__lte=F("low_stock_threshold")
    ).select_related("category", "brand")
    products = Product.objects.filter(
        is_active=True, quantity__lte=F("low_stock_threshold")
    ).select_related("category", "brand")

    sort_by = request.GET.get("sort", "quantity")

    valid_sort_fields = [
        "name",
        "-name",
        "sku",
        "-sku",
        "category__name",
        "-category__name",
        "brand__name",
        "-brand__name",
        "quantity",
        "-quantity",
        "selling_price",
        "-selling_price",
        "cost_price",
        "-cost_price",
        "low_stock_threshold",
        "-low_stock_threshold",
    ]

    if sort_by not in valid_sort_fields:
        sort_by = "quantity"

    products = products.order_by(sort_by)

    paginator = Paginator(products, 16)
    page_number = request.GET.get("page", 1)
    try:
        page_number = int(page_number)
        if page_number < 1:
            page_number = 1
    except ValueError:
        page_number = 1
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "show_pagination": paginator.num_pages > 1,
        "current_sort": sort_by,
        "count": products.count(),
    }

    return render(request, "inventory/low_stock.html", context)
