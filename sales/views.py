from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.db import models
from decimal import Decimal
import logging
from django.db.models import Sum, Count
from django.db.models.functions import TruncDate, ExtractHour
from django.utils import timezone
from datetime import timedelta
import json
from django.db.models import Sum, Count, Avg, Q
from .models import Sale, SaleItem, Return, ReturnItem
from products.models import Product, Barcode, StockMovement
from .forms import ReturnStartForm, get_return_formset
from hardware.printer_client import (
    print_receipt,
    check_printer_status,
    print_test_receipt,
    format_receipt_data,
)

logger = logging.getLogger(__name__)


@login_required
def new_sale(request):
    if not request.user.can_process_sales():
        raise PermissionDenied("You do not have permission to process sales.")

    existing_sale = Sale.objects.filter(
        cashier=request.user, completed_at__isnull=True
    ).first()

    if existing_sale:
        existing_sale.delete()

    if request.method == "POST":
        sale_type = request.POST.get("sale_type", "RETAIL")
        sale = Sale.objects.create(cashier=request.user, sale_type=sale_type)
        return redirect("sales:process_sale", sale_id=sale.id)

    return render(request, "sales/new_sale.html")


@login_required
@require_http_methods(["GET"])
def printer_status(request):
    if not request.user.can_process_sales():
        return JsonResponse({"success": False, "error": "Permission denied"})

    printer_ready, printer_message = check_printer_status()

    return JsonResponse(
        {
            "success": True,
            "printer_ready": printer_ready,
            "printer_message": printer_message,
        }
    )


@login_required
def process_sale(request, sale_id):
    if not request.user.can_process_sales():
        raise PermissionDenied("You do not have permission to process sales.")

    sale = get_object_or_404(Sale, id=sale_id, cashier=request.user)

    if sale.completed_at:
        return redirect("sales:new_sale")

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "add_item":
            return add_item_to_sale(request, sale)
        elif action == "remove_item":
            return remove_item_from_sale(request, sale)
        elif action == "update_quantity":
            return update_item_quantity(request, sale)
        elif action == "complete_sale":
            return complete_sale(request, sale)
        elif action == "scan_barcode":
            return scan_barcode(request, sale)
        elif action == "hold_sale":
            return hold_sale(request, sale)
        elif action == "recall_sale":
            return recall_sale(request, sale)
        elif action == "assign_delivery":
            return assign_delivery(request, sale)

    items = sale.items.select_related("product").all()
    subtotal = sum(item.quantity * item.unit_price for item in items)

    special_total = Decimal("0")
    if sale.sale_type == "SPECIAL":
        special_total = sum(
            ((item.product.special_price or item.unit_price) - item.unit_price)
            * item.quantity
            for item in items
        )

    available_products = Product.objects.filter(
        is_active=True, quantity__gt=0
    ).order_by("name")

    context = {
        "sale": sale,
        "items": items,
        "subtotal": subtotal,
        "special_total": special_total,
        "total": subtotal + special_total,
        "available_products": available_products,
        "is_held": sale.is_held,
    }
    return render(request, "sales/process_sale.html", context)


def add_item_to_sale(request, sale):
    if sale.is_held:
        messages.error(request, "Cannot add items to a sale that is on hold")
        return redirect("sales:process_sale", sale_id=sale.id)

    product_id = request.POST.get("product_id")
    quantity = int(request.POST.get("quantity", 1))

    try:
        product = Product.objects.get(id=product_id, is_active=True)

        if sale.sale_type == "SPECIAL" and not product.special_price:
            messages.error(
                request, f"{product.name} has no special price for special sale"
            )
            return redirect("sales:process_sale", sale_id=sale.id)

        existing_item = sale.items.filter(product=product).first()
        total_quantity = quantity
        if existing_item:
            total_quantity = existing_item.quantity + quantity

        if sale.sale_type == "WHOLESALE" and product.wholesale_price:
            unit_price = product.wholesale_price
        elif sale.sale_type == "SPECIAL" and product.special_price:
            unit_price = product.special_price
        else:
            unit_price = product.selling_price

        if existing_item:
            existing_item.quantity = total_quantity
            existing_item.save()
        else:
            SaleItem.objects.create(
                sale=sale,
                product=product,
                quantity=quantity,
                unit_price=unit_price,
            )

        messages.success(request, f"Added {quantity} x {product.name} to sale")
    except Product.DoesNotExist:
        messages.error(request, "Product not found or inactive")

    return redirect("sales:process_sale", sale_id=sale.id)


@login_required
def remove_item_from_sale(request, sale):
    if sale.is_held:
        return JsonResponse({"success": False, "error": "Sale is on hold"})

    item_id = request.POST.get("item_id")
    try:
        item = sale.items.get(id=item_id)
        item.delete()

        items = sale.items.all()
        subtotal = sum(item.quantity * item.unit_price for item in items)
        special_total = Decimal("0")
        if sale.sale_type == "SPECIAL":
            special_total = sum(
                ((item.product.special_price or item.unit_price) - item.unit_price)
                * item.quantity
                for item in items
            )

        return JsonResponse(
            {
                "success": True,
                "totals": {
                    "items_count": items.count(),
                    "subtotal": str(subtotal),
                    "special_total": str(special_total),
                    "total": str(subtotal + special_total),
                },
            }
        )
    except SaleItem.DoesNotExist:
        return JsonResponse({"success": False, "error": "Item not found in sale"})


