from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('product/<int:pk>/', views.product_detail, name='product_detail'),
    path('sell/', views.create_listing, name='create_listing'),
    path('product/<int:pk>/edit/', views.edit_listing, name='edit_listing'),
    path('product/<int:pk>/delete/', views.delete_listing, name='delete_listing'),
    path('product/<int:pk>/buy/', views.buy_product, name='buy_product'),
]
