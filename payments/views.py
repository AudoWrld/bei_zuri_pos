import uuid
import json
import logging
from decimal import Decimal
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.utils import timezone
from django.db.models import Q
from .models import Payment
from .api import STKPushAPI
from datetime import timedelta
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib import messages
from .models import Debt

logger = logging.getLogger(__name__)
payment_logger = logging.getLogger("payment")


@login_required
def initiate_payment_view(request):
    if request.method != "POST":
        return JsonResponse(
            {"success": False, "error": "Method not allowed"}, status=405
        )

    try:
        logger.critical(f"RAW POST DATA: {dict(request.POST)}")

        amount = request.POST.get("amount")
        phone_number = request.POST.get("phone_number")
        sale_id = request.POST.get("sale_id")
        notes = request.POST.get("note", "")

        if not all([amount, phone_number, sale_id]):
            logger.error(
                f"Missing parameters - amount={amount}, phone={phone_number}, sale_id={sale_id}"
            )
            return JsonResponse(
                {"success": False, "error": "Missing required parameters"}, status=400
            )

        try:
            amount = Decimal(str(amount))
        except Exception:
            return JsonResponse(
                {"success": False, "error": "Invalid amount format"}, status=400
            )

        from sales.models import Sale

        try:
            sale = Sale.objects.get(id=sale_id)
            logger.info(
                f"Processing payment for Sale #{sale.sale_number} by cashier {sale.cashier.username}"
            )
        except Sale.DoesNotExist:
            logger.error(f"Sale {sale_id} not found")
            return JsonResponse(
                {"success": False, "error": "Sale not found"}, status=404
            )

        transaction_reference = (
            f"SALE-{sale.sale_number}-{uuid.uuid4().hex[:6].upper()}"
        )

        payment = Payment.objects.create(
            payment_type="mpesa",
            amount=amount,
            phone_number=phone_number,
            status="pending",
            transaction_reference=transaction_reference,
            notes=notes or f"Payment for Sale #{sale.sale_number}",
        )

        logger.info(
            f"INITIATING PAYMENT - Ref: {transaction_reference}, Sale: {sale.sale_number}, Amount: {amount}"
        )

        try:
            result = STKPushAPI.initiate_stk_push(
                phone_number, float(amount), transaction_reference
            )

            if result["success"]:
                checkout_id = result["data"].get("checkout_request_id", "")
                if checkout_id:
                    payment.checkout_request_id = checkout_id
                    payment.save()
                    logger.info(
                        f"Stored checkout_request_id: {checkout_id} for payment {payment.id}"
                    )

                return JsonResponse(
                    {
                        "success": True,
                        "transaction_reference": transaction_reference,
                        "checkout_request_id": checkout_id,
                        "sale_id": sale.id,
                        "message": "Payment initiated successfully. Check your phone.",
                    }
                )
            else:
                payment.delete()
                error_msg = result.get("message", "Unknown error")
                logger.error(f"STK Push failed: {error_msg}")

                return JsonResponse(
                    {
                        "success": False,
                        "error": "Unable to send payment request. Please try again.",
                    },
                    status=400,
                )
        except Exception as stk_error:
            logger.error(f"STK Push exception: {str(stk_error)}", exc_info=True)
            payment.delete()
            return JsonResponse(
                {
                    "success": False,
                    "error": "Unable to send payment request. Please try again.",
                },
                status=500,
            )

    except Exception as e:
        logger.error(f"Error initiating payment: {str(e)}", exc_info=True)
        return JsonResponse(
            {
                "success": False,
                "error": "Payment could not be processed. Please try again later.",
            },
            status=500,
        )


