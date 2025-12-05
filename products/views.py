from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from .models import Product, Category, Brand, StockMovement
from .forms import ProductForm, CategoryForm, BrandForm, Barcode
import json


@login_required
def product_detail(request, slug):
    product = get_object_or_404(Product, slug=slug)
    context = {
        "product": product,
    }
    return render(request, "products/product_detail.html", context)


@login_required
def product_list(request):
    products = Product.objects.all()

    search_query = request.GET.get("search", "").strip()
    if search_query:
        products = products.filter(
            Q(name__icontains=search_query)
            | Q(sku__icontains=search_query)
            | Q(category__name__icontains=search_query)
            | Q(brand__name__icontains=search_query)
        )

    sort_by = request.GET.get("sort", "name")

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
        "created_at",
        "-created_at",
    ]

    if sort_by not in valid_sort_fields:
        sort_by = "name"

    products = products.order_by(sort_by)

    paginator = Paginator(products, 15)
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
        "search_query": search_query,
    }
    return render(request, "products/product_list.html", context)


@login_required
def add_product(request):
    if not request.user.can_add_products():
        raise PermissionDenied("You do not have permission to add products.")

    if request.method == "POST":
        form = ProductForm(request.POST)
        if form.is_valid():
            product = form.save(commit=False)
            if not product.sku:
                from .models import generate_sku

                product.sku = generate_sku(product.name)
            product.save()

            barcodes_data = request.POST.get("barcodes", "[]")
            try:
                barcode_list = json.loads(barcodes_data)
                if barcode_list:
                    for barcode_value in barcode_list:
                        if barcode_value.strip():
                            Barcode.objects.create(
                                barcode=barcode_value.strip(),
                                product=product,
                                is_active=True,
                            )
                else:
                    from .models import generate_barcode

                    Barcode.objects.create(
                        barcode=generate_barcode(), product=product, is_active=True
                    )
            except (json.JSONDecodeError, ValueError):
                from .models import generate_barcode

                Barcode.objects.create(
                    barcode=generate_barcode(), product=product, is_active=True
                )

            if product.quantity > 0:
                from .models import StockMovement

                StockMovement.objects.create(
                    product=product,
                    movement_type="IN",
                    quantity=product.quantity,
                    previous_quantity=0,
                    new_quantity=product.quantity,
                    notes=f"Initial stock - {product.quantity} units",
                )

            messages.success(request, "Product added successfully.")
            return redirect("products:product_list")

    else:
        form = ProductForm()

    context = {
        "form": form,
    }
    return render(request, "products/add_product.html", context)


@login_required
def stock_movements(request):
    movements = StockMovement.objects.select_related('product').all()

    search_query = request.GET.get("search", "").strip()
    if search_query:
        movements = movements.filter(
            Q(product__name__icontains=search_query) |
            Q(movement_type__icontains=search_query) |
            Q(notes__icontains=search_query)
        )

    movement_type = request.GET.get("movement_type")
    if movement_type:
        movements = movements.filter(movement_type=movement_type)

    sort_by = request.GET.get("sort", "-created_at")

    valid_sort_fields = [
        "product__name",
        "-product__name",
        "movement_type",
        "-movement_type",
        "quantity",
        "-quantity",
        "created_at",
        "-created_at",
    ]

    if sort_by not in valid_sort_fields:
        sort_by = "-created_at"

    movements = movements.order_by(sort_by)

    paginator = Paginator(movements, 15)
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
        "search_query": search_query,
        "movement_type": movement_type,
    }
    return render(request, "products/stock_movements.html", context)


@login_required
def category_list(request):
    categories = Category.objects.all()
    context = {
        "categories": categories,
    }
    return render(request, "products/category_list.html", context)


@login_required
def add_category(request):
    if not request.user.can_add_products():
        raise PermissionDenied("You do not have permission to add categories.")

    if request.method == "POST":
        form = CategoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Category added successfully.")
            return redirect("products:category_list")
    else:
        form = CategoryForm()

    context = {
        "form": form,
    }
    return render(request, "products/add_category.html", context)


