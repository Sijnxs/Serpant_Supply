import logging
from django.contrib.auth.models import User
from django.conf import settings
from rest_framework import generics, status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework_simplejwt.tokens import RefreshToken
from marketplace.models import Product, Purchase, Sale
from .serializers import (
    UserSerializer, RegisterSerializer,
    ProductSerializer, ProductCreateSerializer,
    PurchaseSerializer, SaleSerializer,
)
from .permissions import IsOwnerOrReadOnly, IsSellerOrAdmin, IsAdminUser

logger = logging.getLogger('serpantsupply')
paypal_logger = logging.getLogger('serpantsupply.paypal')


# ─── Auth endpoints ───────────────────────────────────────────────────────────

class RegisterAPIView(generics.CreateAPIView):
    """POST /api/auth/register/ — create a new user, return JWT tokens."""
    serializer_class = RegisterSerializer
    permission_classes = (permissions.AllowAny,)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        refresh = RefreshToken.for_user(user)
        logger.info(f'API: new user registered via API: {user.username}')
        return Response({
            'user': UserSerializer(user).data,
            'access': str(refresh.access_token),
            'refresh': str(refresh),
        }, status=status.HTTP_201_CREATED)


class MeAPIView(generics.RetrieveAPIView):
    """GET /api/auth/me/ — return current user profile."""
    serializer_class = UserSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_object(self):
        return self.request.user


# ─── Product endpoints ────────────────────────────────────────────────────────

class ProductListAPIView(generics.ListAPIView):
    """GET /api/products/ — list available (unsold) products with search/filter."""
    serializer_class = ProductSerializer
    permission_classes = (permissions.AllowAny,)

    def get_queryset(self):
        qs = Product.objects.filter(is_sold=False)
        q = self.request.query_params.get('q')
        condition = self.request.query_params.get('condition')
        sort = self.request.query_params.get('sort', '-created_at')
        if q:
            from django.db.models import Q
            qs = qs.filter(Q(name__icontains=q) | Q(description__icontains=q))
        if condition:
            qs = qs.filter(condition=condition)
        valid_sorts = ['-created_at', 'price', '-price', 'name']
        if sort in valid_sorts:
            qs = qs.order_by(sort)
        return qs


class ProductDetailAPIView(generics.RetrieveAPIView):
    """GET /api/products/<id>/ — single product."""
    serializer_class = ProductSerializer
    permission_classes = (permissions.AllowAny,)
    queryset = Product.objects.all()


class ProductCreateAPIView(generics.CreateAPIView):
    """POST /api/products/ — create listing (auth required)."""
    serializer_class = ProductCreateSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def perform_create(self, serializer):
        product = serializer.save(seller=self.request.user)
        Sale.objects.create(seller=self.request.user, product=product,
                            item_name=product.name, price=product.price)
        logger.info(f'API: product created id={product.id} by {self.request.user.username}')


class ProductUpdateDeleteAPIView(generics.RetrieveUpdateDestroyAPIView):
    """GET/PATCH/DELETE /api/products/<id>/manage/ — owner or admin only."""
    serializer_class = ProductCreateSerializer
    permission_classes = (permissions.IsAuthenticated, IsSellerOrAdmin)
    queryset = Product.objects.all()


class MyListingsAPIView(generics.ListAPIView):
    """GET /api/my/listings/ — current user's listings."""
    serializer_class = ProductSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        return Product.objects.filter(seller=self.request.user)


class MyPurchasesAPIView(generics.ListAPIView):
    """GET /api/my/purchases/ — current user's purchases."""
    serializer_class = PurchaseSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        return Purchase.objects.filter(user=self.request.user)


# ─── PayPal payment endpoints ─────────────────────────────────────────────────

