import usb.core
import usb.util
import logging
import json
import os
from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from decimal import Decimal
import pytz

logger = logging.getLogger(__name__)


def load_printer_config():
    config_path = os.path.join(os.path.dirname(__file__), "printer_config.json")

    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            config = json.load(f)
            return (
                int(config["vendor_id"], 16),
                int(config["product_id"], 16),
                int(config["out_endpoint"], 16),
            )

    return 0x0483, 0x5743, 0x01


VENDOR_ID, PRODUCT_ID, OUT_ENDPOINT = load_printer_config()

ESC = b"\x1b"
GS = b"\x1d"

INIT = ESC + b"@"
ALIGN_LEFT = ESC + b"a\x00"
ALIGN_CENTER = ESC + b"a\x01"
ALIGN_RIGHT = ESC + b"a\x02"
BOLD_ON = ESC + b"E\x01"
BOLD_OFF = ESC + b"E\x00"
UNDERLINE_ON = ESC + b"-\x01"
UNDERLINE_OFF = ESC + b"-\x00"
DOUBLE_HEIGHT = GS + b"!\x01"
NORMAL_SIZE = GS + b"!\x00"
CUT_PAPER = GS + b"V\x41\x03"
LINE_FEED = b"\n"
SET_LEFT_MARGIN = b"\x1d\x4c"


def find_printer():
    try:
        dev = usb.core.find(idVendor=VENDOR_ID, idProduct=PRODUCT_ID)

        if dev is None:
            logger.error(
                f"Printer not found (VID: {hex(VENDOR_ID)}, PID: {hex(PRODUCT_ID)})"
            )
            return None

        try:
            dev.set_configuration()
            logger.info("Printer configured successfully")
        except usb.core.USBError as e:
            logger.warning(f"Could not set configuration: {e}")

        try:
            usb.util.claim_interface(dev, 0)
            logger.info("Interface claimed successfully")
        except usb.core.USBError as e:
            logger.warning(f"Could not claim interface: {e}")

        return dev

    except Exception as e:
        logger.error(f"Error finding printer: {e}")
        return None


def print_data(data):
    try:
        dev = find_printer()
        if dev is None:
            return False, "Printer not found"

        dev.write(OUT_ENDPOINT, data)
        logger.info("Data sent to printer successfully")

        try:
            usb.util.release_interface(dev, 0)
        except:
            pass

        return True, "Print successful"

    except usb.core.USBError as e:
        logger.error(f"USB Error: {e}")
        return False, f"USB Error: {str(e)}"

    except Exception as e:
        logger.error(f"Print error: {e}")
        return False, f"Error: {str(e)}"


def format_line(left, right, width=48):
    available = width - len(left) - len(right)
    spaces = " " * max(available, 1)
    return left + spaces + right


def truncate_text(text, max_length):
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."


def format_item_line(name, qty, price, total):
    name_width = 22
    qty_width = 3
    price_width = 10
    total_width = 10
    spacing = 1

    truncated_name = truncate_text(name, name_width)
    name_part = truncated_name.ljust(name_width)
    qty_part = str(qty).rjust(qty_width)
    price_part = str(price).rjust(price_width)
    total_part = str(total).rjust(total_width)

    return (
        name_part
        + " " * spacing
        + qty_part
        + " " * spacing
        + price_part
        + " " * spacing
        + total_part
    )


def generate_qr_code(data):
    commands = bytearray()
    commands.extend(b"\x1d\x28\x6b\x04\x00\x31\x41\x32\x00")
    commands.extend(b"\x1d\x28\x6b\x03\x00\x31\x43\x06")
    commands.extend(b"\x1d\x28\x6b\x03\x00\x31\x45\x30")
    qr_len = len(data) + 3
    pl = qr_len % 256
    ph = qr_len // 256
    commands.extend(bytes([0x1D, 0x28, 0x6B, pl, ph, 0x31, 0x50, 0x30]) + data.encode())
    commands.extend(b"\x1d\x28\x6b\x03\x00\x31\x51\x30")
    return bytes(commands)