@login_required
def check_payment_status(request):
    transaction_reference = request.GET.get("transaction_reference")

    if not transaction_reference:
        return JsonResponse(
            {"success": False, "error": "Transaction reference required"}, status=400
        )

    try:
        payment = Payment.objects.filter(
            transaction_reference=transaction_reference
        ).first()

        if not payment:
            return JsonResponse(
                {"status": "PENDING", "message": "Payment verification in progress"},
                status=200,
            )

        payment.refresh_from_db()

        if payment.status == "pending" and payment.checkout_request_id:
            logger.info(
                f"Checking HashPay status for checkout_id: {payment.checkout_request_id}"
            )

            api_result = STKPushAPI.check_transaction_status(
                payment.checkout_request_id
            )

            if api_result.get("success"):
                if api_result.get("is_complete"):
                    result_data = api_result.get("data", {})
                    payment.status = "completed"
                    payment.mpesa_receipt_number = result_data.get(
                        "MpesaReceiptNumber", ""
                    )
                    payment.notes = f"Payment completed via status check. {result_data.get('ResultDesc', '')}"
                    payment.save()

                    logger.info(
                        f"Payment {payment.transaction_reference} marked as completed via status check"
                    )
                elif api_result.get("is_failed"):
                    result_data = api_result.get("data", {})
                    payment.status = "failed"
                    payment.notes = f"Payment failed: {result_data.get('ResultDesc', 'Unknown error')}"
                    payment.save()

                    logger.warning(
                        f"Payment {payment.transaction_reference} marked as failed via status check"
                    )
                elif api_result.get("is_pending"):
                    result_data = api_result.get("data", {})
                    logger.info(
                        f"Payment {payment.transaction_reference} still pending: {result_data.get('ResultDesc', 'Processing')}"
                    )

        if payment.status == "completed":
            return JsonResponse(
                {
                    "status": "SUCCESS",
                    "amount": str(payment.amount),
                    "transaction_reference": payment.transaction_reference,
                    "mpesa_receipt": payment.mpesa_receipt_number or "",
                    "message": "Payment successful",
                }
            )
        elif payment.status == "failed":
            return JsonResponse(
                {
                    "status": "FAILED",
                    "amount": str(payment.amount),
                    "transaction_reference": payment.transaction_reference,
                    "message": payment.notes or "Payment failed",
                }
            )
        else:
            return JsonResponse(
                {
                    "status": "PENDING",
                    "amount": str(payment.amount),
                    "transaction_reference": payment.transaction_reference,
                    "message": "Payment still processing",
                }
            )

    except Exception as e:
        logger.error(f"Error checking payment status: {str(e)}", exc_info=True)
        return JsonResponse(
            {"status": "PENDING", "message": "Status check in progress"}, status=200
        )


@csrf_exempt
def payment_callback(request):
    if request.method != "POST":
        return JsonResponse(
            {"status": "error", "message": "Method not allowed"}, status=405
        )

    try:
        raw_payload = request.body.decode("utf-8")
        data = json.loads(raw_payload)
        logger.critical(f"PAYMENT CALLBACK RECEIVED: {data}")
        payment_logger.critical(f"HASHPAY WEBHOOK: {json.dumps(data, indent=2)}")

        response_data = data.get("response", data)

        checkout_request_id = response_data.get(
            "CheckoutRequestID"
        ) or response_data.get("checkout_request_id", "")
        merchant_request_id = response_data.get(
            "MerchantRequestID"
        ) or response_data.get("merchant_request_id", "")

        result_code = response_data.get("ResultCode")
        if result_code is None:
            result_code = response_data.get("ResponseCode")
        result_code = str(result_code) if result_code is not None else ""

        result_desc = (
            response_data.get("ResultDesc")
            or response_data.get("ResponseDescription")
            or response_data.get("result_desc", "")
        )
        mpesa_receipt = (
            response_data.get("TransactionReceipt")
            or response_data.get("MpesaReceiptNumber")
            or response_data.get("mpesa_receipt_number", "")
        )
        amount = (
            response_data.get("TransactionAmount")
            or response_data.get("Amount")
            or response_data.get("amount", 0)
        )
        phone = (
            response_data.get("Msisdn")
            or response_data.get("PhoneNumber")
            or response_data.get("phone_number", "")
        )

        with transaction.atomic():
            payment = None

            if checkout_request_id:
                payment = (
                    Payment.objects.select_for_update()
                    .filter(checkout_request_id=checkout_request_id)
                    .first()
                )
                if payment:
                    logger.info(
                        f"Found payment by checkout_request_id: {checkout_request_id}"
                    )

            if not payment and phone:
                normalized_phone = str(phone)[-9:]
                payment = (
                    Payment.objects.select_for_update()
                    .filter(phone_number__endswith=normalized_phone, status="pending")
                    .order_by("-created_at")
                    .first()
                )
                if payment:
                    logger.info(f"Found payment by phone number: {phone}")

            if not payment:
                logger.error(
                    f"PAYMENT NOT FOUND - Checkout: {checkout_request_id}, Phone: {phone}"
                )
                return JsonResponse(
                    {"status": "error", "message": "Payment not found"}, status=404
                )

            logger.info(
                f"PROCESSING WEBHOOK for Payment ID: {payment.id}, Ref: {payment.transaction_reference}"
            )

            if result_code == "0":
                payment.status = "completed"
                if amount:
                    payment.amount = Decimal(str(amount))
                if mpesa_receipt:
                    payment.mpesa_receipt_number = mpesa_receipt

                from sales.models import Sale

                sale_parts = payment.transaction_reference.split("-")
                if len(sale_parts) >= 2:
                    sale_number = "-".join(sale_parts[1:3])
                    sale = Sale.objects.filter(sale_number=sale_number).first()

                    if sale and not sale.completed_at:
                        sale.payment_method = "M-Pesa"
                        sale.complete_sale()

                        payment.notes = f"Payment for Sale #{sale.sale_number} received. Receipt: {mpesa_receipt}"
                        payment.save()

                        logger.info(
                            f"Sale #{sale.sale_number} completed with M-PESA payment {mpesa_receipt}"
                        )
                    else:
                        payment.notes = (
                            f"Payment received. Receipt: {mpesa_receipt}. {result_desc}"
                        )
                        payment.save()
                        if sale:
                            logger.warning(f"Sale {sale_number} already completed")
                        else:
                            logger.warning(f"Sale {sale_number} not found for payment")
                else:
                    payment.notes = (
                        f"Payment received. Receipt: {mpesa_receipt}. {result_desc}"
                    )
                    payment.save()
                    logger.warning(
                        f"Could not extract sale number from reference: {payment.transaction_reference}"
                    )

            else:
                payment.status = "failed"
                payment.notes = f"Payment failed: {result_desc} (Code: {result_code})"
                payment.save()
                logger.warning(
                    f"Payment {payment.transaction_reference} marked as FAILED: {result_desc}"
                )

            return JsonResponse(
                {"status": "success", "message": "Callback processed successfully"}
            )

    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in callback: {str(e)}")
        return JsonResponse({"status": "error", "message": "Invalid JSON"}, status=400)
    except Exception as e:
        logger.error(f"ERROR processing payment callback: {str(e)}", exc_info=True)
        return JsonResponse(
            {"status": "error", "message": "Internal error"}, status=500
        )


