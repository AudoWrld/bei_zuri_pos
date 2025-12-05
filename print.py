#!/usr/bin/env python3

import usb.core
import usb.util
import time
import datetime
import json
import os
from collections import Counter
import qrcode
from io import BytesIO


def load_printer_config():
    if os.path.exists("printer_config.json"):
        with open("printer_config.json", "r") as f:
            config = json.load(f)
            return {
                "vendor_id": int(config["vendor_id"], 16),
                "product_id": int(config["product_id"], 16),
                "out_ep": int(config["out_endpoint"], 16),
            }
    return {"vendor_id": 0x0483, "product_id": 0x5743, "out_ep": 0x01}


PRINTER_CONFIG = load_printer_config()
PRINTER_VENDOR_ID = PRINTER_CONFIG["vendor_id"]
PRINTER_PRODUCT_ID = PRINTER_CONFIG["product_id"]
PRINTER_OUT_EP = PRINTER_CONFIG["out_ep"]

PRODUCTS = {
    "1234567890128": {"name": "Coca Cola 500ml", "price": 1.5, "sku": "DRINK001"},
    "2345678901234": {"name": "Water Bottle", "price": 1.0, "sku": "DRINK002"},
    "3456789012340": {"name": "Chocolate Bar", "price": 2.5, "sku": "SNACK001"},
    "4567890123456": {"name": "Chips", "price": 3.0, "sku": "SNACK002"},
    "5678901234562": {"name": "Sandwich", "price": 5.5, "sku": "FOOD001"},
    "6789012345678": {"name": "Coffee", "price": 2.75, "sku": "DRINK003"},
    "7890123456784": {"name": "Energy Drink", "price": 3.5, "sku": "DRINK004"},
    "8901234567890": {"name": "Juice Box", "price": 2.0, "sku": "DRINK005"},
    "9012345678906": {"name": "Candy", "price": 0.75, "sku": "SNACK003"},
    "0123456789012": {"name": "Gum", "price": 1.25, "sku": "SNACK004"},
}


class RawUSBPrinter:
    def __init__(self):
        self.dev = None

    def connect(self):
        print("\nConnecting to printer...")

        self.dev = usb.core.find(
            idVendor=PRINTER_VENDOR_ID, idProduct=PRINTER_PRODUCT_ID
        )

        if self.dev is None:
            print("✗ Printer not found!")
            return False

        print(f"✓ Found: {self.dev.product}")

        try:
            self.dev.set_configuration()
        except:
            pass

        try:
            usb.util.claim_interface(self.dev, 0)
            print("✓ Printer ready")
            return True
        except Exception as e:
            print(f"✗ Failed to claim interface: {e}")
            return False

    def print_raw(self, data):
        if not self.dev:
            return False

        try:
            self.dev.write(PRINTER_OUT_EP, data)
            time.sleep(0.5)
            return True
        except Exception as e:
            print(f"Print error: {e}")
            return False

    def disconnect(self):
        if self.dev:
            try:
                usb.util.release_interface(self.dev, 0)
            except:
                pass


