from rest_framework import serializers
from django.contrib.auth.models import User
from marketplace.models import Product, Purchase, Sale


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'date_joined', 'is_staff')
        read_only_fields = ('id', 'date_joined', 'is_staff')


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    password2 = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ('username', 'email', 'password', 'password2')

    def validate(self, data):
        if data['password'] != data['password2']:
            raise serializers.ValidationError({'password': 'Passwords do not match.'})
        if User.objects.filter(email=data['email']).exists():
            raise serializers.ValidationError({'email': 'Email already registered.'})
        return data

    def create(self, validated_data):
        validated_data.pop('password2')
        return User.objects.create_user(**validated_data)


class ProductSerializer(serializers.ModelSerializer):
    seller_username = serializers.CharField(source='seller.username', read_only=True)
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = (
            'id', 'name', 'price', 'description', 'condition',
            'is_sold', 'created_at', 'seller', 'seller_username', 'image_url'
        )
        read_only_fields = ('id', 'seller', 'seller_username', 'is_sold', 'created_at', 'image_url')

    def get_image_url(self, obj):
        request = self.context.get('request')
        if obj.image and request:
            return request.build_absolute_uri(obj.image.url)
        return None


class ProductCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ('name', 'price', 'description', 'condition', 'image')

    def validate_price(self, value):
        if value <= 0:
            raise serializers.ValidationError('Price must be greater than zero.')
        return value


class PurchaseSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_price = serializers.DecimalField(source='product.price', max_digits=10, decimal_places=2, read_only=True)
    seller_username = serializers.CharField(source='product.seller.username', read_only=True)

    class Meta:
        model = Purchase
        fields = ('id', 'product', 'product_name', 'product_price', 'seller_username', 'purchased_at')
        read_only_fields = ('id', 'purchased_at')


class SaleSerializer(serializers.ModelSerializer):
    buyer_username = serializers.CharField(source='buyer.username', read_only=True, allow_null=True)

    class Meta:
        model = Sale
        fields = ('id', 'item_name', 'price', 'buyer_username', 'listed_at')
        read_only_fields = fields
