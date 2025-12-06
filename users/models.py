from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.conf import settings


class UserManager(BaseUserManager):
    def create_user(self, username, email=None, password=None, **extra_fields):
        if not username:
            raise ValueError("The Username field must be set")
        email = self.normalize_email(email) if email else None
        user = self.model(username=username, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", User.ADMIN)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self.create_user(username, email, password, **extra_fields)


class User(AbstractUser):
    ADMIN = "admin"
    CASHIER = "cashier"
    DELIVERY_GUY = "delivery_guy"
    SUPERVISOR = "supervisor"
    CUSTOMER = "customer"

    ROLE_CHOICES = [
        (ADMIN, "Administrator"),
        (CASHIER, "Cashier"),
        (DELIVERY_GUY, "Delivery Guy"),
        (SUPERVISOR, "Supervisor"),
        (CUSTOMER, "Customer"),
    ]

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=CUSTOMER)
    phone_number = models.CharField(max_length=15, blank=True, null=True)

    server_id = models.IntegerField(unique=True, null=True, blank=True, db_index=True)
    synced_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()
    REQUIRED_FIELDS = ["email", "first_name", "last_name", "phone_number"]

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"
        ordering = ["-date_joined"]

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.get_role_display()})"

    def is_synced_from_server(self):
        return self.server_id is not None if settings.IS_DESKTOP else False

    def is_admin(self):
        return self.role == self.ADMIN

    def is_cashier(self):
        return self.role == self.CASHIER

    def is_delivery_guy(self):
        return self.role == self.DELIVERY_GUY

    def is_supervisor(self):
        return self.role == self.SUPERVISOR

    def is_customer(self):
        return self.role == self.CUSTOMER

    def can_view_products(self):
        return True

    def can_view_brand_category(self):
        return self.role == self.ADMIN

    def can_add_products(self):
        return self.role == self.ADMIN

    def can_edit_products(self):
        return self.role == self.ADMIN

    def can_delete_products(self):
        return self.role == self.ADMIN

    def can_add_category_brand(self):
        return self.role == self.ADMIN

    def can_edit_category_brand(self):
        return self.role == self.ADMIN

    def can_delete_category_brand(self):
        return self.role == self.ADMIN

    def can_process_sales(self):
        return self.role in [self.ADMIN, self.CASHIER, self.SUPERVISOR]

    def can_manage_inventory(self):
        return self.role in [self.ADMIN, self.SUPERVISOR]

    def can_view_reports(self):
        return self.role in [self.ADMIN, self.SUPERVISOR]

    def can_manage_users(self):
        return self.role == self.ADMIN

    def can_handle_deliveries(self):
        return self.role in [self.ADMIN, self.DELIVERY_GUY, self.SUPERVISOR]

    def can_approve_sale_changes(self):
        return self.role in [self.ADMIN, self.SUPERVISOR]
