import usb.core
import usb.util
import json
import os


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
ALIGN_CENTER = ESC + b"a\x01"
ALIGN_LEFT = ESC + b"a\x00"
BOLD_ON = ESC + b"E\x01"
BOLD_OFF = ESC + b"E\x00"
LINE_FEED = b"\n"
CUT_PAPER = GS + b"V\x41\x03"


def find_printer():
    try:
        dev = usb.core.find(idVendor=VENDOR_ID, idProduct=PRODUCT_ID)
        if dev is None:
            return None

        try:
            if dev.is_kernel_driver_active(0):
                dev.detach_kernel_driver(0)
        except (AttributeError, usb.core.USBError):
            pass

        try:
            dev.set_configuration()
        except usb.core.USBError:
            pass

        try:
            usb.util.claim_interface(dev, 0)
        except usb.core.USBError:
            pass

        return dev
    except Exception:
        return None


def print_data(data):
    dev = None
    try:
        dev = find_printer()
        if dev is None:
            return False, "Printer not found"

        dev.write(OUT_ENDPOINT, data)
        return True, "Print successful"

    except usb.core.USBError as e:
        return False, f"USB Error: {str(e)}"
    except Exception as e:
        return False, f"Error: {str(e)}"
    finally:
        if dev is not None:
            try:
                usb.util.release_interface(dev, 0)
            except:
                pass


def generate_barcode(barcode_data: str, barcode_type="EAN13"):
    if not barcode_data.isdigit():
        raise ValueError("Barcode must contain only numbers")

    if barcode_type == "EAN13":
        if len(barcode_data) != 13:
            raise ValueError(f"EAN-13 barcode must be exactly 13 digits")
        format_code = 0x43
    elif barcode_type == "UPCA":
        if len(barcode_data) not in [11, 12]:
            raise ValueError(f"UPC-A barcode must be 11-12 digits")
        format_code = 0x41
    else:
        raise ValueError("barcode_type must be 'EAN13' or 'UPCA'")

    commands = bytearray()
    commands.extend(GS + b"H\x02")
    commands.extend(GS + b"h\x50")
    commands.extend(GS + b"w\x02")
    commands.extend(GS + b"k" + bytes([format_code]))
    commands.extend(bytes([len(barcode_data)]))
    commands.extend(barcode_data.encode())

    return bytes(commands)


def build_double_barcode_label(barcode_number):
    label = bytearray()

    if barcode_number.startswith('0') and len(barcode_number) == 13:
        upc_code = barcode_number[1:]
        barcode_cmd = generate_barcode(upc_code, "UPCA")
    else:
        barcode_cmd = generate_barcode(barcode_number, "EAN13")

    label.extend(ALIGN_CENTER)
    label.extend(barcode_cmd)
    label.extend(LINE_FEED)
    
    label.extend(ALIGN_CENTER)
    label.extend(barcode_cmd)
    label.extend(LINE_FEED)

    return bytes(label)


def build_label_page(barcode_number, quantity):
    page = bytearray()
    page.extend(INIT)

    pairs = quantity // 2
    remainder = quantity % 2

    for i in range(pairs):
        page.extend(build_double_barcode_label(barcode_number))

    if remainder == 1:
        page.extend(ALIGN_CENTER)
        if barcode_number.startswith('0') and len(barcode_number) == 13:
            upc_code = barcode_number[1:]
            barcode_cmd = generate_barcode(upc_code, "UPCA")
        else:
            barcode_cmd = generate_barcode(barcode_number, "EAN13")
        page.extend(barcode_cmd)
        page.extend(LINE_FEED)

    page.extend(CUT_PAPER)
    return bytes(page)


def print_barcodes(barcode_number, quantity):
    try:
        if not barcode_number.isdigit():
            return False, "Barcode must contain only digits"

        if len(barcode_number) != 13:
            return False, f"Barcode must be 13 digits"

        if quantity < 1:
            return False, "Quantity must be at least 1"

        label_bytes = build_label_page(barcode_number, quantity)
        success, message = print_data(label_bytes)

        if success:
            return True, f"Printed {quantity} barcode(s) successfully"
        else:
            return False, message

    except Exception as e:
        return False, f"Error: {str(e)}"


if __name__ == "__main__":
    print("\n" + "="*50)
    print("BARCODE LABEL PRINTER")
    print("="*50)

    barcode = input("\nEnter 13-digit barcode number: ").strip()
    quantity = input("Enter quantity to print: ").strip()

    try:
        qty = int(quantity)
        success, message = print_barcodes(barcode, qty)
        print(f"\n{message}\n")
    except ValueError:
        print("\nError: Quantity must be a number\n")