@login_required
def update_item_quantity(request, sale):
    if sale.is_held:
        return JsonResponse({"success": False, "error": "Sale is on hold"})

    item_id = request.POST.get("item_id")
    quantity = int(request.POST.get("quantity", 1))

    try:
        item = sale.items.get(id=item_id)

        if quantity < 1:
            return JsonResponse(
                {"success": False, "error": "Quantity must be at least 1"}
            )

        item.quantity = quantity
        item.save()

        items = sale.items.all()
        subtotal = sum(i.quantity * i.unit_price for i in items)
        special_total = Decimal("0")
        if sale.sale_type == "SPECIAL":
            special_total = sum(
                ((i.product.special_price or i.unit_price) - i.unit_price) * i.quantity
                for i in items
            )

        return JsonResponse(
            {
                "success": True,
                "item_total": str(item.total_amount),
                "totals": {
                    "items_count": items.count(),
                    "subtotal": str(subtotal),
                    "special_total": str(special_total),
                    "total": str(subtotal + special_total),
                },
            }
        )
    except SaleItem.DoesNotExist:
        return JsonResponse({"success": False, "error": "Item not found in sale"})
    except Exception as e:
        logger.error(f"Error updating quantity: {str(e)}")
        return JsonResponse({"success": False, "error": str(e)})


