import usb.core
import usb.util
import json
import os


def find_all_usb_devices():
    devices = usb.core.find(find_all=True)
    device_list = []

    for dev in devices:
        try:
            device_info = {
                "vendor_id": hex(dev.idVendor),
                "product_id": hex(dev.idProduct),
                "manufacturer": (
                    usb.util.get_string(dev, dev.iManufacturer)
                    if dev.iManufacturer
                    else "Unknown"
                ),
                "product": (
                    usb.util.get_string(dev, dev.iProduct)
                    if dev.iProduct
                    else "Unknown"
                ),
            }
            device_list.append(device_info)
        except:
            pass

    return device_list


def detect_thermal_printer():
    known_printers = [
        {"vendor_id": 0x0483, "product_id": 0x5743, "name": "Generic Thermal Printer"},
        {"vendor_id": 0x04B8, "product_id": 0x0202, "name": "Epson TM Series"},
        {"vendor_id": 0x154F, "product_id": 0x0000, "name": "Citizen Thermal"},
        {"vendor_id": 0x0DD4, "product_id": 0x0205, "name": "Custom VKP80"},
        {"vendor_id": 0x0519, "product_id": 0x2013, "name": "Star Micronics"},
        {"vendor_id": 0x0FE6, "product_id": 0x811E, "name": "ICS Advent"},
        {"vendor_id": 0x20D1, "product_id": 0x7008, "name": "Xprinter"},
    ]

    for printer in known_printers:
        dev = usb.core.find(
            idVendor=printer["vendor_id"], idProduct=printer["product_id"]
        )
        if dev:
            return printer, dev

    return None, None


def find_printer_endpoint(dev):
    try:
        cfg = dev.get_active_configuration()
        intf = cfg[(0, 0)]

        for ep in intf:
            if (
                usb.util.endpoint_direction(ep.bEndpointAddress)
                == usb.util.ENDPOINT_OUT
            ):
                return hex(ep.bEndpointAddress)

        return "0x01"
    except:
        return "0x01"


def test_print(vendor_id, product_id, endpoint):
    try:
        dev = usb.core.find(idVendor=int(vendor_id, 16), idProduct=int(product_id, 16))

        if dev is None:
            return False, "Printer not found"

        try:
            dev.set_configuration()
        except:
            pass

        try:
            usb.util.claim_interface(dev, 0)
        except Exception as e:
            return False, f"Cannot access printer: {str(e)}"

        test_data = b"\x1b\x40"
        test_data += b"\x1b\x61\x01"
        test_data += b"\x1b\x21\x10"
        test_data += b"BEIZURI POS\n"
        test_data += b"\x1b\x21\x00"
        test_data += b"Test Print Successful\n"
        test_data += b"\n\n\n"
        test_data += b"\x1d\x56\x41\x03"

        dev.write(int(endpoint, 16), test_data)

        usb.util.release_interface(dev, 0)
        return True, "Test print successful"

    except Exception as e:
        return False, f"Test print failed: {str(e)}"


def save_config(vendor_id, product_id, endpoint, name):
    config = {
        "name": name,
        "vendor_id": vendor_id,
        "product_id": product_id,
        "out_endpoint": endpoint,
    }

    config_path = os.path.join(os.path.dirname(__file__), "printer_config.json")

    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)

    print(f"\n✓ Configuration saved to: {config_path}")


def main():
    print("=" * 70)
    print("  BEIZURI POS - Thermal Printer Setup")
    print("=" * 70)

    print("\n[1/3] Detecting thermal printer...")
    printer_info, dev = detect_thermal_printer()

    if printer_info:
        print(f"\n✓ Found: {printer_info['name']}")
        print(f"  Vendor ID:  {hex(printer_info['vendor_id'])}")
        print(f"  Product ID: {hex(printer_info['product_id'])}")

        use_detected = input("\nUse this printer? [Y/n]: ").strip().lower()

        if use_detected != "n":
            vendor_id = hex(printer_info["vendor_id"])
            product_id = hex(printer_info["product_id"])
            endpoint = find_printer_endpoint(dev)
            printer_name = printer_info["name"]

            print(f"\n[2/3] Testing printer connection...")
            success, message = test_print(vendor_id, product_id, endpoint)

            if success:
                print(f"✓ {message}")
                print("\n[3/3] Saving configuration...")
                save_config(vendor_id, product_id, endpoint, printer_name)
                print("\n" + "=" * 70)
                print("  Setup Complete!")
                print("=" * 70)
                print("\nYour thermal printer is now configured.")
                print("You can now use it with your Django POS system.")
                return
            else:
                print(f"✗ {message}")
                print("\nFalling back to manual configuration...")

    print("\n" + "=" * 70)
    print("  Manual Printer Configuration")
    print("=" * 70)

    print("\nDetected USB devices:")
    devices = find_all_usb_devices()

    if not devices:
        print("✗ No USB devices found!")
        return

    for i, dev in enumerate(devices, 1):
        print(f"\n{i}. {dev['product']} ({dev['manufacturer']})")
        print(f"   VID: {dev['vendor_id']}, PID: {dev['product_id']}")

    print("\n" + "-" * 70)
    choice = input("\nSelect your thermal printer number (or 'q' to quit): ").strip()

    if choice.lower() == "q":
        return

    try:
        idx = int(choice) - 1
        selected = devices[idx]

        vendor_id = selected["vendor_id"]
        product_id = selected["product_id"]
        endpoint = input(f"\nOUT Endpoint address (default 0x01): ").strip() or "0x01"
        printer_name = (
            input(f"Printer name (default '{selected['product']}'): ").strip()
            or selected["product"]
        )

        print(f"\n[2/3] Testing printer...")
        success, message = test_print(vendor_id, product_id, endpoint)

        if success:
            print(f"✓ {message}")
            print("\n[3/3] Saving configuration...")
            save_config(vendor_id, product_id, endpoint, printer_name)
            print("\n" + "=" * 70)
            print("  Setup Complete!")
            print("=" * 70)
        else:
            print(f"✗ {message}")
            print("\nPlease check your printer connection and try again.")

    except (ValueError, IndexError):
        print("✗ Invalid selection")
    except Exception as e:
        print(f"✗ Error: {str(e)}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nSetup cancelled.")
