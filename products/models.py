from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from django.utils.text import slugify
from decimal import Decimal
import random
import string
import re


def generate_sku(product_name):
    clean_name = re.sub(r"[^a-zA-Z0-9]", "", product_name.upper())

    if len(clean_name) >= 3:
        prefix = clean_name[:3]
    elif len(clean_name) > 0:
        prefix = clean_name.ljust(3, "X")
    else:
        prefix = "PRD"

    number = "".join(random.choices(string.digits, k=2))
    return f"{prefix}{number}"


def calculate_ean13_checksum(code):
    if len(code) != 12:
        raise ValueError("EAN13 needs 12 digits")

    odd_sum = sum(int(code[i]) for i in range(0, 12, 2))
    even_sum = sum(int(code[i]) for i in range(1, 12, 2))
    total = odd_sum + (even_sum * 3)
    checksum = (10 - (total % 10)) % 10

    return str(checksum)


def validate_ean13(barcode):
    if len(barcode) != 13:
        return False

    if not barcode.isdigit():
        return False

    calculated_checksum = calculate_ean13_checksum(barcode[:12])

    return calculated_checksum == barcode[12]


def generate_barcode():
    max_attempts = 50

    for _ in range(max_attempts):
        base = "".join(random.choices(string.digits, k=12))
        checksum = calculate_ean13_checksum(base)
        barcode = base + checksum

        from products.models import Barcode

        if not Barcode.objects.filter(barcode=barcode).exists():
            return barcode

    import time

    timestamp = str(int(time.time() * 1000))[-12:]
    checksum = calculate_ean13_checksum(timestamp)
    return timestamp + checksum


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    server_id = models.IntegerField(unique=True, null=True, blank=True, db_index=True)
    synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name_plural = "Categories"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Brand(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    server_id = models.IntegerField(unique=True, null=True, blank=True, db_index=True)
    synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Barcode(models.Model):
    barcode = models.CharField(
        max_length=25,
        unique=True,
        default=generate_barcode,
        editable=True,
        db_index=True,
    )
    product = models.ForeignKey(
        "Product",
        on_delete=models.CASCADE,
        related_name="barcodes",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    server_id = models.IntegerField(unique=True, null=True, blank=True, db_index=True)
    synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["barcode"]),
        ]

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.barcode and len(self.barcode) == 13:
            if not validate_ean13(self.barcode):
                raise ValidationError(
                    {"barcode": "Invalid EAN-13 barcode. Checksum does not match."}
                )

    def __str__(self):
        return f"{self.barcode} - {self.product.name}"