@login_required
def payment_list(request):
    payments = Payment.objects.all()

    search_query = request.GET.get("search", "").strip()
    if search_query:
        payments = payments.filter(
            Q(transaction_reference__icontains=search_query)
            | Q(notes__icontains=search_query)
            | Q(mpesa_receipt_number__icontains=search_query)
        )

    sort_by = request.GET.get("sort", "-created_at")

    valid_sort_fields = [
        "transaction_reference",
        "-transaction_reference",
        "payment_type",
        "-payment_type",
        "amount",
        "-amount",
        "phone_number",
        "-phone_number",
        "status",
        "-status",
        "mpesa_receipt_number",
        "-mpesa_receipt_number",
        "created_at",
        "-created_at",
    ]

    if sort_by not in valid_sort_fields:
        sort_by = "-created_at"

    payments = payments.order_by(sort_by)

    from django.core.paginator import Paginator

    paginator = Paginator(payments, 15)
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
        "current_sort": sort_by,
        "search_query": search_query,
    }

    return render(request, "payments/payment_list.html", context)


@login_required
def debt_list(request):
    if request.user.is_cashier():
        debts = Debt.objects.filter(cashier=request.user)
    else:
        debts = Debt.objects.all()

    search_query = request.GET.get("search", "").strip()
    if search_query:
        debts = debts.filter(
            Q(customer_first_name__icontains=search_query)
            | Q(customer_second_name__icontains=search_query)
            | Q(customer_email__icontains=search_query)
            | Q(customer_phone__icontains=search_query)
            | Q(payment__transaction_reference__icontains=search_query)
        )

    sort_by = request.GET.get("sort", "-created_at")

    valid_sort_fields = [
        "customer_first_name",
        "-customer_first_name",
        "customer_second_name",
        "-customer_second_name",
        "customer_email",
        "-customer_email",
        "customer_phone",
        "-customer_phone",
        "amount_owed",
        "-amount_owed",
        "amount_paid",
        "-amount_paid",
        "status",
        "-status",
        "cashier__username",
        "-cashier__username",
        "created_at",
        "-created_at",
    ]

    if sort_by not in valid_sort_fields:
        sort_by = "-created_at"

    debts = debts.order_by(sort_by)

    from django.core.paginator import Paginator

    paginator = Paginator(debts, 15)
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
        "current_sort": sort_by,
        "search_query": search_query,
    }

    return render(request, "payments/debt_list.html", context)
