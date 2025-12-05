from django.db import models
from django.conf import settings
from django.utils import timezone
from decimal import Decimal


class Sale(models.Model):
    SALE_TYPES = [
        ("RETAIL", "Retail Sale"),
        ("WHOLESALE", "Wholesale Sale"),
        ("SPECIAL", "Special Sale"),
    ]

    sale_number = models.CharField(
        max_length=20, unique=True, editable=False, db_index=True
    )
    sale_type = models.CharField(max_length=10, choices=SALE_TYPES, default="RETAIL")
    cashier = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, db_index=True
    )
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    special_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    final_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    payment_method = models.CharField(max_length=50, blank=True)
    money_received = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    change_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True, db_index=True)
    is_held = models.BooleanField(default=False, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=["sale_number"]),
            models.Index(fields=["cashier"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["completed_at"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"Sale {self.sale_number} - {self.final_amount}"

    def save(self, *args, **kwargs):
        if not self.sale_number:
            # Generate sale number like SALE-20241125-0001
            today = timezone.now().strftime("%Y%m%d")
            last_sale = (
                Sale.objects.filter(sale_number__startswith=f"SALE-{today}")
                .order_by("-sale_number")
                .first()
            )

            if last_sale:
                last_number = int(last_sale.sale_number.split("-")[-1])
                new_number = last_number + 1
            else:
                new_number = 1

            self.sale_number = f"SALE-{today}-{new_number:04d}"

        super().save(*args, **kwargs)

    def complete_sale(self):
        """Complete the sale and update inventory"""
        if self.completed_at:
            return 

        self.completed_at = timezone.now()

        total = Decimal("0")
        special_total = Decimal("0")

        for item in self.items.all():
            if self.sale_type == "SPECIAL":
                item_total = item.quantity * item.product.special_price
            else:
                item_total = item.quantity * item.unit_price
            total += item_total

            item.product.sell(item.quantity)

        self.total_amount = total
        self.special_amount = special_total
        self.final_amount = total - self.discount_amount

        self.save()


class SaleItem(models.Model):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey("products.Product", on_delete=models.CASCADE)
    quantity = models.IntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    discount_amount = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.product.name} x{self.quantity}"

    def save(self, *args, **kwargs):
        # Calculate total amount
        if self.sale.sale_type == "SPECIAL":
            self.total_amount = (
                self.quantity * self.product.special_price - self.discount_amount
            )
        else:
            self.total_amount = self.quantity * self.unit_price - self.discount_amount
        super().save(*args, **kwargs)
