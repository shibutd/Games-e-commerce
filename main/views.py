from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import DetailView, ListView
from django.utils import timezone
from .models import Item, OrderItem, Order


class HomeView(ListView):
    model = Item
    paginate_by = 10
    template_name = 'home.html'


class ItemDetailView(DetailView):
    model = Item
    template_name = 'product.html'


def checkout(request):
    return render(request, 'checkout.html')


def add_to_cart(request, slug):
    item = get_object_or_404(Item, slug=slug)
    order_item, created = OrderItem.objects.get_or_create(
        user=request.user, item=item, ordered=False)

    # Check if order exists
    order_qs = Order.objects.filter(user=request.user, ordered=False)
    if order_qs.exists():
        order = order_qs[0]
        # If Item already in the order add another instance of Item
        if order.items.filter(item__slug=item.slug).exists():
            order_item.quantity += 1
            order_item.save()
            messages.info(request, "This item's quantity was updated.")

        else:
            order.items.add(order_item)
            messages.info(request, 'This item was added to your cart.')
    else:
        order = Order.objects.create(user=request.user,
                                     ordered_date=timezone.now())
        order.items.add(order_item)
        messages.info(request, 'This item was added to your cart.')
    return redirect('main:product', slug=slug)


def remove_from_cart(request, slug):
    item = get_object_or_404(Item, slug=slug)
    order_qs = Order.objects.filter(user=request.user, ordered=False)
    if order_qs.exists():
        order = order_qs[0]
        # if the item in the order than remove it
        if order.items.filter(item__slug=item.slug).exists():
            order_item = OrderItem.objects.filter(
                user=request.user, item=item, ordered=False)[0]
            order.items.remove(order_item)
            messages.info(request, 'This item was removed from your cart.')
            return redirect('main:product', slug=slug)
        # if the item is NOT in the order - dislpay message
        else:
            messages.info(request, 'This item is not in your cart.')
            return redirect('main:product', slug=slug)
    else:
        # This user has no orders exists
        messages.info(request, 'You have no active orders.')
        return redirect('main:product', slug=slug)
