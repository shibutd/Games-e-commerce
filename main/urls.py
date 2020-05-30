from django.urls import path
from .views import (HomeView, ItemDetailView, OrderSummary,
                    checkout, add_to_cart, remove_from_cart,
                    remove_single_from_cart)


app_name = 'main'

urlpatterns = [
    path('', HomeView.as_view(), name='home'),
    path('product/<slug>/', ItemDetailView.as_view(), name='product'),
    path('order-summary/', OrderSummary.as_view(), name='order-summary'),
    path('checkout/', checkout, name='checkout'),
    path('add-to-cart/<slug>/', add_to_cart, name='add-to-cart'),
    path('remove-from-cart/<slug>/', remove_from_cart,
         name='remove-from-cart'),
    path('remove-single-from-cart/<slug>', remove_single_from_cart,
         name='remove-single-from-cart'),
]