def complete_sale(request, sale):
    if sale.is_held:
        messages.error(request, "Cannot complete a sale that is on hold")
        return redirect("sales:process_sale", sale_id=sale.id)

    payment_method = request.POST.get("payment_method", "Cash")
    money_received = request.POST.get("money_received")
    mobile_number = request.POST.get("mobile_number")
    transaction_reference = request.POST.get("transaction_reference")

    customer_first_name = request.POST.get("customer_first_name")
    customer_second_name = request.POST.get("customer_second_name")
    customer_phone = request.POST.get("customer_phone")
    customer_email = request.POST.get("customer_email")

    if not sale.items.exists():
        messages.error(request, "Cannot complete sale with no items")
        return redirect("sales:process_sale", sale_id=sale.id)

    if payment_method == "Cash":
        if not money_received:
            messages.error(request, "Enter money received")
            return redirect("sales:process_sale", sale_id=sale.id)

        money_received = Decimal(money_received)

        if money_received < sale.final_amount:
            messages.error(
                request,
                f"Amount received ({money_received}) is less than total ({sale.final_amount})",
            )
            return redirect("sales:process_sale", sale_id=sale.id)

        sale.payment_method = payment_method
        sale.discount_amount = Decimal("0")
        sale.complete_sale()
        sale.money_received = money_received
        sale.change_amount = money_received - sale.final_amount
        sale.save()

        from payments.models import Payment
        import uuid

        transaction_ref = f"SALE-{sale.sale_number}-{uuid.uuid4().hex[:6].upper()}"
        Payment.objects.create(
            payment_type="cash",
            amount=sale.final_amount,
            status="completed",
            transaction_reference=transaction_ref,
            notes=f"Cash payment for Sale #{sale.sale_number}",
        )

        success, message = print_receipt(sale)

        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse(
                {
                    "success": True,
                    "sale_number": sale.sale_number,
                    "print_success": success,
                    "print_message": message,
                }
            )

        if success:
            messages.success(
                request, f"Sale {sale.sale_number} completed and receipt printed!"
            )
        else:
            messages.warning(
                request,
                f"Sale {sale.sale_number} completed but printing failed: {message}",
            )

        return redirect("sales:new_sale")

    elif payment_method in ["M-Pesa", "M-PESA"]:
        paybill_confirmed = request.POST.get("paybill_confirmed")

        if paybill_confirmed:
            items = sale.items.all()
            subtotal = sum(item.quantity * item.unit_price for item in items)
            special_total = Decimal("0")
            if sale.sale_type == "SPECIAL":
                special_total = sum(
                    ((item.product.special_price or item.unit_price) - item.unit_price)
                    * item.quantity
                    for item in items
                )
            total_amount = subtotal + special_total

            from payments.models import Payment
            import uuid

            transaction_ref = f"SALE-{sale.sale_number}-{uuid.uuid4().hex[:6].upper()}"
            Payment.objects.create(
                payment_type="mpesa",
                amount=total_amount,
                status="completed",
                transaction_reference=transaction_ref,
                notes=f"PayBill payment for Sale #{sale.sale_number}",
            )

            sale.payment_method = "M-Pesa"
            sale.discount_amount = Decimal("0")
            sale.complete_sale()
            sale.save()

            success, message = print_receipt(sale)

            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse(
                    {
                        "success": True,
                        "sale_number": sale.sale_number,
                        "print_success": success,
                        "print_message": message,
                    }
                )
            else:
                if success:
                    messages.success(
                        request,
                        f"Sale {sale.sale_number} completed and receipt printed!",
                    )
                else:
                    messages.warning(
                        request,
                        f"Sale {sale.sale_number} completed but printing failed: {message}",
                    )
                return redirect("sales:new_sale")

        if transaction_reference:
            from payments.models import Payment

            payment = Payment.objects.filter(
                transaction_reference=transaction_reference
            ).first()

            if payment and payment.status == "completed" and not sale.completed_at:
                sale.payment_method = "M-Pesa"
                sale.discount_amount = Decimal("0")
                sale.complete_sale()
                sale.save()

                success, message = print_receipt(sale)

                if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                    return JsonResponse(
                        {
                            "success": True,
                            "sale_number": sale.sale_number,
                            "print_success": success,
                            "print_message": message,
                        }
                    )
                else:
                    if success:
                        messages.success(
                            request,
                            f"Sale {sale.sale_number} completed and receipt printed!",
                        )
                    else:
                        messages.warning(
                            request,
                            f"Sale {sale.sale_number} completed but printing failed: {message}",
                        )
                    return redirect("sales:new_sale")
            elif payment and payment.status == "completed" and sale.completed_at:
                success, message = print_receipt(sale)

                if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                    return JsonResponse(
                        {
                            "success": True,
                            "sale_number": sale.sale_number,
                            "print_success": success,
                            "print_message": message,
                        }
                    )
                else:
                    if success:
                        messages.success(
                            request,
                            f"Sale {sale.sale_number} already completed. Receipt printed!",
                        )
                    else:
                        messages.warning(
                            request,
                            f"Sale {sale.sale_number} already completed but printing failed: {message}",
                        )
                    return redirect("sales:new_sale")

        if not mobile_number:
            messages.error(request, "Mobile number is required for M-PESA payment")
            return redirect("sales:process_sale", sale_id=sale.id)

        items = sale.items.all()
        subtotal = sum(item.quantity * item.unit_price for item in items)
        special_total = Decimal("0")
        if sale.sale_type == "SPECIAL":
            special_total = sum(
                ((item.product.special_price or item.unit_price) - item.unit_price)
                * item.quantity
                for item in items
            )
        total_amount = subtotal + special_total

        if total_amount <= 0:
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse(
                    {"success": False, "error": "Sale amount must be greater than 0"}
                )
            else:
                messages.error(request, "Sale amount must be greater than 0")
                return redirect("sales:process_sale", sale_id=sale.id)

        from payments.api import STKPushAPI
        import uuid
        from payments.models import Payment

        transaction_ref = f"SALE-{sale.sale_number}-{uuid.uuid4().hex[:6].upper()}"

        payment = Payment.objects.create(
            payment_type="mpesa",
            amount=total_amount,
            phone_number=mobile_number,
            status="pending",
            transaction_reference=transaction_ref,
            notes=f"Payment for Sale #{sale.sale_number}",
        )

        result = STKPushAPI.initiate_stk_push(
            mobile_number, float(total_amount), transaction_ref
        )

        if result["success"]:
            checkout_id = result["data"].get("checkout_request_id", "")
            if checkout_id:
                payment.checkout_request_id = checkout_id
                payment.save()

            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse(
                    {
                        "success": True,
                        "payment_initiated": True,
                        "transaction_reference": transaction_ref,
                        "message": "Payment initiated. Please check your phone and complete the payment.",
                    }
                )
            else:
                messages.info(
                    request,
                    "M-PESA payment initiated. Please complete the payment on your phone.",
                )
                return redirect("sales:process_sale", sale_id=sale.id)
        else:
            payment.delete()
            error_msg = result.get("message", "Failed to initiate M-PESA payment")
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse({"success": False, "error": error_msg})
            else:
                messages.error(request, error_msg)
                return redirect("sales:process_sale", sale_id=sale.id)

    elif payment_method == "Debt":
        if not customer_first_name or not customer_phone:
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse(
                    {
                        "success": False,
                        "error": "Customer first name and phone number are required for debt sales",
                    }
                )
            else:
                messages.error(
                    request,
                    "Customer first name and phone number are required for debt sales",
                )
                return redirect("sales:process_sale", sale_id=sale.id)

        sale.payment_method = payment_method
        sale.discount_amount = Decimal("0")
        sale.complete_sale()
        sale.money_received = None
        sale.change_amount = None
        sale.save()

        from payments.models import Payment, Debt
        import uuid

        transaction_ref = f"SALE-{sale.sale_number}-{uuid.uuid4().hex[:6].upper()}"
        payment = Payment.objects.create(
            payment_type="debt",
            amount=sale.final_amount,
            status="pending",
            transaction_reference=transaction_ref,
            notes=f"Debt payment for Sale #{sale.sale_number}",
        )

        Debt.objects.create(
            payment=payment,
            cashier=request.user,
            customer_first_name=customer_first_name,
            customer_second_name=customer_second_name or "",
            customer_phone=customer_phone,
            customer_email=customer_email or "",
            amount_owed=sale.final_amount,
            amount_paid=Decimal("0"),
            status="unpaid",
            notes=f"Debt for Sale #{sale.sale_number}. Cashier {request.user.get_full_name()} is responsible for collection.",
        )

        success, message = print_receipt(sale)

        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse(
                {
                    "success": True,
                    "sale_number": sale.sale_number,
                    "print_success": success,
                    "print_message": message,
                    "responsibility_message": f"You are responsible for collecting this debt from {customer_first_name}.",
                }
            )

        if success:
            messages.success(
                request, f"Sale {sale.sale_number} completed and receipt printed!"
            )
        else:
            messages.warning(
                request,
                f"Sale {sale.sale_number} completed but printing failed: {message}",
            )

        messages.warning(
            request,
            f"You are responsible for collecting this debt from {customer_first_name} {customer_second_name or ''}.",
        )

        return redirect("sales:new_sale")

    else:
        sale.payment_method = payment_method
        sale.discount_amount = Decimal("0")
        sale.complete_sale()
        sale.money_received = None
        sale.change_amount = None
        sale.save()

        from payments.models import Payment, Debt
        import uuid

        transaction_ref = f"SALE-{sale.sale_number}-{uuid.uuid4().hex[:6].upper()}"
        Payment.objects.create(
            payment_type="other",
            amount=sale.final_amount,
            status="completed",
            transaction_reference=transaction_ref,
            notes=f"Payment for Sale #{sale.sale_number}",
        )

        success, message = print_receipt(sale)

        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse(
                {
                    "success": True,
                    "sale_number": sale.sale_number,
                    "print_success": success,
                    "print_message": message,
                }
            )

        if success:
            messages.success(
                request, f"Sale {sale.sale_number} completed and receipt printed!"
            )
        else:
            messages.warning(
                request,
                f"Sale {sale.sale_number} completed but printing failed: {message}",
            )

        return redirect("sales:new_sale")


