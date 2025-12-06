from rest_framework import serializers
from django.contrib.auth import get_user_model
from products.models import Product, Category, Brand, Barcode

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
