from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from . import views

urlpatterns = [
    # ── Auth / JWT ─────────────────────────────────────────────────────────
    path('auth/register/',  views.RegisterAPIView.as_view(),         name='api_register'),
    path('auth/login/',     TokenObtainPairView.as_view(),           name='api_token_obtain'),
    path('auth/refresh/',   TokenRefreshView.as_view(),              name='api_token_refresh'),
    path('auth/me/',        views.MeAPIView.as_view(),               name='api_me'),

    # ── Products ───────────────────────────────────────────────────────────
    path('products/',               views.ProductListAPIView.as_view(),         name='api_products'),
    path('products/create/',        views.ProductCreateAPIView.as_view(),       name='api_product_create'),
    path('products/<int:pk>/',      views.ProductDetailAPIView.as_view(),       name='api_product_detail'),
    path('products/<int:pk>/manage/', views.ProductUpdateDeleteAPIView.as_view(), name='api_product_manage'),

    # ── My Account ─────────────────────────────────────────────────────────
    path('my/listings/',   views.MyListingsAPIView.as_view(),   name='api_my_listings'),
    path('my/purchases/',  views.MyPurchasesAPIView.as_view(),  name='api_my_purchases'),

    # ── PayPal Payments ────────────────────────────────────────────────────
    path('payments/create-order/', views.PayPalCreateOrderAPIView.as_view(),  name='api_paypal_create'),
    path('payments/execute/',      views.PayPalExecuteOrderAPIView.as_view(), name='api_paypal_execute'),

    # ── Admin ──────────────────────────────────────────────────────────────
    path('admin/users/', views.AdminUserListAPIView.as_view(), name='api_admin_users'),
    path('admin/stats/', views.admin_stats,                    name='api_admin_stats'),
]