@require_http_methods(["POST"])
def scan_barcode(request, sale):
    if sale.is_held:
        return JsonResponse({"success": False, "error": "Sale is on hold"})

    barcode = request.POST.get("barcode", "").strip()

    if not barcode:
        return JsonResponse({"success": False, "error": "No barcode provided"})

    try:
        product = None
        product = Product.objects.filter(sku=barcode, is_active=True).first()
        if not product:
            barcode_obj = (
                Barcode.objects.filter(barcode=barcode, is_active=True)
                .select_related("product")
                .first()
            )
            if barcode_obj:
                product = barcode_obj.product
                if not product.is_active:
                    raise Product.DoesNotExist

        if not product:
            raise Product.DoesNotExist

        if sale.sale_type == "SPECIAL" and not product.special_price:
            return JsonResponse(
                {
                    "success": False,
                    "error": f"{product.name} has no special price for special sale",
                }
            )

        if sale.sale_type == "WHOLESALE" and product.wholesale_price:
            unit_price = product.wholesale_price
        elif sale.sale_type == "SPECIAL" and product.special_price:
            unit_price = product.special_price
        else:
            unit_price = product.selling_price

        existing_item = sale.items.filter(product=product).first()
        if existing_item:
            existing_item.quantity += 1
            existing_item.save()
            quantity = existing_item.quantity
            item_id = existing_item.id
        else:
            new_item = SaleItem.objects.create(
                sale=sale,
                product=product,
                quantity=1,
                unit_price=unit_price,
            )
            quantity = 1
            item_id = new_item.id

        items = sale.items.all()
        subtotal = sum(item.quantity * item.unit_price for item in items)
        special_total = Decimal("0")
        if sale.sale_type == "SPECIAL":
            special_total = sum(
                ((item.product.special_price or item.unit_price) - item.unit_price)
                * item.quantity
                for item in items
            )

        total_price = quantity * unit_price
        if sale.sale_type == "SPECIAL" and product.special_price:
            total_price = quantity * product.special_price

        return JsonResponse(
            {
                "success": True,
                "item_id": item_id,
                "product": {
                    "id": product.id,
                    "name": product.name,
                    "price": str(unit_price),
                    "quantity": quantity,
                    "total": str(total_price),
                },
                "totals": {
                    "items_count": items.count(),
                    "subtotal": str(subtotal),
                    "special_total": str(special_total),
                    "total": str(subtotal + special_total),
                },
            }
        )

    except Product.DoesNotExist:
        return JsonResponse({"success": False, "error": "Product not found"})
    except Exception as e:
        logger.error(f"Error scanning barcode: {str(e)}")
        return JsonResponse({"success": False, "error": str(e)})


@login_required
def reprint_receipt(request, sale_id):
    if not request.user.can_process_sales():
        return JsonResponse(
            {"success": False, "error": "You do not have permission to print receipts."}
        )

    sale = get_object_or_404(Sale, id=sale_id, completed_at__isnull=False)

    success, message = print_receipt(sale)

    if success:
        return JsonResponse(
            {"success": True, "message": "Receipt reprinted successfully"}
        )
    else:
        return JsonResponse({"success": False, "error": f"Print failed: {message}"})


@login_required
@require_http_methods(["GET"])
def test_printer_view(request):
    if not request.user.can_process_sales():
        return JsonResponse(
            {"success": False, "error": "You do not have permission to test printer."}
        )

    success, message = print_test_receipt()

    if success:
        return JsonResponse({"success": True, "message": message})
    else:
        return JsonResponse(
            {"success": False, "error": f"Test print failed: {message}"}
        )


@login_required
def hold_sale(request, sale):
    if sale.is_held:
        return JsonResponse({"success": False, "error": "Sale is already on hold"})
    else:
        sale.is_held = True
        sale.save()
        return JsonResponse(
            {
                "success": True,
                "message": f"Sale {sale.sale_number} has been put on hold",
            }
        )