@login_required
def update_category(request, pk):
    category = get_object_or_404(Category, pk=pk)
    if not request.user.can_edit_products():
        raise PermissionDenied("You do not have permission to edit categories.")

    if request.method == "POST":
        form = CategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, "Category updated successfully.")
            return redirect("products:category_list")
    else:
        form = CategoryForm(instance=category)

    context = {
        "form": form,
        "category": category,
    }
    return render(request, "products/update_category.html", context)


@login_required
def brand_list(request):
    brands = Brand.objects.all()
    context = {
        "brands": brands,
    }
    return render(request, "products/brand_list.html", context)


@login_required
def add_brand(request):
    if not request.user.can_add_products():
        raise PermissionDenied("You do not have permission to add brands.")

    if request.method == "POST":
        form = BrandForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Brand added successfully.")
            return redirect("products:brand_list")
    else:
        form = BrandForm()

    context = {
        "form": form,
    }
    return render(request, "products/add_brand.html", context)


@login_required
def update_brand(request, pk):
    brand = get_object_or_404(Brand, pk=pk)
    if not request.user.can_edit_products():
        raise PermissionDenied("You do not have permission to edit brands.")

    if request.method == "POST":
        form = BrandForm(request.POST, instance=brand)
        if form.is_valid():
            form.save()
            messages.success(request, "Brand updated successfully.")
            return redirect("products:brand_list")
    else:
        form = BrandForm(instance=brand)

    context = {
        "form": form,
        "brand": brand,
    }
    return render(request, "products/update_brand.html", context)


@login_required
def update_product(request, slug):
    product = get_object_or_404(Product, slug=slug)
    if not request.user.can_edit_products():
        raise PermissionDenied("You do not have permission to edit products.")

    original_quantity = product.quantity

    if request.method == "POST":
        form = ProductForm(request.POST, instance=product)
        if form.is_valid():
            product = form.save(commit=False)
            if not product.sku:
                from .models import generate_sku

                product.sku = generate_sku(product.name)
            product.save()

            product.barcodes.all().delete()

            barcodes_data = request.POST.get("barcodes", "[]")
            try:
                barcode_list = json.loads(barcodes_data)
                if barcode_list:
                    for barcode_value in barcode_list:
                        if barcode_value.strip():
                            Barcode.objects.create(
                                barcode=barcode_value.strip(),
                                product=product,
                                is_active=True,
                            )
                else:
                    from .models import generate_barcode

                    Barcode.objects.create(
                        barcode=generate_barcode(), product=product, is_active=True
                    )
            except (json.JSONDecodeError, ValueError):
                pass

            if product.quantity != original_quantity:
                from .models import StockMovement

                movement_type = "ADJUST"
                quantity = product.quantity - original_quantity
                StockMovement.objects.create(
                    product=product,
                    movement_type=movement_type,
                    quantity=abs(quantity),
                    previous_quantity=original_quantity,
                    new_quantity=product.quantity,
                    notes=f"Stock adjusted - {quantity} units",
                )

            messages.success(request, "Product updated successfully.")
            return redirect("products:product_list")
    else:
        form = ProductForm(instance=product)

    barcodes_list = [b.barcode for b in product.barcodes.filter(is_active=True)]
    context = {
        "form": form,
        "product": product,
        "barcodes": json.dumps(barcodes_list),
    }
    return render(request, "products/update_product.html", context)


@login_required
def toggle_active(request, slug):
    product = get_object_or_404(Product, slug=slug)
    if not request.user.can_edit_products():
        raise PermissionDenied("You do not have permission to edit products.")

    product.is_active = not product.is_active
    product.save()
    status = "activated" if product.is_active else "deactivated"
    messages.success(request, f"Product {status} successfully.")
    return redirect("products:product_detail", slug=product.slug)


@login_required
def add_stock(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if not request.user.can_manage_inventory():
        raise PermissionDenied("You do not have permission to manage inventory.")

    if request.method == "POST":
        quantity = int(request.POST.get("quantity", 0))
        if quantity > 0:
            product.restock(quantity)
            messages.success(
                request, f"Added {quantity} units to {product.name} stock."
            )
        else:
            messages.error(request, "Quantity must be greater than 0.")
    return redirect("products:product_list")