class POSSystem:
    def __init__(self):
        self.cart = []
        self.printer = RawUSBPrinter()
        self.receipt_number = self.generate_receipt_number()

    def generate_receipt_number(self):
        return f"R{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"

    def add_to_cart(self, barcode):
        if barcode in PRODUCTS:
            product = PRODUCTS[barcode]
            self.cart.append(
                {
                    "barcode": barcode,
                    "name": product["name"],
                    "price": product["price"],
                    "time": datetime.datetime.now(),
                }
            )
            print(f"\n✓ Added: {product['name']} - ${product['price']:.2f}")
            return True
        else:
            print(f"\n✗ Unknown barcode: {barcode}")
            return False

    def get_total(self):
        return sum(item["price"] for item in self.cart)

    def display_cart(self):
        print("\n" + "=" * 60)
        print("CURRENT CART")
        print("=" * 60)

        if not self.cart:
            print("(empty)")
        else:
            item_counts = Counter(item["barcode"] for item in self.cart)

            for barcode, qty in item_counts.items():
                product = PRODUCTS[barcode]
                price = product["price"] * qty
                print(f"{qty}x {product['name']:<25} ${price:>6.2f}")

        print("-" * 60)
        print(f"{'TOTAL':<30} ${self.get_total():>6.2f}")
        print("=" * 60)

    def print_receipt(self):
        LINE_WIDTH = 30   # Keep overall width for 30mm paper

        if not self.printer.connect():
            print("⚠ Cannot connect to printer")
            return False

        try:
            commands = []

            # Reset printer
            commands.append(b"\x1b\x40")
            commands.append(b"\x1b\x33\x00")  # Line spacing
            commands.append(bytes([0x1D, 0x5C, 0x00, 0x00]))  # Left margin
            # commands.append(b"\x1d\x88\x20\x01")  # Optional density

            # --- HEADER ---
            commands.append(b"\x1b\x61\x01")  # center
            commands.append(b"\x1b\x21\x10")  # bold/large
            commands.append(b"BEIZURI\n")
            commands.append(b"\x1b\x21\x00")
            commands.append(b"Bondo Town, Siaya\n")
            commands.append(b"Tel: +254 785 053 060\n\n")

            # Divider
            commands.append(b"\x1b\x61\x00")
            commands.append(b"-" * LINE_WIDTH + b"\n")

            date_str = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
            commands.append(f"Date: {date_str}\n".encode())
            commands.append(f"Receipt: {self.receipt_number}\n".encode())
            commands.append(b"-" * LINE_WIDTH + b"\n")

            # --- ITEM DETAILS (wider spacing) ---
            ITEM_WIDTH = 40  # temporary wider width for details

            item_counts = Counter(item["barcode"] for item in self.cart)
            for barcode, qty in item_counts.items():
                product = PRODUCTS[barcode]
                name = product["name"]
                price = product["price"] * qty

                # truncate long names
                if len(name) > 35:
                    name = name[:35]

                # Name on first line
                commands.append(name.encode() + b"\n")

                # Price + qty line with ITEM_WIDTH spacing
                price_line = f"  {qty} x ${product['price']:.2f}"
                total_line = f"${price:.2f}"
                spaces_needed = ITEM_WIDTH - len(price_line) - len(total_line)
                if spaces_needed < 1:
                    spaces_needed = 1

                line2 = price_line + (" " * spaces_needed) + total_line + "\n"
                commands.append(line2.encode())

            commands.append(b"-" * LINE_WIDTH + b"\n")

            # --- TOTAL ---
            total = self.get_total()
            total_label = "TOTAL:"
            total_val = f"${total:.2f}"
            total_spaces = LINE_WIDTH - len(total_label) - len(total_val)
            if total_spaces < 1:
                total_spaces = 1
            commands.append((total_label + (" " * total_spaces) + total_val + "\n").encode())
            commands.append(b"-" * LINE_WIDTH + b"\n\n")

            # --- QR CODE ---
            commands.append(b"\x1b\x61\x01")  # center
            qr_data = f"BEIZURI-{self.receipt_number}-${total:.2f}"
            commands.append(b"\x1d\x28\x6b\x04\x00\x31\x41\x32\x00")  # model
            commands.append(b"\x1d\x28\x6b\x03\x00\x31\x43\x03")      # size
            commands.append(b"\x1d\x28\x6b\x03\x00\x31\x45\x30")      # ECC

            qr_len = len(qr_data) + 3
            pl = qr_len % 256
            ph = qr_len // 256
            commands.append(bytes([0x1D, 0x28, 0x6B, pl, ph, 0x31, 0x50, 0x30]) + qr_data.encode())
            commands.append(b"\x1d\x28\x6b\x03\x00\x31\x51\x30")  # print QR

            commands.append(b"\nScan for details\n\n")

            # Footer
            commands.append(b"Thank you for shopping!\n")
            commands.append(b"Visit us again\n")
            commands.append(b"\x1b\x61\x00")
            commands.append(b"\n")
            commands.append(b"-" * LINE_WIDTH + b"\n\n\n")

            # Cut
            commands.append(b"\x1d\x56\x41\x03")

            data = b"".join(commands)

            print("\n→ Printing receipt...")
            if self.printer.print_raw(data):
                print("✓ Receipt printed successfully!")
                return True
            else:
                print("✗ Print failed")
                return False

        except Exception as e:
            print(f"✗ Print error: {e}")
            return False
        finally:
            self.printer.disconnect()


    def run(self):
        print("=" * 60)
        print("  POS SYSTEM - BEIZURI")
        print("=" * 60)
        print("\n✓ System ready!")
        print("\nEnter barcodes (or type 'done' to finish):\n")

        try:
            while True:
                barcode = input("→ Scan/Enter barcode: ").strip()

                if barcode.lower() in ["done", "finish", "exit", "quit"]:
                    break

                if barcode:
                    self.add_to_cart(barcode)
                    self.display_cart()

        except KeyboardInterrupt:
            print("\n\n✓ Transaction complete!")

        if self.cart:
            self.display_cart()
            try:
                response = input("\nPrint receipt? [y/n]: ").strip().lower()
                if response == "y":
                    self.receipt_number = self.generate_receipt_number()
                    self.print_receipt()
            except KeyboardInterrupt:
                print("\nSkipping receipt.")
        else:
            print("\nNo items in cart.")

        self.cart = []


def main():
    print("=" * 60)
    print("  BEIZURI POS System v3.1 - 58mm")
    print("=" * 60)

    if os.path.exists("printer_config.json"):
        with open("printer_config.json", "r") as f:
            config = json.load(f)
            print(f"\nCurrent Printer: {config.get('name', 'Unknown')}")
            print(f"VID:PID: {config['vendor_id']}:{config['product_id']}")
    else:
        print("\n⚠ No printer configured yet!")
        print("Run: python universal_printer_setup.py")

    print("\n1. Run POS System")
    print("2. Print Test Receipt")
    print("3. Configure/Change Printer")
    print("4. Exit")

    choice = input("\nSelect [1-4]: ").strip()

    if choice == "1":
        pos = POSSystem()
        pos.run()
    elif choice == "2":
        pos = POSSystem()
        print("\nPrinting test receipt...")
        pos.add_to_cart("1234567890128")
        pos.add_to_cart("2345678901234")
        pos.add_to_cart("1234567890128")
        pos.display_cart()
        pos.print_receipt()
    elif choice == "3":
        print("\nRun: python universal_printer_setup.py")
        print("This will detect and configure your printer automatically.")
    else:
        print("Goodbye!")


if __name__ == "__main__":
    main()