def build_receipt(receipt_data):
    receipt = bytearray()

    receipt.extend(INIT)
    receipt.extend(SET_LEFT_MARGIN + b"\x00\x00")

    receipt.extend(ALIGN_CENTER)
    receipt.extend(BOLD_ON)
    receipt.extend(DOUBLE_HEIGHT)
    receipt.extend(receipt_data["shop_name"].encode("utf-8"))
    receipt.extend(LINE_FEED)
    receipt.extend(NORMAL_SIZE)
    receipt.extend(BOLD_OFF)

    receipt.extend(receipt_data["address"].encode("utf-8"))
    receipt.extend(LINE_FEED)
    receipt.extend(receipt_data["phone"].encode("utf-8"))
    receipt.extend(LINE_FEED)
    receipt.extend(LINE_FEED)

    receipt.extend(ALIGN_LEFT)
    receipt.extend(b"-" * 48)
    receipt.extend(LINE_FEED)

    receipt.extend(format_line("Sale No:", receipt_data["sale_number"]).encode("utf-8"))
    receipt.extend(LINE_FEED)
    receipt.extend(format_line("Date:", receipt_data["date"]).encode("utf-8"))
    receipt.extend(LINE_FEED)
    receipt.extend(format_line("Type:", receipt_data["sale_type"]).encode("utf-8"))
    receipt.extend(LINE_FEED)
    receipt.extend(format_line("Cashier:", receipt_data["cashier"]).encode("utf-8"))
    receipt.extend(LINE_FEED)
    receipt.extend(
        format_line("Payment:", receipt_data["payment_method"]).encode("utf-8")
    )
    receipt.extend(LINE_FEED)

    receipt.extend(b"-" * 48)
    receipt.extend(LINE_FEED)
    receipt.extend(LINE_FEED)

    receipt.extend(BOLD_ON)
    header = format_item_line("Item", "Qty", "Price", "Total")
    receipt.extend(header.encode("utf-8"))
    receipt.extend(LINE_FEED)
    receipt.extend(BOLD_OFF)
    receipt.extend(b"-" * 48)
    receipt.extend(LINE_FEED)

    for item in receipt_data["items"]:
        item_line = format_item_line(
            item["name"], item["quantity"], item["unit_price"], item["total"]
        )
        receipt.extend(item_line.encode("utf-8"))
        receipt.extend(LINE_FEED)

    receipt.extend(b"-" * 48)
    receipt.extend(LINE_FEED)
    receipt.extend(LINE_FEED)

    receipt.extend(ALIGN_RIGHT)
    receipt.extend(
        format_line("", f"Subtotal: {receipt_data['subtotal']}").encode("utf-8")
    )
    receipt.extend(LINE_FEED)

    if float(receipt_data.get("special_amount", 0)) != 0:
        receipt.extend(
            format_line(
                "", f"Special Discount: {receipt_data['special_amount']}"
            ).encode("utf-8")
        )
        receipt.extend(LINE_FEED)

    if float(receipt_data.get("discount_amount", 0)) != 0:
        receipt.extend(
            format_line("", f"Discount: {receipt_data['discount_amount']}").encode(
                "utf-8"
            )
        )
        receipt.extend(LINE_FEED)

    receipt.extend(ALIGN_LEFT)
    receipt.extend(b"=" * 48)
    receipt.extend(LINE_FEED)

    receipt.extend(BOLD_ON)
    receipt.extend(DOUBLE_HEIGHT)
    receipt.extend(format_line("TOTAL:", receipt_data["total"]).encode("utf-8"))
    receipt.extend(LINE_FEED)
    receipt.extend(NORMAL_SIZE)
    receipt.extend(BOLD_OFF)

    receipt.extend(b"=" * 48)
    receipt.extend(LINE_FEED)
    receipt.extend(LINE_FEED)

    if receipt_data.get("payment_method") == "Cash":
        if receipt_data.get("money_received"):
            receipt.extend(ALIGN_RIGHT)
            receipt.extend(
                format_line("", f"Paid: {receipt_data['money_received']}").encode(
                    "utf-8"
                )
            )
            receipt.extend(LINE_FEED)

        if (
            receipt_data.get("change_amount")
            and float(receipt_data["change_amount"]) > 0
        ):
            receipt.extend(ALIGN_RIGHT)
            receipt.extend(
                format_line("", f"Change: {receipt_data['change_amount']}").encode(
                    "utf-8"
                )
            )
            receipt.extend(LINE_FEED)

    receipt.extend(LINE_FEED)
    receipt.extend(ALIGN_CENTER)
    receipt.extend(b"'" * 32)
    receipt.extend(LINE_FEED)
    receipt.extend(LINE_FEED)

    try:
        qr_data = receipt_data.get("qr_code_data", "http://localhost:8080")
        receipt.extend(generate_qr_code(qr_data))
        receipt.extend(LINE_FEED)
        receipt.extend(b"Scan for details\n")
    except Exception as e:
        logger.error(f"QR code generation failed: {e}")

    receipt.extend(LINE_FEED)
    receipt.extend(b"Thank you for your purchase!\n")
    receipt.extend(b"Please come again\n")
    receipt.extend(b"Goods once sold will not be re-accepted\n")
    receipt.extend(LINE_FEED)
    receipt.extend(LINE_FEED)
    receipt.extend(LINE_FEED)

    receipt.extend(CUT_PAPER)

    return bytes(receipt)


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
        "special_amount": (
            f"{sale.special_amount:.2f}" if sale.special_amount else "0.00"
        ),
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
        receipt_bytes = build_receipt(receipt_data)

        success, message = print_data(receipt_bytes)

        if success:
            logger.info(f"Receipt printed for sale {sale.sale_number}")
            return True, "Receipt printed successfully"
        else:
            logger.error(f"Print failed for sale {sale.sale_number}: {message}")
            return False, message

    except Exception as e:
        logger.error(f"Unexpected print error for sale {sale.sale_number}: {str(e)}")
        return False, f"Print error: {str(e)}"


