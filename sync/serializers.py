from rest_framework import serializers
from django.contrib.auth import get_user_model
from products.models import Product, Category, Brand, Barcode
from sales.models import Sale, SaleItem, Return, ReturnItem

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "role",
            "phone_number",
            "is_active",
            "is_staff",
            "is_superuser",
            "created_at",
            "updated_at",
            "password",
        ]
        extra_kwargs = {"password": {"write_only": True}}


class UserSyncSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "role",
            "phone_number",
            "is_active",
            "is_staff",
            "is_superuser",
            "created_at",
            "updated_at",
            "password",
        ]


class CategorySyncSerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = [
            "id",
            "name",
            "description",
            "is_active",
            "created_at",
            "updated_at",
        ]


class BrandSyncSerializer(serializers.ModelSerializer):
    class Meta:
        model = Brand
        fields = [
            "id",
            "name",
            "description",
            "is_active",
            "created_at",
        ]


class BarcodeSyncSerializer(serializers.ModelSerializer):
    class Meta:
        model = Barcode
        fields = [
            "id",
            "barcode",
            "product_id",
            "is_active",
            "created_at",
        ]


class ProductSyncSerializer(serializers.ModelSerializer):
    barcodes = BarcodeSyncSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "description",
            "category_id",
            "brand_id",
            "slug",
            "sku",
            "cost_price",
            "selling_price",
            "wholesale_price",
            "special_price",
            "quantity",
            "low_stock_threshold",
            "weight",
            "sold_count",
            "is_active",
            "created_at",
            "updated_at",
            "barcodes",
        ]


class SaleItemSyncSerializer(serializers.ModelSerializer):
    class Meta:
        model = SaleItem
        fields = [
            "id",
            "product_id",
            "quantity",
            "unit_price",
            "discount_amount",
            "total_amount",
            "created_at",
        ]


class SaleSyncSerializer(serializers.ModelSerializer):
    items = SaleItemSyncSerializer(many=True, read_only=True)

    class Meta:
        model = Sale
        fields = [
            "id",
            "sale_number",
            "sale_type",
            "cashier_id",
            "total_amount",
            "special_amount",
            "discount_amount",
            "final_amount",
            "payment_method",
            "money_received",
            "change_amount",
            "notes",
            "created_at",
            "completed_at",
            "items",
        ]


class ReturnItemSyncSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReturnItem
        fields = [
            "id",
            "sale_item_id",
            "quantity",
            "return_reason",
            "unit_price",
            "total_price",
            "created_at",
        ]


class ReturnSyncSerializer(serializers.ModelSerializer):
    items = ReturnItemSyncSerializer(many=True, read_only=True)

    class Meta:
        model = Return
        fields = [
            "id",
            "return_number",
            "sale_id",
            "cashier_id",
            "total_return_amount",
            "notes",
            "created_at",
            "items",
        ]