@login_required
def recall_sale(request, sale):
    if not sale.is_held:
        return JsonResponse({"success": False, "error": "Sale is not on hold"})
    else:
        sale.is_held = False
        sale.save()
        return JsonResponse(
            {"success": True, "message": f"Sale {sale.sale_number} has been recalled"}
        )


@login_required
def assign_delivery(request, sale):
    if not request.user.can_process_sales():
        return JsonResponse({"success": False, "error": "Permission denied"})

    if sale.is_held:
        return JsonResponse({"success": False, "error": "Sale is on hold"})

    if not sale.items.exists():
        return JsonResponse(
            {"success": False, "error": "Cannot assign delivery for empty sale"}
        )

    delivery_guy_id = request.POST.get("delivery_guy_id")
    delivery_address = request.POST.get("delivery_address", "").strip()
    notes = request.POST.get("notes", "").strip()

    if not delivery_guy_id:
        return JsonResponse({"success": False, "error": "Delivery guy is required"})

    if not delivery_address:
        return JsonResponse({"success": False, "error": "Delivery address is required"})

    try:
        from users.models import User

        delivery_guy = User.objects.get(
            id=delivery_guy_id, role="delivery_guy", is_active=True
        )

        # Check if delivery guy has active delivery
        from delivery.models import Delivery

        active_delivery = Delivery.objects.filter(
            delivery_guy=delivery_guy, status__in=["assigned", "in_transit"]
        ).first()

        if active_delivery:
            return JsonResponse(
                {
                    "success": False,
                    "error": f"Delivery guy {delivery_guy.get_full_name()} is currently busy with another delivery",
                }
            )

        # Calculate total amount
        items = sale.items.all()
        subtotal = sum(item.quantity * item.unit_price for item in items)
        special_total = Decimal("0")
        if sale.sale_type == "SPECIAL":
            special_total = sum(
                ((item.product.special_price or item.unit_price) - item.unit_price)
                * item.quantity
                for item in items
            )
        total_amount = subtotal + special_total

        # Create delivery
        delivery = Delivery.objects.create(
            sale=sale,
            responsible_cashier=request.user,
            delivery_guy=delivery_guy,
            delivery_address=delivery_address,
            notes=notes,
            status="assigned",
            payment_status="pending",
        )

        # Update sale
        sale.payment_method = "Delivery"
        sale.discount_amount = Decimal("0")
        sale.complete_sale()
        sale.save()

        # Create payment record
        from payments.models import Payment
        import uuid

        transaction_ref = f"SALE-{sale.sale_number}-{uuid.uuid4().hex[:6].upper()}"
        Payment.objects.create(
            payment_type="delivery",
            amount=total_amount,
            status="pending",
            transaction_reference=transaction_ref,
            notes=f"Delivery payment for Sale #{sale.sale_number}",
        )

        # Print receipt
        success, message = print_receipt(sale)

        return JsonResponse(
            {
                "success": True,
                "sale_number": sale.sale_number,
                "delivery_number": delivery.delivery_number,
                "print_success": success,
                "print_message": message,
                "message": f"Delivery assigned to {delivery_guy.get_full_name()}",
            }
        )

    except User.DoesNotExist:
        return JsonResponse({"success": False, "error": "Delivery guy not found"})
    except Exception as e:
        logger.error(f"Error assigning delivery: {str(e)}")
        return JsonResponse({"success": False, "error": "Error assigning delivery"})


@login_required
def sales_history(request):
    if not request.user.can_process_sales():
        raise PermissionDenied("You do not have permission to view sales history.")

    sales = Sale.objects.filter(completed_at__isnull=False)

    search_query = request.GET.get("search", "").strip()
    if search_query:
        sales = sales.filter(
            Q(sale_number__icontains=search_query)
            | Q(cashier__username__icontains=search_query)
            | Q(sale_type__icontains=search_query)
            | Q(payment_method__icontains=search_query)
        )

    start_date = request.GET.get("start_date")
    end_date = request.GET.get("end_date")
    sort_by = request.GET.get("sort", "-completed_at")

    valid_sort_fields = [
        "sale_number",
        "-sale_number",
        "sale_type",
        "-sale_type",
        "cashier__username",
        "-cashier__username",
        "final_amount",
        "-final_amount",
        "payment_method",
        "-payment_method",
        "completed_at",
        "-completed_at",
    ]

    if sort_by not in valid_sort_fields:
        sort_by = "-completed_at"

    if start_date and start_date != "None":
        sales = sales.filter(completed_at__date__gte=start_date)
    if end_date and end_date != "None":
        sales = sales.filter(completed_at__date__lte=end_date)

    sales = sales.order_by(sort_by)

    paginator = Paginator(sales, 15)
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
        "start_date": start_date,
        "end_date": end_date,
        "current_sort": sort_by,
        "search_query": search_query,
    }
    return render(request, "sales/history.html", context)


@login_required
def sale_detail(request, sale_id):
    if not request.user.can_process_sales():
        raise PermissionDenied("You do not have permission to view sale details.")

    sale = get_object_or_404(Sale, id=sale_id, completed_at__isnull=False)
    sale_items = SaleItem.objects.filter(sale=sale).select_related("product")
    context = {
        "sale": sale,
        "sale_items": sale_items,
    }
    return render(request, "sales/sale_detail.html", context)


