from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register_view, name='register'),
    path('verify-2fa/', views.verify_2fa, name='verify_2fa'),
    path('resend-2fa/', views.resend_2fa, name='resend_2fa'),
    path('profile/', views.profile_view, name='profile'),
]
