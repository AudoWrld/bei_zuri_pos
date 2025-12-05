import usb.core
import usb.util
import time
import datetime
import json
import os
from decimal import Decimal
from django.utils import timezone


def load_printer_config():
    config_path = os.path.join(os.path.dirname(__file__), "printer_config.json")

    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            config = json.load(f)
            return {
                "vendor_id": int(config["vendor_id"], 16),
                "product_id": int(config["product_id"], 16),
                "out_ep": int(config["out_endpoint"], 16),
            }

    return {"vendor_id": 0x0483, "product_id": 0x5743, "out_ep": 0x01}


class ThermalPrinter:

    def __init__(self):
        self.dev = None
        self.config = load_printer_config()

    def connect(self):
        try:
            self.dev = usb.core.find(
                idVendor=self.config["vendor_id"], idProduct=self.config["product_id"]
            )

            if self.dev is None:
                return False, "Printer not found. Please check USB connection."

            try:
                self.dev.set_configuration()
            except:
                pass

            try:
                usb.util.claim_interface(self.dev, 0)
                return True, "Printer connected successfully"
            except Exception as e:
                return False, f"Failed to claim printer interface: {str(e)}"

        except Exception as e:
            return False, f"Connection error: {str(e)}"

    def disconnect(self):
        if self.dev:
            try:
                usb.util.release_interface(self.dev, 0)
            except:
                pass

    def print_raw(self, data):
        if not self.dev:
            return False

        try:
            self.dev.write(self.config["out_ep"], data)
            time.sleep(0.5)
            return True
        except Exception as e:
            print(f"Print error: {e}")
            return False


def format_receipt_commands(sale):
    LINE_WIDTH = 30
    ITEM_WIDTH = 40
    commands = []

    commands.append(b"\x1b\x40")
    commands.append(b"\x1b\x33\x00")
    commands.append(bytes([0x1D, 0x5C, 0x00, 0x00]))

    commands.append(b"\x1b\x61\x01")
    commands.append(b"\x1b\x21\x10")
    commands.append(b"BEIZURI\n")
    commands.append(b"\x1b\x21\x00")
    commands.append(b"Bondo Town, Siaya\n")
    commands.append(b"Tel: +254 785 053 060\n\n")

    commands.append(b"\x1b\x61\x00")
    commands.append(b"-" * LINE_WIDTH + b"\n")

    date_str = timezone.localtime(sale.completed_at).strftime("%d/%m/%Y %H:%M")
    commands.append(f"Date: {date_str}\n".encode())
    commands.append(f"Receipt: {sale.sale_number}\n".encode())
    commands.append(f"Type: {sale.get_sale_type_display()}\n".encode())

    cashier_name = sale.cashier.get_full_name() or sale.cashier.username
    commands.append(f"Cashier: {cashier_name}\n".encode())
    commands.append(b"-" * LINE_WIDTH + b"\n")

    total_deduction = Decimal("0")
    for item in sale.items.all():
        name = item.product.name
        qty = item.quantity
        price = float(item.unit_price)
        total = float(item.total_amount)

        if len(name) > 35:
            name = name[:32] + "..."

        commands.append(name.encode() + b"\n")

        price_line = f"  {qty} x KSh{price:.2f}"
        total_line = f"KSh{total:.2f}"
        spaces_needed = ITEM_WIDTH - len(price_line) - len(total_line)
        spaces_needed = max(1, spaces_needed)

        line = price_line + (" " * spaces_needed) + total_line + "\n"
        commands.append(line.encode())

        if sale.sale_type == "SPECIAL":
            deduction = (item.unit_price - item.product.special_price) * item.quantity
            total_deduction += deduction

    commands.append(b"-" * LINE_WIDTH + b"\n")

    def format_total_line(label, value):
        value_str = f"KSh{float(value):.2f}"
        spaces = LINE_WIDTH - len(label) - len(value_str)
        spaces = max(1, spaces)
        return (label + (" " * spaces) + value_str + "\n").encode()

    if total_deduction > 0:
        original_subtotal = sale.total_amount + total_deduction
        commands.append(format_total_line("Original Subtotal:", original_subtotal))
        commands.append(format_total_line("Special Deduction:", total_deduction))
        commands.append(format_total_line("Adjusted Subtotal:", sale.total_amount))
    else:
        commands.append(format_total_line("Subtotal:", sale.total_amount))

    if sale.special_amount > 0:
        commands.append(format_total_line("Special:", sale.special_amount))

    if sale.discount_amount > 0:
        commands.append(format_total_line("Discount:", sale.discount_amount))

    commands.append(b"-" * LINE_WIDTH + b"\n")

    commands.append(b"\x1b\x21\x10")
    commands.append(format_total_line("TOTAL:", sale.final_amount))
    commands.append(b"\x1b\x21\x00")

    commands.append(b"-" * LINE_WIDTH + b"\n")
    commands.append(f"Payment: {sale.payment_method}\n".encode())
    commands.append(b"\n")

    commands.append(b"\x1b\x61\x01")

    qr_data = f"BEIZURI-{sale.sale_number}-KSh{float(sale.final_amount):.2f}"

    commands.append(b"\x1d\x28\x6b\x04\x00\x31\x41\x32\x00")
    commands.append(b"\x1d\x28\x6b\x03\x00\x31\x43\x03")
    commands.append(b"\x1d\x28\x6b\x03\x00\x31\x45\x30")

    qr_len = len(qr_data) + 3
    pl = qr_len % 256
    ph = qr_len // 256
    commands.append(
        bytes([0x1D, 0x28, 0x6B, pl, ph, 0x31, 0x50, 0x30]) + qr_data.encode()
    )

    commands.append(b"\x1d\x28\x6b\x03\x00\x31\x51\x30")
    commands.append(b"\nScan for details\n\n")

    commands.append(b"Thank you for shopping!\n")
    commands.append(b"Visit us again soon\n")
    commands.append(b"\x1b\x61\x00")
    commands.append(b"\n")
    commands.append(b"-" * LINE_WIDTH + b"\n\n\n")

    commands.append(b"\x1d\x56\x41\x03")

    return b"".join(commands)


def print_sale_receipt(sale):
    if not sale.completed_at:
        return False, "Cannot print receipt for incomplete sale"

    printer = ThermalPrinter()

    success, message = printer.connect()
    if not success:
        return False, message

    try:
        commands = format_receipt_commands(sale)

        if printer.print_raw(commands):
            return True, "Receipt printed successfully"
        else:
            return False, "Failed to send data to printer"

    except Exception as e:
        return False, f"Print error: {str(e)}"

    finally:
        printer.disconnect()


def check_printer_status():
    printer = ThermalPrinter()
    success, message = printer.connect()
    printer.disconnect()
    return success, message