def public_receipt(request, sale_id):
    sale = get_object_or_404(Sale, id=sale_id, completed_at__isnull=False)
    receipt_data = format_receipt_data(sale)
    context = {
        "receipt_data": receipt_data,
        "sale_id": sale.id,
    }
    return render(request, "sales/receipt.html", context)


def sale_analytics(request):
    today = timezone.now().date()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)

    completed_sales = Sale.objects.filter(completed_at__isnull=False)

    today_sales = completed_sales.filter(completed_at__date=today).aggregate(
        total=Sum("final_amount"), count=Count("id")
    )

    week_sales = completed_sales.filter(completed_at__date__gte=week_ago).aggregate(
        total=Sum("final_amount"), count=Count("id")
    )

    month_sales = completed_sales.filter(completed_at__date__gte=month_ago).aggregate(
        total=Sum("final_amount"), count=Count("id")
    )

    total_sales = completed_sales.aggregate(
        total=Sum("final_amount"), count=Count("id"), avg=Avg("final_amount")
    )

    sales_by_type = (
        completed_sales.values("sale_type")
        .annotate(total=Sum("final_amount"), count=Count("id"))
        .order_by("-total")
    )

    daily_sales = (
        completed_sales.filter(completed_at__date__gte=week_ago)
        .annotate(day=TruncDate("completed_at"))
        .values("day")
        .annotate(total=Sum("final_amount"), count=Count("id"))
        .order_by("day")
    )

    top_products = (
        SaleItem.objects.filter(sale__completed_at__isnull=False)
        .values("product__name", "product__sold_count")
        .annotate(quantity=Sum("quantity"), revenue=Sum("total_amount"))
        .order_by("-quantity")[:10]
    )

    daily_list = []
    for item in daily_sales:
        daily_list.append(
            {
                "day": item["day"].strftime("%Y-%m-%d"),
                "total": float(item["total"] or 0),
                "count": item["count"],
            }
        )

    type_list = []
    for item in sales_by_type:
        type_list.append(
            {
                "sale_type": item["sale_type"],
                "total": float(item["total"] or 0),
                "count": item["count"],
            }
        )

    context = {
        "today_sales": today_sales,
        "week_sales": week_sales,
        "month_sales": month_sales,
        "total_sales": total_sales,
        "sales_by_type": json.dumps(type_list),
        "daily_sales": json.dumps(daily_list),
        "top_products": top_products,
    }

    return render(request, "sales/sale_analytics.html", context)


def sale_report(request):
    start_date = request.GET.get("start_date")
    end_date = request.GET.get("end_date")
    sale_type = request.GET.get("sale_type")
    cashier = request.GET.get("cashier")

    completed_sales = Sale.objects.filter(completed_at__isnull=False)

    if start_date:
        completed_sales = completed_sales.filter(completed_at__date__gte=start_date)
    if end_date:
        completed_sales = completed_sales.filter(completed_at__date__lte=end_date)
    if sale_type:
        completed_sales = completed_sales.filter(sale_type=sale_type)
    if cashier:
        completed_sales = completed_sales.filter(cashier_id=cashier)

    summary = completed_sales.aggregate(
        total_sales=Sum("final_amount"),
        total_count=Count("id"),
        avg_sale=Avg("final_amount"),
        total_discount=Sum("discount_amount"),
    )

    sales_list = completed_sales.select_related("cashier").prefetch_related("items")

    paginator = Paginator(sales_list, 20)
    page_number = request.GET.get("page", 1)
    try:
        page_number = int(page_number)
        if page_number < 1:
            page_number = 1
    except ValueError:
        page_number = 1
    page_obj = paginator.get_page(page_number)

    from django.contrib.auth import get_user_model

    User = get_user_model()
    cashiers = User.objects.filter(sale__isnull=False).distinct()

    context = {
        "summary": summary,
        "page_obj": page_obj,
        "cashiers": cashiers,
        "filters": {
            "start_date": start_date,
            "end_date": end_date,
            "sale_type": sale_type,
            "cashier": cashier,
        },
    }

    return render(request, "sales/sale_report.html", context)


def sale_trend(request):
    today = timezone.now().date()
    days_back = int(request.GET.get("days", 30))
    start_date = today - timedelta(days=days_back)

    completed_sales = Sale.objects.filter(
        completed_at__isnull=False, completed_at__date__gte=start_date
    )

    daily_trend = (
        completed_sales.annotate(day=TruncDate("completed_at"))
        .values("day")
        .annotate(total=Sum("final_amount"), count=Count("id"))
        .order_by("day")
    )

    hourly_trend = (
        completed_sales.annotate(hour=ExtractHour("completed_at"))
        .values("hour")
        .annotate(total=Sum("final_amount"), count=Count("id"))
        .order_by("hour")
    )

    type_trend = (
        completed_sales.values("sale_type")
        .annotate(total=Sum("final_amount"), count=Count("id"))
        .order_by("-total")
    )

    daily_list = []
    for item in daily_trend:
        daily_list.append(
            {
                "day": item["day"].strftime("%Y-%m-%d"),
                "total": float(item["total"] or 0),
                "count": item["count"],
            }
        )

    hourly_list = []
    for item in hourly_trend:
        hourly_list.append(
            {
                "hour": item["hour"],
                "total": float(item["total"] or 0),
                "count": item["count"],
            }
        )

    type_list = []
    for item in type_trend:
        type_list.append(
            {
                "sale_type": item["sale_type"],
                "total": float(item["total"] or 0),
                "count": item["count"],
            }
        )

    context = {
        "daily_trend": json.dumps(daily_list),
        "hourly_trend": json.dumps(hourly_list),
        "type_trend": json.dumps(type_list),
        "days_back": days_back,
    }

    return render(request, "sales/sale_trend.html", context)


