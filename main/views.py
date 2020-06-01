from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import DetailView, ListView, View
from django.utils import timezone
import stripe
import random
from .models import (Item, OrderItem, Order,
                     BillingAddress, Payment, Coupon)
from .forms import CheckoutForm, CouponForm


stripe.api_key = settings.STRIPE_SECRET_KEY


class HomeView(ListView):
    model = Item
    paginate_by = 10
    template_name = 'home.html'


class ItemDetailView(DetailView):
    model = Item
    template_name = 'product.html'


class OrderSummaryView(LoginRequiredMixin, View):

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


class CheckoutView(LoginRequiredMixin, View):

    def get(self, *args, **kwargs):
        form, couponform = CheckoutForm(), CouponForm()
        try:
            order = Order.objects.get(
                user=self.request.user, ordered=False)
        except ObjectDoesNotExist:
            messages.warning(self.request, 'You have no active order.')
            return redirect('main:home')
        context = {
            'form': form,
            'couponform': couponform,
            'order': order,
            'DISPLAY_COUPON_FORM': True,
        }
        return render(self.request, 'checkout.html', context)

    def post(self, *args, **kwargs):
        form = CheckoutForm(self.request.POST or None)
        try:
            order = Order.objects.get(
                user=self.request.user, ordered=False)
        except ObjectDoesNotExist:
            messages.warning(self.request, 'You have no active order.')
            return redirect('main:home')

        if form.is_valid():
            street_address = form.cleaned_data.get('street_address')
            apartment_address = form.cleaned_data.get('apartment_address')
            country = form.cleaned_data.get('country')
            zip_address = form.cleaned_data.get('zip_address')
            # same_shipping_address = form.cleaned_data.get(
            #     'same_shipping_address')
            # save_info = form.cleaned_data.get('save_info')

            billing_address = BillingAddress(
                user=self.request.user,
                street_address=street_address,
                apartment_address=apartment_address,
                country=country,
                zip_address=zip_address,
            )
            billing_address.save()
            order.billing_address = billing_address
            order.save()

            payment_option = form.cleaned_data.get('payment_option')
            if payment_option == 'S':
                return redirect('main:payment', payment_option='stripe')
            elif payment_option == 'P':
                return redirect('main:payment', payment_option='paypal')
            else:
                messages.warning(
                    self.request, 'Invalid payment option selected.')
                return redirect('main:checkout')

        messages.warning(self.request, 'Failed checkout.')
        return redirect('main:checkout')


class PaymentView(LoginRequiredMixin, View):

    def get(self, *args, **kwargs):
        order = Order.objects.get(user=self.request.user, ordered=False)
        if order.billing_address:
            context = {
                'order': order,
                'DISPLAY_COUPON_FORM': False,
            }
            return render(self.request, 'payment.html', context)
        else:
            messages.warning(
                self.request, 'You have no billing address.')
            return redirect('main:checkout')

    def post(self, *args, **kwargs):
        order = Order.objects.get(user=self.request.user, ordered=False)
        # token = self.request.POST.get('stripeToken')
        # amount = int(order.get_total() * 100)
        try:
            # Use Stripe's library to make requests
            # charge = stripe.Charge.create(
            #     amount=amount,  # cents
            #     currency="usd",
            #     source=token,
            # )

            # Create the payment
            payment = Payment()
            # payment.stripe_charge_id = charge['id']

            # Temporary random payment number
            payment.stripe_charge_id = random.randint(0, 1000)

            payment.user = self.request.user
            payment.amount = order.get_total()
            payment.save()

            # Update order_items status to "ordered"
            order_items = order.items.all()
            order_items.update(ordered=True)
            for item in order_items:
                item.save()

            # Assign the payment to the order
            order.ordered = True
            order.payment = payment
            order.save()

            messages.success(self.request, 'Your order was successfully paid!')
            return redirect('main:home')
        except (
            stripe.error.CardError,
            stripe.error.RateLimitError,
            stripe.error.InvalidRequestError,
            stripe.error.AuthenticationError,
            stripe.error.APIConnectionError,
            stripe.error.StripeError,
        ) as e:
            messages.warning(self.request, f'{e.error.message}')
            return redirect('main:payment', payment_option='stripe')
        except Exception:
            messages.warning(
                self.request, 'Serious error occured. Please try again.')
            return redirect('main:home')


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


class AddCouponView(LoginRequiredMixin, View):

    def post(self, *args, **kwargs):
        form = CouponForm(self.request.POST or None)
        if form.is_valid():
            try:
                code = form.cleaned_data.get('code')
                order = Order.objects.get(
                    user=self.request.user, ordered=False)
                order.coupon = self.get_coupon(code)
                order.save()
                messages.success(
                    self.request, 'Successfully added coupon.')
                return redirect('main:checkout')
            except ObjectDoesNotExist:
                messages.warning(
                    self.request, 'You have no active order.')
                return redirect('main:home')

    def get_coupon(self, code):
        try:
            coupon = Coupon.objects.get(code=code)
        except ObjectDoesNotExist:
            messages.warning(
                self.request, 'This coupon does not exists.')
            return redirect('main:checkout')
        return coupon
