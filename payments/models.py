from django.db import models
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils.crypto import get_random_string

User = get_user_model()


class Payment(models.Model):
    PAYMENT_TYPE = [
        ("mpesa", "M-Pesa"),
        ("cash", "Cash"),
        ("card", "Card"),
        ("debt", "Debt Payment"),
        ("delivery", "Delivery Payment"),
    ]
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("completed", "Completed"),
        ("failed", "Failed"),
        ("cancelled", "Cancelled"),
        ("pending_cash", "Pending Cash Approval"),
    ]

    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPE)

    amount = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_reference = models.CharField(max_length=100, unique=True, db_index=True)
    mpesa_receipt_number = models.CharField(
        max_length=100, blank=True, null=True, unique=True, db_index=True
    )
    phone_number = models.CharField(max_length=15)
    checkout_request_id = models.CharField(max_length=100, blank=True, null=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
    )
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "created_at"]),
        ]
        verbose_name = "Payment"
        verbose_name_plural = "Payments"


class Debt(models.Model):
    DEBT_STATUS = [
        ("unpaid", "Unpaid"),
        ("partial", "Partially Paid"),
        ("cleared", "Cleared"),
    ]

    payment = models.OneToOneField(
        Payment,
        on_delete=models.CASCADE,
        related_name="debt_record",
        limit_choices_to={"payment_type": "debt"},
    )

    cashier = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="handled_debts",
    )

    customer_email = models.EmailField(blank=True, null=True)
    customer_first_name = models.CharField(max_length=120, blank=True, null=True)
    customer_second_name = models.CharField(max_length=120, blank=True, null=True)
    customer_phone = models.CharField(max_length=20, blank=True, null=True)

    amount_owed = models.DecimalField(max_digits=10, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    status = models.CharField(max_length=20, choices=DEBT_STATUS, default="unpaid")

    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    customer_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="customer_debts",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Debt"
        verbose_name_plural = "Debts"

    def __str__(self):
        full_name = " ".join(
            filter(None, [self.customer_first_name, self.customer_second_name])
        )
        return f"Debt #{self.id} - {full_name or 'Unknown'}"

    def save(self, *args, **kwargs):
        creating = self.pk is None
        super().save(*args, **kwargs)
        if creating:
            self.assign_or_create_customer()

    def assign_or_create_customer(self):
        phone = (self.customer_phone or "").strip()
        email = (self.customer_email or "").strip().lower()
        first = (self.customer_first_name or "").strip()
        second = (self.customer_second_name or "").strip()

        user = None

        if phone:
            try:
                user = User.objects.get(phone_number=phone)
            except User.DoesNotExist:
                user = None

        if not user and email:
            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                user = None

        if not user:
            user = User.objects.create(
                username=phone if phone else get_random_string(10),
                first_name=first,
                last_name=second,
                phone_number=phone if phone else None,
                email=email if email else None,
                role=User.CUSTOMER,
            )
            user.set_password(get_random_string(12))
            user.save()

        self.customer_user = user
        self.save(update_fields=["customer_user"])
