from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import DetailView, ListView, View
from django.utils import timezone
from .models import Item, OrderItem, Order


class HomeView(ListView):
    model = Item
    paginate_by = 10
    template_name = 'home.html'


class ItemDetailView(DetailView):
    model = Item
    template_name = 'product.html'


class OrderSummary(LoginRequiredMixin, View):

    def get(self, *args, **kwargs):
        try:
            order = Order.objects.get(
                user=self.request.user, ordered=False)
            context = {
                'object': order
            }
            return render(self.request, 'order_summary.html', context)
        except ObjectDoesNotExist:
            messages.warning(self.request, 'You have no active order.')
            return redirect('main:home')


def checkout(request):
    return render(request, 'checkout.html')


@login_required
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
            # messages.info(request, "This item's quantity was updated.")
        else:
            order.items.add(order_item)
            messages.info(request, 'This item was added to your cart.')
    else:
        order = Order.objects.create(user=request.user,
                                     ordered_date=timezone.now())
        order.items.add(order_item)
        messages.info(request, 'This item was added to your cart.')
    return redirect('main:order-summary')


@login_required
def remove_single_from_cart(request, slug):
    item = get_object_or_404(Item, slug=slug)
    order_qs = Order.objects.filter(user=request.user, ordered=False)
    if order_qs.exists():
        order = order_qs[0]
        # if the item in the order than remove it
        if order.items.filter(item__slug=item.slug).exists():
            order_item = OrderItem.objects.filter(
                user=request.user, item=item, ordered=False)[0]
            if order_item.quantity > 1:
                order_item.quantity -= 1
                order_item.save()
            return redirect('main:order-summary')
        # if the item is NOT in the order - dislpay message
        else:
            messages.warning(request, 'This item is not in your cart.')
            return redirect('main:product', slug=slug)
    else:
        # This user has no orders exists
        messages.warning(request, 'You have no active orders.')
        return redirect('main:product', slug=slug)


@login_required
def remove_from_cart(request, slug):
    item = get_object_or_404(Item, slug=slug)
    order_qs = Order.objects.filter(user=request.user, ordered=False)
    if order_qs.exists():
        order = order_qs[0]
        # if the item in the order than remove it
        if order.items.filter(item__slug=item.slug).exists():
            order_item = OrderItem.objects.filter(
                user=request.user, item=item, ordered=False)[0]
            order_item.delete()
            # order.items.remove(order_item)
            messages.info(request, 'This item was removed from your cart.')
            return redirect('main:order-summary')
        # if the item is NOT in the order - dislpay message
        else:
            messages.warning(request, 'This item is not in your cart.')
            return redirect('main:product', slug=slug)
    else:
        # This user has no orders exists
        messages.warning(request, 'You have no active orders.')
        return redirect('main:product', slug=slug)
