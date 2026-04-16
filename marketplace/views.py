from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.clickjacking import xframe_options_exempt
from django.contrib import messages
from django.conf import settings
from .models import Product, Purchase, Sale
from .forms import ProductForm

def home(request):
    query = request.GET.get('q', '')
    products = Product.objects.filter(is_sold=False)
    if query:
        products = products.filter(name__icontains=query)
    return render(request, 'marketplace/home.html', {
        'products': products,
        'query': query,
    })


def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk)
    return render(request, 'marketplace/product_detail.html', {
        'product': product,
    })


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
            messages.success(request, 'Listing created successfully!')
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
    return render(request, 'marketplace/edit_listing.html', {
        'form': form,
        'product': product,
    })


@login_required
def delete_listing(request, pk):
    product = get_object_or_404(Product, pk=pk, seller=request.user)
    if request.method == 'POST':
        product.delete()
        messages.success(request, 'Listing deleted successfully!')
        return redirect('home')
    return render(request, 'marketplace/confirm_delete.html', {
        'product': product,
    })


@login_required
@xframe_options_exempt
def buy_product(request, pk):
    product = get_object_or_404(Product, pk=pk)
    
    if product.seller == request.user:
        messages.error(request, "You cannot buy your own product.")
        return redirect('product_detail', pk=pk)
        
    if product.is_sold:
        messages.error(request, "This product has already been sold.")
        return redirect('product_detail', pk=pk)
        
    if request.method == 'POST':
        # Dev mode purchase
        product.is_sold = True
        product.save()
        Purchase.objects.create(user=request.user, product=product)
        Sale.objects.filter(product=product).update(buyer=request.user)
        messages.success(request, 'Purchase successful (Dev mode)!')
        # In Django usually reversed by name 'profile' or similar
        return redirect('home')

    paypal_configured = bool(getattr(settings, 'PAYPAL_CLIENT_ID', False) and getattr(settings, 'PAYPAL_CLIENT_SECRET', False))
    paypal_client_id = getattr(settings, 'PAYPAL_CLIENT_ID', '')

    return render(request, 'marketplace/buy_confirm.html', {
        'product': product,
        'paypal_configured': paypal_configured,
        'paypal_client_id': paypal_client_id,
    })