@login_required
def return_start(request):
    if not request.user.can_process_sales():
        raise PermissionDenied("You do not have permission to process returns.")

    if request.method == "POST":
        form = ReturnStartForm(request.POST)
        if form.is_valid():
            sale_number = form.cleaned_data["sale_number"]
            sale = Sale.objects.get(sale_number=sale_number)
            return redirect("sales:return_process", sale_id=sale.id)
    else:
        form = ReturnStartForm()

    return render(request, "sales/return_start.html", {"form": form})


@login_required
def return_process(request, sale_id):
    if not request.user.can_process_sales():
        raise PermissionDenied("You do not have permission to process returns.")

    sale = get_object_or_404(Sale, id=sale_id, completed_at__isnull=False)
    sale_items = sale.items.select_related("product").all()

    sale_items_with_returns = []
    for item in sale_items:
        already_returned = (
            ReturnItem.objects.filter(sale_item=item).aggregate(total=Sum("quantity"))[
                "total"
            ]
            or 0
        )
        available = item.quantity - already_returned
        sale_items_with_returns.append(
            {"item": item, "already_returned": already_returned, "available": available}
        )

    if request.method == "POST":
        return_data = []
        total_return_amount = Decimal("0")
        has_items = False

        for key, value in request.POST.items():
            if key.startswith("confirm_") and value == "on":
                sale_item_id = key.replace("confirm_", "")
                quantity_key = f"quantity_{sale_item_id}"
                reason_key = f"reason_{sale_item_id}"
                quantity = int(request.POST.get(quantity_key, 1))
                reason = request.POST.get(reason_key, "FAULTY")

                try:
                    sale_item = SaleItem.objects.get(id=sale_item_id, sale=sale)
                    already_returned = (
                        ReturnItem.objects.filter(sale_item=sale_item).aggregate(
                            total=Sum("quantity")
                        )["total"]
                        or 0
                    )
                    available = sale_item.quantity - already_returned

                    if quantity > available:
                        messages.error(
                            request,
                            f"Cannot return more than {available} units of {sale_item.product.name} (already returned: {already_returned})",
                        )
                        break

                    if quantity > 0:
                        has_items = True
                        unit_price = sale_item.unit_price

                        return_data.append(
                            {
                                "sale_item_id": sale_item.id,
                                "quantity": quantity,
                                "return_reason": reason,
                                "unit_price": str(unit_price),
                                "total_price": str(quantity * unit_price),
                            }
                        )
                        total_return_amount += quantity * unit_price
                except SaleItem.DoesNotExist:
                    messages.error(request, "Invalid item selected")
                    break
        else:
            if not has_items:
                messages.error(request, "Please select at least one item to return.")
            else:
                request.session["return_data"] = {
                    "sale_id": sale.id,
                    "return_items": return_data,
                    "total_return_amount": str(total_return_amount),
                }
                return redirect("sales:return_confirm")

    request.session.pop("return_data", None)

    return_items = []
    total_return_amount = Decimal("0")

    import json

    sale_items_json = json.dumps(
        [
            {
                "id": sid["item"].id,
                "name": sid["item"].product.name,
                "sold_quantity": sid["item"].quantity,
                "already_returned": sid["already_returned"],
                "available": sid["available"],
                "unit_price": str(sid["item"].unit_price),
            }
            for sid in sale_items_with_returns
        ]
    )

    context = {
        "sale": sale,
        "sale_items_json": sale_items_json,
        "return_items": return_items,
        "return_items_json": json.dumps(return_items),
        "total_return_amount": total_return_amount,
    }
    return render(request, "sales/return_process.html", context)


@login_required
def return_confirm(request):
    if not request.user.can_process_sales():
        raise PermissionDenied("You do not have permission to process returns.")

    return_data = request.session.get("return_data")
    if not return_data:
        messages.error(request, "No return data found. Please start over.")
        return redirect("sales:return_start")

    sale = get_object_or_404(Sale, id=return_data["sale_id"])

    if request.method == "POST":
        return_obj = Return.objects.create(
            sale=sale,
            cashier=request.user,
            total_return_amount=Decimal(return_data["total_return_amount"]),
            notes=request.POST.get("notes", ""),
        )

        for item_data in return_data["return_items"]:
            sale_item = SaleItem.objects.get(id=item_data["sale_item_id"])
            ReturnItem.objects.create(
                return_fk=return_obj,
                sale_item=sale_item,
                quantity=item_data["quantity"],
                return_reason=item_data["return_reason"],
                unit_price=Decimal(item_data["unit_price"]),
                total_price=Decimal(item_data["total_price"]),
            )

            product = sale_item.product
            previous_quantity = product.quantity
            product.quantity += item_data["quantity"]
            product.save()

            StockMovement.objects.create(
                product=product,
                movement_type="RETURN",
                quantity=item_data["quantity"],
                previous_quantity=previous_quantity,
                new_quantity=product.quantity,
                notes=f"Return #{return_obj.return_number} - {item_data['return_reason']}",
            )

        del request.session["return_data"]

        messages.success(
            request, f"Return {return_obj.return_number} processed successfully."
        )
        return redirect("sales:history")

    return_items = []
    for item_data in return_data["return_items"]:
        sale_item = SaleItem.objects.select_related("product").get(
            id=item_data["sale_item_id"]
        )
        return_items.append(
            {
                "product": sale_item.product,
                "quantity": item_data["quantity"],
                "return_reason": item_data["return_reason"],
                "unit_price": Decimal(item_data["unit_price"]),
                "total_price": Decimal(item_data["total_price"]),
            }
        )

    context = {
        "sale": sale,
        "return_items": return_items,
        "total_return_amount": Decimal(return_data["total_return_amount"]),
    }
    return render(request, "sales/return_confirm.html", context)


