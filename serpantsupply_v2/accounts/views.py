import random
import logging
from django.shortcuts import render, redirect
from django.core.mail import send_mail, BadHeaderError
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.conf import settings as django_settings
from .models import Email2FACode

logger = logging.getLogger('serpantsupply')
security_logger = logging.getLogger('serpantsupply.security')


def _email_configured():
    """Returns True only when real SMTP credentials exist."""
    return bool(django_settings.EMAIL_HOST_USER and django_settings.EMAIL_HOST_PASSWORD)


def send_2fa_code(request, user):
    """
    Generate code, save to DB, attempt to email.
    Returns (code, email_sent: bool).
    """
    code = str(random.randint(100000, 999999))
    Email2FACode.objects.filter(user=user).delete()
    Email2FACode.objects.create(user=user, code=code)
    request.session['2fa_user_id'] = user.id

    email_sent = False
    try:
        send_mail(
            subject='Your SerpantSupply Verification Code',
            message=(
                f'Hi {user.username},\n\n'
                f'Your verification code is: {code}\n\n'
                f'This code expires in 5 minutes.\n\n'
                f'If you did not request this, please ignore this email.'
            ),
            from_email=django_settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
        email_sent = True
        logger.info(f'2FA code emailed to user {user.username} ({user.email[:3]}***)')
    except BadHeaderError:
        logger.error(f'BadHeaderError sending 2FA to {user.username}')
    except Exception as e:
        logger.warning(f'2FA email failed for {user.username}: {type(e).__name__}: {e}')

    return code, email_sent


@require_http_methods(["GET", "POST"])
def login_view(request):
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)

        if user is not None:
            security_logger.info(f'Successful login attempt for user: {username}')

            if not user.email:
                login(request, user)
                messages.success(request, f'Welcome back, {user.username}!')
                return redirect('home')

            code, email_sent = send_2fa_code(request, user)

            if not _email_configured():
                # Dev fallback: show code on screen
                request.session['2fa_dev_code'] = code
                messages.warning(request, 'Dev mode: no email configured — your code is shown below.')
            elif email_sent:
                email = user.email
                parts = email.split('@')
                masked = parts[0][0] + '***@' + parts[1] if len(parts[0]) > 1 else email
                messages.success(request, f'Verification code sent to {masked}')
            else:
                # Email configured but send failed — still show code so user isn't locked out
                request.session['2fa_dev_code'] = code
                messages.error(request, 'Could not send email. Your code is shown below for now.')

            return redirect('verify_2fa')
        else:
            security_logger.warning(f'Failed login attempt for username: {username}')
            messages.error(request, 'Invalid username or password.')

    return render(request, 'accounts/login.html')


@require_http_methods(["GET", "POST"])
def verify_2fa(request):
    user_id = request.session.get('2fa_user_id')
    if not user_id:
        messages.error(request, 'Session expired. Please log in again.')
        return redirect('login')

    # dev_code only shown when email isn't configured OR email failed
    dev_code = request.session.get('2fa_dev_code')

    if request.method == 'POST':
        entered_code = request.POST.get('code', '').strip()
        try:
            user = User.objects.get(id=user_id)
            fa_code = Email2FACode.objects.filter(user=user).latest('created_at')

            if fa_code.is_expired():
                messages.error(request, 'Code expired. Please sign in again.')
                Email2FACode.objects.filter(user=user).delete()
                request.session.pop('2fa_dev_code', None)
                security_logger.info(f'Expired 2FA code for user id={user_id}')
                return redirect('login')

            if entered_code == fa_code.code:
                Email2FACode.objects.filter(user=user).delete()
                request.session.pop('2fa_user_id', None)
                request.session.pop('2fa_dev_code', None)
                login(request, user)
                security_logger.info(f'2FA verified for user: {user.username}')
                messages.success(request, f'Welcome back, {user.username}!')
                return redirect('home')
            else:
                security_logger.warning(f'Wrong 2FA code entered for user id={user_id}')
                messages.error(request, 'Wrong code. Please try again.')
        except (User.DoesNotExist, Email2FACode.DoesNotExist):
            messages.error(request, 'Session expired. Please sign in again.')
            return redirect('login')

    return render(request, 'accounts/verify_2fa.html', {
        'dev_code': dev_code,
        'dev_mode': not _email_configured(),
        'email_configured': _email_configured(),
    })


@require_http_methods(["GET", "POST"])
def resend_2fa(request):
    user_id = request.session.get('2fa_user_id')
    if not user_id:
        return redirect('login')
    try:
        user = User.objects.get(id=user_id)
        code, email_sent = send_2fa_code(request, user)
        if not _email_configured() or not email_sent:
            request.session['2fa_dev_code'] = code
        else:
            request.session.pop('2fa_dev_code', None)
        messages.success(request, 'A new code has been sent.')
    except User.DoesNotExist:
        return redirect('login')
    return redirect('verify_2fa')


@require_http_methods(["GET", "POST"])
def register_view(request):
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password1 = request.POST.get('password1', '')
        password2 = request.POST.get('password2', '')

        if not all([username, email, password1, password2]):
            messages.error(request, 'All fields are required.')
        elif password1 != password2:
            messages.error(request, 'Passwords do not match.')
        elif len(password1) < 8:
            messages.error(request, 'Password must be at least 8 characters.')
        elif User.objects.filter(username=username).exists():
            messages.error(request, 'Username already taken.')
        elif User.objects.filter(email=email).exists():
            messages.error(request, 'Email already registered.')
        else:
            User.objects.create_user(username=username, email=email, password=password1)
            logger.info(f'New user registered: {username}')
            messages.success(request, 'Account created! Please sign in.')
            return redirect('login')

    return render(request, 'accounts/register.html')


@login_required
def logout_view(request):
    logger.info(f'User logged out: {request.user.username}')
    logout(request)
    messages.success(request, 'You have been signed out.')
    return redirect('login')


@login_required
def profile_view(request):
    from marketplace.models import Product, Purchase
    user_listings = Product.objects.filter(seller=request.user).order_by('-created_at')
    user_purchases = Purchase.objects.filter(user=request.user).order_by('-purchased_at')
    return render(request, 'accounts/profile.html', {
        'user_listings': user_listings,
        'user_purchases': user_purchases,
    })
