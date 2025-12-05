import requests
import logging
from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from decimal import Decimal
import pytz

logger = logging.getLogger(__name__)

PRINT_SERVER_URL = getattr(settings, "PRINT_SERVER_URL", "http://localhost:8080")


def format_receipt_data(sale):
    items = []
    for item in sale.items.all():
        items.append(
            {
                "name": item.product.name,
                "quantity": item.quantity,
                "unit_price": f"{item.unit_price:.2f}",
                "total": f"{item.total_amount:.2f}",
            }
        )

    ke_tz = pytz.timezone("Africa/Nairobi")
    completed_at_ke = sale.completed_at.astimezone(ke_tz)

    receipt = {
        "shop_name": "BEIZURI",
        "address": "Bondo Town, Siaya",
        "phone": "Tel: +254 785 053 060",
        "sale_number": sale.sale_number,
        "date": completed_at_ke.strftime("%d/%m/%Y %H:%M"),
        "sale_type": sale.get_sale_type_display(),
        "cashier": sale.cashier.get_full_name() or sale.cashier.username,
        "items": items,
        "subtotal": f"{sale.total_amount:.2f}",
        "special_amount": f"{sale.special_amount:.2f}" if sale.special_amount else "0.00",
        "discount_amount": (
            f"{sale.discount_amount:.2f}" if sale.discount_amount else "0.00"
        ),
        "total": f"{sale.final_amount:.2f}",
        "payment_method": sale.payment_method or "Cash",
        "money_received": f"{sale.money_received:.2f}" if sale.money_received else None,
        "change_amount": f"{sale.change_amount:.2f}" if sale.change_amount else "0.00",
        "qr_code_data": f"{settings.RECEIPT_BASE_URL}{reverse('sales:public_receipt', args=[sale.id])}",
    }

    return receipt


def print_receipt(sale, timeout=5):
    try:
        receipt_data = format_receipt_data(sale)

        response = requests.post(
            f"{PRINT_SERVER_URL}/print",
            json={"receipt": receipt_data},
            timeout=timeout,
            headers={"Content-Type": "application/json"},
        )

        if response.status_code == 200:
            result = response.json()
            if result.get("success"):
                logger.info(f"Receipt printed for sale {sale.sale_number}")
                return True, "Receipt printed successfully"
            else:
                error_msg = result.get("error", "Unknown error")
                logger.error(f"Print failed for sale {sale.sale_number}: {error_msg}")
                return False, error_msg
        else:
            logger.error(f"Print server returned status {response.status_code}")
            return False, f"Print server error: {response.status_code}"

    except requests.exceptions.ConnectionError:
        logger.warning(f"Print server not accessible for sale {sale.sale_number}")
        return False, "Print server not running. Please start the print service."

    except requests.exceptions.Timeout:
        logger.warning(f"Print timeout for sale {sale.sale_number}")
        return False, "Print request timed out"

    except Exception as e:
        logger.error(f"Unexpected print error for sale {sale.sale_number}: {str(e)}")
        return False, f"Print error: {str(e)}"


def check_printer_status():
    try:
        response = requests.get(f"{PRINT_SERVER_URL}/status", timeout=3)

        if response.status_code == 200:
            result = response.json()
            return result.get("success", False), result.get("message", "Unknown status")
        else:
            return False, f"Server returned status {response.status_code}"

    except requests.exceptions.ConnectionError:
        return False, "Print server not running"

    except Exception as e:
        return False, str(e)


def print_test_receipt():
    try:
        response = requests.get(f"{PRINT_SERVER_URL}/test", timeout=5)

        if response.status_code == 200:
            result = response.json()
            if result.get("success"):
                return True, "Test receipt printed successfully"
            else:
                return False, result.get("error", "Test print failed")
        else:
            return False, f"Server error: {response.status_code}"

    except requests.exceptions.ConnectionError:
        return False, "Print server not running"

    except Exception as e:
        return False, str(e)