@login_required
def get_delivery_guys(request):
    if not request.user.can_process_sales():
        return JsonResponse({"success": False, "error": "Permission denied"})

    search_term = request.GET.get("search", "").strip()

    from users.models import User
    from delivery.models import Delivery

    delivery_guys = User.objects.filter(role="delivery_guy", is_active=True)
    if search_term:
        delivery_guys = delivery_guys.filter(
            models.Q(username__icontains=search_term)
            | models.Q(first_name__icontains=search_term)
            | models.Q(last_name__icontains=search_term)
            | models.Q(phone_number__icontains=search_term)
        )
    active_deliveries = Delivery.objects.filter(
        delivery_guy__in=delivery_guys, status__in=["assigned", "in_transit"]
    ).select_related("delivery_guy")

    active_delivery_map = {d.delivery_guy_id: d for d in active_deliveries}

    result = []
    for guy in delivery_guys:
        active_delivery = active_delivery_map.get(guy.id)
        result.append(
            {
                "id": guy.id,
                "name": guy.get_full_name() or guy.username,
                "username": guy.username,
                "phone": guy.phone_number,
                "active_delivery": (
                    active_delivery.delivery_number if active_delivery else None
                ),
            }
        )

    return JsonResponse({"success": True, "delivery_guys": result})


@login_required
def returns_history(request):
    if not request.user.can_process_sales():
        raise PermissionDenied("You do not have permission to view returns history.")

    returns = Return.objects.select_related("sale", "cashier").prefetch_related("items")

    search_query = request.GET.get("search", "").strip()
    if search_query:
        returns = returns.filter(
            Q(return_number__icontains=search_query)
            | Q(sale__sale_number__icontains=search_query)
            | Q(cashier__username__icontains=search_query)
        )

    start_date = request.GET.get("start_date")
    end_date = request.GET.get("end_date")
    sort_by = request.GET.get("sort", "-created_at")

    valid_sort_fields = [
        "return_number",
        "-return_number",
        "sale__sale_number",
        "-sale__sale_number",
        "cashier__username",
        "-cashier__username",
        "total_return_amount",
        "-total_return_amount",
        "created_at",
        "-created_at",
    ]

    if sort_by not in valid_sort_fields:
        sort_by = "-created_at"

    if start_date and start_date != "None":
        returns = returns.filter(created_at__date__gte=start_date)
    if end_date and end_date != "None":
        returns = returns.filter(created_at__date__lte=end_date)

    returns = returns.order_by(sort_by)

    paginator = Paginator(returns, 15)
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
        "start_date": start_date,
        "end_date": end_date,
        "current_sort": sort_by,
        "search_query": search_query,
    }
    return render(request, "sales/returns_history.html", context)


@login_required
def return_detail(request, return_id):
    if not request.user.can_process_sales():
        raise PermissionDenied("You do not have permission to view return details.")

    return_obj = get_object_or_404(Return, id=return_id)
    return_items = ReturnItem.objects.filter(return_fk=return_obj).select_related("sale_item__product")
    context = {
        "return_obj": return_obj,
        "return_items": return_items,
    }
    return render(request, "sales/return_detail.html", context)


@login_required
def search_sale_product(request):
    if not request.user.can_process_sales():
        return JsonResponse({"success": False, "error": "Permission denied"})

    sale_id = request.GET.get("sale_id")
    query = request.GET.get("query", "").strip()

    if not sale_id or not query:
        return JsonResponse({"success": False, "error": "Missing parameters"})

    try:
        sale = Sale.objects.get(id=sale_id, completed_at__isnull=False)
        sale_items = sale.items.select_related("product").all()

        matching_items = []
        for item in sale_items:
            product = item.product
            if product.sku.upper() == query.upper() or any(
                barcode.barcode.upper() == query.upper()
                for barcode in product.barcodes.filter(is_active=True)
            ):
                matching_items.append(
                    {
                        "sale_item_id": item.id,
                        "name": product.name,
                        "sold_quantity": item.quantity,
                        "unit_price": str(item.unit_price),
                    }
                )

        return JsonResponse({"success": True, "products": matching_items})

    except Sale.DoesNotExist:
        return JsonResponse({"success": False, "error": "Sale not found"})
    except Exception as e:
        logger.error(f"Error searching sale product: {str(e)}")
        return JsonResponse({"success": False, "error": "Search failed"})