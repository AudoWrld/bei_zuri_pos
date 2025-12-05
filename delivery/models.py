from django.db import models
from django.conf import settings
from django.utils import timezone
from django.utils.crypto import get_random_string
from django.core.exceptions import ValidationError


def generate_delivery_number():
    prefix = "DEL"
    random_part = get_random_string(
        8, allowed_chars="0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    )
    return f"{prefix}-{random_part}"


class Delivery(models.Model):
    DELIVERY_STATUS = [
        ("pending", "Pending"),
        ("assigned", "Assigned"),
        ("in_transit", "In Transit"),
        ("delivered", "Delivered"),
        ("cancelled", "Cancelled"),
    ]

    PAYMENT_STATUS = [
        ("pending", "Pending"),
        ("completed", "Completed"),
        ("failed", "Failed"),
        ("cancelled", "Cancelled"),
        ("pending_cash", "Pending Cash Approval"),
    ]

    delivery_number = models.CharField(
        max_length=20,
        unique=True,
        default=generate_delivery_number,
        editable=False,
        db_index=True,
    )

    sale = models.OneToOneField(
        "sales.Sale",
        on_delete=models.CASCADE,
        related_name="delivery",
    )

    responsible_cashier = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="cashier_deliveries",
        limit_choices_to={"role__in": ["admin", "cashier", "supervisor"]},
    )

    delivery_guy = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_deliveries",
        limit_choices_to={"role": "delivery_guy"},
    )

    delivery_address = models.TextField()

    status = models.CharField(
        max_length=20,
        choices=DELIVERY_STATUS,
        default="pending",
        db_index=True,
    )

    payment_status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS,
        default="pending",
    )

    notes = models.TextField(blank=True, null=True)

    assigned_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["delivery_number"]),
            models.Index(fields=["status", "created_at"]),
        ]
        verbose_name = "Delivery"
        verbose_name_plural = "Deliveries"

    def __str__(self):
        return f"{self.delivery_number}"

    def assign_delivery_guy(self, delivery_guy):
        if delivery_guy.role != "delivery_guy":
            raise ValueError("User must have delivery_guy role")

        active_delivery = (
            Delivery.objects.filter(
                delivery_guy=delivery_guy, status__in=["assigned", "in_transit"]
            )
            .exclude(pk=self.pk)
            .first()
        )

        if active_delivery:
            raise ValidationError(
                f"Delivery guy {delivery_guy.get_full_name()} already has an active delivery "
                f"({active_delivery.delivery_number}). They must complete it before being assigned another."
            )

        self.delivery_guy = delivery_guy
        self.status = "assigned"
        self.assigned_at = timezone.now()
        self.save()

    def mark_in_transit(self):
        self.status = "in_transit"
        self.save()

    def mark_delivered(self):
        self.status = "delivered"
        self.delivered_at = timezone.now()
        self.save()

    def mark_payment_completed(self):
        self.payment_status = "completed"
        self.save()

    def mark_payment_failed(self):
        self.payment_status = "failed"
        self.save()

    def cancel_delivery(self):
        if self.status == "delivered":
            raise ValueError("Cannot cancel a delivered order")
        self.status = "cancelled"
        self.payment_status = "cancelled"
        self.save()