def check_printer_status():
    try:
        dev = find_printer()

        if dev is None:
            return False, "Printer not found. Please check USB connection."

        try:
            usb.util.release_interface(dev, 0)
        except:
            pass

        return True, "Printer is ready"

    except Exception as e:
        logger.error(f"Error checking status: {e}")
        return False, str(e)


def print_test_receipt():
    from datetime import datetime

    try:
        test_receipt = {
            "shop_name": "BEIZURI",
            "address": "Bondo Town, Siaya",
            "phone": "Tel: +254 785 053 060",
            "sale_number": "TEST-001",
            "date": datetime.now().strftime("%d/%m/%Y %H:%M"),
            "sale_type": "Test",
            "cashier": "System",
            "items": [
                {
                    "name": "Test Item 1",
                    "quantity": 2,
                    "unit_price": "100.00",
                    "total": "200.00",
                },
                {
                    "name": "Test Item 2 With Very Long Name That Needs Truncation",
                    "quantity": 1,
                    "unit_price": "50.00",
                    "total": "50.00",
                },
            ],
            "subtotal": "250.00",
            "special_amount": "0.00",
            "discount_amount": "0.00",
            "total": "250.00",
            "payment_method": "Cash",
            "qr_code_data": "http://localhost:8080",
        }

        receipt_bytes = build_receipt(test_receipt)
        success, message = print_data(receipt_bytes)

        if success:
            return True, "Test receipt printed successfully"
        else:
            return False, message

    except Exception as e:
        logger.error(f"Error printing test receipt: {e}")
        return False, str(e)
