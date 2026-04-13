import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.conf import settings
from .models import Product, Purchase, Sale
from .forms import ProductForm

logger = logging.getLogger('serpantsupply')

def home(request):
    query = request.GET.get('q', '')
    condition = request.GET.get('condition', '')
    sort = request.GET.get('sort', '-created_at')
    
    products = Product.objects.filter(is_sold=False)
    
    if query:
        products = products.filter(Q(name__icontains=query) | Q(description__icontains=query))
    if condition:
        products = products.filter(condition=condition)
        
    valid_sorts = ['-created_at', 'price', '-price', 'name']
    if sort in valid_sorts:
        products = products.order_by(sort)
        
    return render(request, 'marketplace/home.html', {
        'products': products, 
        'query': query, 
        'condition': condition, 
        'sort': sort,
    })

def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk)
    return render(request, 'marketplace/product_detail.html', {'product': product})

@login_required
def create_listing(request):
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            product = form.save(commit=False)
            product.seller = request.user
            product.save()
            Sale.objects.create(
                seller=request.user, 
                product=product,
                item_name=product.name, 
                price=product.price
            )
            logger.info(f'Product listed: id={product.id} by {request.user.username}')
            messages.success(request, f'"{product.name}" listed successfully!')
            return redirect('product_detail', pk=product.pk)
    else:
        form = ProductForm()
    return render(request, 'marketplace/create_listing.html', {'form': form})

@login_required
def edit_listing(request, pk):
    product = get_object_or_404(Product, pk=pk, seller=request.user)
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            form.save()
            messages.success(request, 'Listing updated successfully!')
            return redirect('product_detail', pk=product.pk)
    else:
        form = ProductForm(instance=product)
    return render(request, 'marketplace/edit_listing.html', {'form': form, 'product': product})

@login_required
def delete_listing(request, pk):
    product = get_object_or_404(Product, pk=pk, seller=request.user)
    if request.method == 'POST':
        product.delete()
        messages.success(request, 'Listing deleted.')
        return redirect('home')
    return render(request, 'marketplace/confirm_delete.html', {'product': product})

@login_required
def buy_product(request, pk):
    product = get_object_or_404(Product, pk=pk, is_sold=False)

    if product.seller == request.user:
        messages.error(request, "You can't buy your own listing.")
        return redirect('product_detail', pk=pk)

    # Fetch credentials safely from settings
    client_id = getattr(settings, 'PAYPAL_CLIENT_ID', None)
    client_secret = getattr(settings, 'PAYPAL_CLIENT_SECRET', None)

    # Logic: Only configured if both keys exist and aren't empty strings
    paypal_configured = bool(client_id and client_secret)

    # --- DEBUGGING LOGS (Check your terminal/console) ---
    print("--- PAYPAL DEBUG ---")
    print(f"Client ID: {client_id}")
    print(f"Configured Status: {paypal_configured}")
    # ----------------------------------------------------

    if request.method == 'POST' and not paypal_configured:
        # Dev fallback: instant purchase without payment
        product.is_sold = True
        product.save()
        Purchase.objects.create(user=request.user, product=product)
        Sale.objects.filter(product=product).update(buyer=request.user)
        logger.info(f'Dev purchase: product={product.id} buyer={request.user.username}')
        messages.success(request, f'You purchased "{product.name}"! (dev mode)')
        return redirect('profile')

    return render(request, 'marketplace/buy_confirm.html', {
        'product': product,
        'paypal_configured': paypal_configured,
        'paypal_client_id': client_id,
    })