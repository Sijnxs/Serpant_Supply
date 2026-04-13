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

class PayPalCreateOrderAPIView(APIView):
    """
    POST /api/payments/create-order/
    Body: { "product_id": 1 }
    Returns: { "order_id": "...", "approve_url": "..." }
    """
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request):
        product_id = request.data.get('product_id')
        if not product_id:
            return Response({'error': 'product_id required.'}, status=400)

        try:
            product = Product.objects.get(id=product_id, is_sold=False)
        except Product.DoesNotExist:
            return Response({'error': 'Product not found or already sold.'}, status=404)

        if product.seller == request.user:
            return Response({'error': "You can't buy your own listing."}, status=400)

        # Check PayPal credentials
        if not settings.PAYPAL_CLIENT_ID or not settings.PAYPAL_CLIENT_SECRET:
            return Response({
                'error': 'PayPal not configured.',
                'hint': 'Set PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET env vars.'
            }, status=503)

        try:
            import paypalrestsdk
            paypalrestsdk.configure({
                'mode': settings.PAYPAL_MODE,
                'client_id': settings.PAYPAL_CLIENT_ID,
                'client_secret': settings.PAYPAL_CLIENT_SECRET,
            })

            payment = paypalrestsdk.Payment({
                'intent': 'sale',
                'payer': {'payment_method': 'paypal'},
                'redirect_urls': {
                    'return_url': request.build_absolute_uri(f'/api/payments/execute/?product_id={product.id}'),
                    'cancel_url': request.build_absolute_uri(f'/product/{product.id}/'),
                },
                'transactions': [{
                    'item_list': {
                        'items': [{
                            'name': product.name[:127],
                            'sku': str(product.id),
                            'price': str(product.price),
                            'currency': 'USD',
                            'quantity': 1,
                        }]
                    },
                    'amount': {
                        'total': str(product.price),
                        'currency': 'USD',
                    },
                    'description': f'SerpantSupply purchase: {product.name[:127]}',
                }],
            })

            if payment.create():
                approve_url = next(
                    (link.href for link in payment.links if link.rel == 'approval_url'),
                    None
                )
                # Store payment+product in session for execute step
                request.session['paypal_payment_id'] = payment.id
                request.session['paypal_product_id'] = product.id
                paypal_logger.info(
                    f'PayPal order created: payment_id={payment.id} '
                    f'product={product.id} buyer={request.user.username}'
                )
                return Response({'order_id': payment.id, 'approve_url': approve_url})
            else:
                paypal_logger.error(f'PayPal payment.create() failed: {payment.error}')
                return Response({'error': 'PayPal order creation failed.', 'detail': str(payment.error)}, status=502)

        except Exception as e:
            paypal_logger.error(f'PayPal exception: {e}')
            return Response({'error': 'PayPal service error.', 'detail': str(e)}, status=502)


class PayPalExecuteOrderAPIView(APIView):
    """
    GET /api/payments/execute/?paymentId=...&PayerID=...&product_id=...
    Called by PayPal redirect after user approves.
    """
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request):
        payment_id = request.query_params.get('paymentId') or request.session.get('paypal_payment_id')
        payer_id = request.query_params.get('PayerID')
        product_id = request.query_params.get('product_id') or request.session.get('paypal_product_id')

        if not all([payment_id, payer_id, product_id]):
            return Response({'error': 'Missing payment parameters.'}, status=400)

        try:
            product = Product.objects.get(id=product_id, is_sold=False)
        except Product.DoesNotExist:
            return Response({'error': 'Product no longer available.'}, status=404)

        try:
            import paypalrestsdk
            paypalrestsdk.configure({
                'mode': settings.PAYPAL_MODE,
                'client_id': settings.PAYPAL_CLIENT_ID,
                'client_secret': settings.PAYPAL_CLIENT_SECRET,
            })

            payment = paypalrestsdk.Payment.find(payment_id)
            if payment.execute({'payer_id': payer_id}):
                product.is_sold = True
                product.save()
                Purchase.objects.create(user=request.user, product=product)
                Sale.objects.filter(product=product).update(buyer=request.user)
                request.session.pop('paypal_payment_id', None)
                request.session.pop('paypal_product_id', None)
                paypal_logger.info(
                    f'PayPal payment executed: payment_id={payment_id} '
                    f'product={product.id} buyer={request.user.username}'
                )
                # Redirect to profile with success message
                from django.shortcuts import redirect
                from django.contrib import messages
                messages.success(request, f'Payment successful! You purchased "{product.name}".')
                return redirect('profile')
            else:
                paypal_logger.error(f'PayPal execute failed: {payment.error}')
                return Response({'error': 'Payment execution failed.', 'detail': str(payment.error)}, status=502)

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
