from io import BytesIO
from datetime import datetime
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from .models import Sale, SaleItem


def download_receipt(request, sale_number):
    sale = get_object_or_404(Sale, sale_number=sale_number)
    sale_items = SaleItem.objects.filter(sale=sale)

    receipt_data = {
        "shop_name": "BEIZURI",
        "address": "Bondo Town, Siaya",
        "phone": "Tel: +254 785 053 060",
        "sale_number": sale.sale_number,
        "date": sale.created_at.strftime("%d/%m/%Y %H:%M"),
        "sale_type": sale.get_sale_type_display(),
        "cashier": sale.cashier.get_full_name() if sale.cashier else "N/A",
        "items": [
            {
                "name": item.product.name,
                "quantity": item.quantity,
                "unit_price": f"{item.unit_price:.2f}",
                "total": f"{item.total_amount:.2f}",
            }
            for item in sale_items
        ],
        "subtotal": f"{sale.total_amount:.2f}",
        "special_amount": (
            f"{sale.special_amount:.2f}" if sale.special_amount else "0.00"
        ),
        "discount_amount": (
            f"{sale.discount_amount:.2f}" if sale.discount_amount else "0.00"
        ),
        "total": f"{sale.final_amount:.2f}",
        "payment_method": sale.payment_method,
        "money_received": f"{sale.money_received:.2f}" if sale.money_received else None,
        "change_amount": f"{sale.change_amount:.2f}" if sale.change_amount else "0.00",
    }

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    y = height - 1 * inch

    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawCentredString(width / 2, y, receipt_data["shop_name"])
    y -= 20

    pdf.setFont("Helvetica", 10)
    pdf.drawCentredString(width / 2, y, receipt_data["address"])
    y -= 15
    pdf.drawCentredString(width / 2, y, receipt_data["phone"])
    y -= 30

    pdf.line(1 * inch, y, width - 1 * inch, y)
    y -= 20

    pdf.setFont("Helvetica", 10)
    pdf.drawString(1 * inch, y, f"Sale #: {receipt_data['sale_number']}")
    y -= 15
    pdf.drawString(1 * inch, y, f"Date: {receipt_data['date']}")
    y -= 15
    pdf.drawString(1 * inch, y, f"Type: {receipt_data['sale_type']}")
    y -= 15
    pdf.drawString(1 * inch, y, f"Cashier: {receipt_data['cashier']}")
    y -= 15
    pdf.drawString(1 * inch, y, f"Payment: {receipt_data['payment_method']}")
    y -= 30

    pdf.line(1 * inch, y, width - 1 * inch, y)
    y -= 20

    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(1 * inch, y, "Item")
    pdf.drawString(4 * inch, y, "Qty")
    pdf.drawString(5 * inch, y, "Price")
    pdf.drawString(6 * inch, y, "Total")
    y -= 15

    pdf.line(1 * inch, y, width - 1 * inch, y)
    y -= 15

    pdf.setFont("Helvetica", 10)
    for item in receipt_data["items"]:
        pdf.drawString(1 * inch, y, item["name"][:40])
        pdf.drawString(4 * inch, y, str(item["quantity"]))
        pdf.drawString(5 * inch, y, item["unit_price"])
        pdf.drawString(6 * inch, y, item["total"])
        y -= 15

    y -= 10
    pdf.line(1 * inch, y, width - 1 * inch, y)
    y -= 20

    pdf.drawRightString(6.5 * inch, y, f"Subtotal: {receipt_data['subtotal']}")
    y -= 15

    if float(receipt_data.get("special_amount", 0)) != 0:
        pdf.drawRightString(
            6.5 * inch, y, f"Special Discount: -{receipt_data['special_amount']}"
        )
        y -= 15

    if float(receipt_data.get("discount_amount", 0)) != 0:
        pdf.drawRightString(
            6.5 * inch, y, f"Discount: -{receipt_data['discount_amount']}"
        )
        y -= 15

    y -= 10
    pdf.line(1 * inch, y, width - 1 * inch, y)
    y -= 20

    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawRightString(6.5 * inch, y, f"TOTAL: {receipt_data['total']}")
    y -= 20

    pdf.setFont("Helvetica", 10)
    if receipt_data.get("payment_method") == "Cash":
        if receipt_data.get("money_received"):
            pdf.drawRightString(
                6.5 * inch, y, f"Paid: {receipt_data['money_received']}"
            )
            y -= 15
        if (
            receipt_data.get("change_amount")
            and float(receipt_data["change_amount"]) > 0
        ):
            pdf.drawRightString(
                6.5 * inch, y, f"Change: {receipt_data['change_amount']}"
            )
            y -= 15

    y -= 30
    pdf.line(1 * inch, y, width - 1 * inch, y)
    y -= 20

    pdf.drawCentredString(width / 2, y, "Thank you for your purchase!")
    y -= 15
    pdf.drawCentredString(width / 2, y, "Please come again")

    pdf.save()
    buffer.seek(0)

    return HttpResponse(
        buffer,
        content_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="receipt_{receipt_data["sale_number"]}.pdf"'
        },
    )