def _get_paypal_access_token():
    """Exchange client credentials for a PayPal v2 access token."""
    import requests as http_requests
    from base64 import b64encode

    base_url = 'https://api-m.sandbox.paypal.com' if settings.PAYPAL_MODE == 'sandbox' else 'https://api-m.paypal.com'
    credentials = b64encode(
        f'{settings.PAYPAL_CLIENT_ID}:{settings.PAYPAL_CLIENT_SECRET}'.encode()
    ).decode()
    resp = http_requests.post(
        f'{base_url}/v1/oauth2/token',
        headers={
            'Authorization': f'Basic {credentials}',
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        data='grant_type=client_credentials',
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()['access_token'], base_url


class PayPalCreateOrderAPIView(APIView):
    """
    POST /api/payments/create-order/
    Body: { "product_id": 1 }
    Returns: { "order_id": "..." }  — v2 Orders API
    """
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request):
        import requests as http_requests

        product_id = request.data.get('product_id')
        if not product_id:
            return Response({'error': 'product_id required.'}, status=400)

        try:
            product = Product.objects.get(id=int(product_id), is_sold=False)
        except (Product.DoesNotExist, ValueError):
            return Response({'error': 'Product not found or already sold.'}, status=404)

        if product.seller == request.user:
            return Response({'error': "You can't buy your own listing."}, status=400)

        if not settings.PAYPAL_CLIENT_ID or not settings.PAYPAL_CLIENT_SECRET:
            return Response({
                'error': 'PayPal not configured.',
                'hint': 'Set PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET env vars.'
            }, status=503)

        try:
            access_token, base_url = _get_paypal_access_token()

            resp = http_requests.post(
                f'{base_url}/v2/checkout/orders',
                headers={
                    'Authorization': f'Bearer {access_token}',
                    'Content-Type': 'application/json',
                },
                json={
                    'intent': 'CAPTURE',
                    'purchase_units': [{
                        'reference_id': str(product.id),
                        'description': f'SerpantSupply: {product.name[:127]}',
                        'amount': {
                            'currency_code': 'USD',
                            'value': str(product.price),
                        },
                    }],
                },
                timeout=10,
            )
            resp.raise_for_status()
            order = resp.json()
            order_id = order['id']

            # Store in session so execute can look up the product
            request.session['paypal_order_id'] = order_id
            request.session['paypal_product_id'] = product.id

            paypal_logger.info(
                f'PayPal v2 order created: order_id={order_id} '
                f'product={product.id} buyer={request.user.username}'
            )
            return Response({'order_id': order_id})

        except Exception as e:
            paypal_logger.error(f'PayPal create-order exception: {e}')
            return Response({'error': 'PayPal service error.', 'detail': str(e)}, status=502)


class PayPalExecuteOrderAPIView(APIView):
    """
    GET /api/payments/execute/?orderID=...&product_id=...
    Called by PayPal redirect after user approves (v2 capture flow).
    """
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request):
        import requests as http_requests

        order_id = request.query_params.get('orderID') or request.session.get('paypal_order_id')
        product_id = request.query_params.get('product_id') or request.session.get('paypal_product_id')

        if not all([order_id, product_id]):
            return Response({'error': 'Missing payment parameters.'}, status=400)

        try:
            product = Product.objects.get(id=int(product_id), is_sold=False)
        except (Product.DoesNotExist, ValueError):
            return Response({'error': 'Product no longer available.'}, status=404)

        try:
            access_token, base_url = _get_paypal_access_token()

            resp = http_requests.post(
                f'{base_url}/v2/checkout/orders/{order_id}/capture',
                headers={
                    'Authorization': f'Bearer {access_token}',
                    'Content-Type': 'application/json',
                },
                timeout=10,
            )
            resp.raise_for_status()
            capture = resp.json()

            if capture.get('status') == 'COMPLETED':
                product.is_sold = True
                product.save()
                Purchase.objects.create(user=request.user, product=product)
                Sale.objects.filter(product=product).update(buyer=request.user)
                request.session.pop('paypal_order_id', None)
                request.session.pop('paypal_product_id', None)
                paypal_logger.info(
                    f'PayPal v2 order captured: order_id={order_id} '
                    f'product={product.id} buyer={request.user.username}'
                )
                from django.shortcuts import redirect
                from django.contrib import messages
                messages.success(request, f'Payment successful! You purchased "{product.name}".')
                return redirect('profile')
            else:
                paypal_logger.error(f'PayPal capture status unexpected: {capture.get("status")} — {capture}')
                return Response({'error': 'Payment capture failed.', 'detail': capture.get('status')}, status=502)

        except Exception as e:
            paypal_logger.error(f'PayPal execute exception: {e}')
            return Response({'error': 'PayPal service error.', 'detail': str(e)}, status=502)


# ─── Admin endpoints ─────────────────────────────────────────────────────────

class AdminUserListAPIView(generics.ListAPIView):
    """GET /api/admin/users/ — admin only."""
    serializer_class = UserSerializer
    permission_classes = (permissions.IsAuthenticated, IsAdminUser)
    queryset = User.objects.all().order_by('-date_joined')


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated, IsAdminUser])
def admin_stats(request):
    """GET /api/admin/stats/ — dashboard numbers."""
    return Response({
        'total_users': User.objects.count(),
        'total_products': Product.objects.count(),
        'active_listings': Product.objects.filter(is_sold=False).count(),
        'sold_listings': Product.objects.filter(is_sold=True).count(),
        'total_purchases': Purchase.objects.count(),
    })
