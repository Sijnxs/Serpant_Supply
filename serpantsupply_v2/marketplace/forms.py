from django import forms
from .models import Product


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['name', 'price', 'description', 'image', 'condition']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 bg-gray-900 border border-gray-700 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 transition',
                'placeholder': 'Product name',
            }),
            'price': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-3 bg-gray-900 border border-gray-700 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 transition',
                'placeholder': '0.00',
                'step': '0.01',
                'min': '0',
            }),
            'description': forms.Textarea(attrs={
                'class': 'w-full px-4 py-3 bg-gray-900 border border-gray-700 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 transition resize-none',
                'rows': 5,
                'placeholder': 'Describe your item in detail...',
            }),
            'condition': forms.Select(attrs={
                'class': 'w-full px-4 py-3 bg-gray-900 border border-gray-700 rounded-xl text-white focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 transition',
            }),
            'image': forms.FileInput(attrs={
                'class': 'hidden',
                'accept': 'image/*',
            }),
        }