class Product(models.Model):
    name = models.CharField(max_length=200, db_index=True)
    description = models.TextField(blank=True)
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="products",
    )
    brand = models.ForeignKey(
        Brand, on_delete=models.SET_NULL, null=True, blank=True, related_name="products"
    )

    slug = models.SlugField(unique=True, blank=True)
    sku = models.CharField(
        max_length=8,
        unique=True,
        editable=True,
        db_index=True,
    )

    cost_price = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(0)]
    )
    selling_price = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(0)]
    )
    wholesale_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        blank=True,
        null=True,
    )

    special_price = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(0)]
    )

    quantity = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    low_stock_threshold = models.IntegerField(
        default=10, validators=[MinValueValidator(0)]
    )

    weight = models.DecimalField(
        max_digits=10, decimal_places=3, blank=True, null=True, help_text="Weight in kg"
    )

    sold_count = models.IntegerField(default=0, validators=[MinValueValidator(0)])

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    server_id = models.IntegerField(unique=True, null=True, blank=True, db_index=True)
    synced_at = models.DateTimeField(null=True, blank=True)

    def clean(self):
        from django.core.exceptions import ValidationError

        if not self.special_price or self.special_price <= 0:
            raise ValidationError(
                "Special price is required and must be greater than 0"
            )

        if self.wholesale_price:
            if not (
                self.cost_price
                < self.special_price
                < self.wholesale_price
                < self.selling_price
            ):
                raise ValidationError(
                    "Prices must satisfy: cost_price < special_price < wholesale_price < selling_price"
                )
        else:
            if not (self.cost_price < self.special_price < self.selling_price):
                raise ValidationError(
                    "Prices must satisfy: cost_price < special_price < selling_price"
                )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["sku"]),
            models.Index(fields=["name"]),
        ]

    def save(self, *args, **kwargs):
        self.name = self.name.title()

        if not self.sku:
            base_sku = generate_sku(self.name)
            sku = base_sku
            counter = 1
            while Product.objects.filter(sku=sku).exclude(pk=self.pk).exists():
                number = str(counter).zfill(2)
                prefix = base_sku[:3]
                sku = f"{prefix}{number}"
                counter += 1
            self.sku = sku

        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1
            while Product.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.sku})"

    @property
    def is_in_stock(self):
        return self.quantity > 0

    @property
    def is_low_stock(self):
        return self.quantity <= self.low_stock_threshold

    @property
    def profit_margin(self):
        from sales.models import SaleItem

        sale_items = SaleItem.objects.filter(product=self).select_related("sale")

        if not sale_items.exists():
            return Decimal("0.00")

        total_revenue = Decimal(0)
        total_cost = Decimal(0)

        for item in sale_items:
            if item.sale.sale_type == "RETAIL":
                selling_price = self.selling_price
            elif item.sale.sale_type == "WHOLESALE":
                selling_price = (
                    self.wholesale_price if self.wholesale_price else self.selling_price
                )
            elif item.sale.sale_type == "SPECIAL":
                selling_price = self.special_price
            else:
                selling_price = self.selling_price

            total_revenue += selling_price * item.quantity
            total_cost += self.cost_price * item.quantity

        if total_cost > 0:
            margin = ((total_revenue - total_cost) / total_cost) * 100
            return min(margin, Decimal("100.00")).quantize(Decimal("0.01"))

        return Decimal("0.00")

    @property
    def revenue_generated(self):
        from sales.models import SaleItem

        total_revenue = Decimal(0)

        sale_items = SaleItem.objects.filter(product=self).select_related("sale")

        for item in sale_items:
            if item.sale.sale_type == "RETAIL":
                selling_price = self.selling_price
            elif item.sale.sale_type == "WHOLESALE":
                selling_price = (
                    self.wholesale_price if self.wholesale_price else self.selling_price
                )
            elif item.sale.sale_type == "SPECIAL":
                selling_price = self.special_price
            else:
                selling_price = self.selling_price

            total_revenue += selling_price * item.quantity

        return total_revenue.quantize(Decimal("0.01"))

    @property
    def total_profit(self):
        from sales.models import SaleItem

        total_profit = Decimal(0)

        sale_items = SaleItem.objects.filter(product=self).select_related("sale")

        for item in sale_items:
            if item.sale.sale_type == "RETAIL":
                selling_price = self.selling_price
            elif item.sale.sale_type == "WHOLESALE":
                selling_price = (
                    self.wholesale_price if self.wholesale_price else self.selling_price
                )
            elif item.sale.sale_type == "SPECIAL":
                selling_price = self.special_price
            else:
                selling_price = self.selling_price

            profit_per_item = selling_price - self.cost_price
            total_profit += profit_per_item * item.quantity

        return total_profit.quantize(Decimal("0.01"))

    @classmethod
    def get_all_products_total_profit(cls):
        from sales.models import SaleItem

        total_profit = Decimal(0)

        sale_items = SaleItem.objects.select_related("product", "sale").all()

        for item in sale_items:
            product = item.product

            if item.sale.sale_type == "RETAIL":
                selling_price = product.selling_price
            elif item.sale.sale_type == "WHOLESALE":
                selling_price = (
                    product.wholesale_price
                    if product.wholesale_price
                    else product.selling_price
                )
            elif item.sale.sale_type == "SPECIAL":
                selling_price = product.special_price
            else:
                selling_price = product.selling_price

            profit_per_item = selling_price - product.cost_price
            total_profit += profit_per_item * item.quantity

        return total_profit.quantize(Decimal("0.01"))

    @classmethod
    def get_all_products_total_revenue(cls):
        from sales.models import SaleItem

        total_revenue = Decimal(0)

        sale_items = SaleItem.objects.select_related("product", "sale").all()

        for item in sale_items:
            product = item.product

            if item.sale.sale_type == "RETAIL":
                selling_price = product.selling_price
            elif item.sale.sale_type == "WHOLESALE":
                selling_price = (
                    product.wholesale_price
                    if product.wholesale_price
                    else product.selling_price
                )
            elif item.sale.sale_type == "SPECIAL":
                selling_price = product.special_price
            else:
                selling_price = product.selling_price

            total_revenue += selling_price * item.quantity

        return total_revenue.quantize(Decimal("0.01"))

    @classmethod
    def get_all_products_profit_margin(cls):
        from sales.models import SaleItem

        total_revenue = Decimal(0)
        total_cost = Decimal(0)

        sale_items = SaleItem.objects.select_related("product", "sale").all()

        for item in sale_items:
            product = item.product

            if item.sale.sale_type == "RETAIL":
                selling_price = product.selling_price
            elif item.sale.sale_type == "WHOLESALE":
                selling_price = (
                    product.wholesale_price
                    if product.wholesale_price
                    else product.selling_price
                )
            elif item.sale.sale_type == "SPECIAL":
                selling_price = product.special_price
            else:
                selling_price = product.selling_price

            total_revenue += selling_price * item.quantity
            total_cost += product.cost_price * item.quantity

        if total_cost > 0:
            margin = ((total_revenue - total_cost) / total_cost) * 100
            return min(margin, Decimal("100.00")).quantize(Decimal("0.01"))

        return Decimal("0.00")

    @property
    def primary_barcode(self):
        return self.barcodes.filter(is_active=True).first()

    @property
    def barcode(self):
        primary = self.primary_barcode
        return primary.barcode if primary else "N/A"

    def get_price_by_sale_type(self, sale_type):
        if sale_type == "RETAIL":
            return self.selling_price
        elif sale_type == "WHOLESALE":
            return self.wholesale_price if self.wholesale_price else self.selling_price
        elif sale_type == "SPECIAL":
            return self.special_price
        return self.selling_price

    def sell(self, quantity=1):
        previous_quantity = self.quantity
        self.quantity -= quantity
        self.sold_count += quantity
        self.save()
        StockMovement.objects.create(
            product=self,
            movement_type="OUT",
            quantity=quantity,
            previous_quantity=previous_quantity,
            new_quantity=self.quantity,
            notes=f"Sale completed - {quantity} units sold",
        )

    def restock(self, quantity):
        previous_quantity = self.quantity
        self.quantity += quantity
        self.save()
        StockMovement.objects.create(
            product=self,
            movement_type="IN",
            quantity=quantity,
            previous_quantity=previous_quantity,
            new_quantity=self.quantity,
            notes=f"Stock added - {quantity} units",
        )


class StockMovement(models.Model):
    MOVEMENT_TYPES = [
        ("IN", "Stock In"),
        ("OUT", "Stock Out"),
        ("ADJUST", "Adjustment"),
        ("RETURN", "Return"),
    ]

    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="stock_movements"
    )
    movement_type = models.CharField(max_length=10, choices=MOVEMENT_TYPES)
    quantity = models.IntegerField()
    previous_quantity = models.IntegerField()
    new_quantity = models.IntegerField()
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.product.name} - {self.movement_type} - {self.quantity}"
