import string
import random
import stripe
from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponseRedirect
from django.views.generic import DetailView, ListView, View
from django.utils import timezone
from .models import (Item, OrderItem, Order, Address,
                     Payment, Coupon, Refund)
from .forms import CheckoutForm, CouponForm, RefundForm


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
        shipping_address_qs = Address.objects.filter(
            user=self.request.user,
            address_type='S',
            default=True,
        )
        if shipping_address_qs.exists():
            context.update(
                {'shipping_address': shipping_address_qs[0]})

        billing_address_qs = Address.objects.filter(
            user=self.request.user,
            address_type='B',
            default=True,
        )
        if billing_address_qs.exists():
            context.update(
                {'billing_address': billing_address_qs[0]})

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
            shipping_address = self.get_shipping_address(form)
            if isinstance(shipping_address, HttpResponseRedirect):
                return shipping_address

            shipping_address.save()

            order.shipping_address = shipping_address
            order.save()

            same_shipping_address = form.cleaned_data.get(
                'same_shipping_address')

            if same_shipping_address:
                billing_address = shipping_address
                billing_address.pk = None
                billing_address.address_type = 'B'
            else:
                billing_address = self.get_billing_address(form)
                if isinstance(billing_address, HttpResponseRedirect):
                    return billing_address

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

    def get_shipping_address(self, form):
        use_default_shipping = form.cleaned_data.get(
            'use_default_shipping')
        if use_default_shipping:
            default_shipping_qs = Address.objects.filter(
                user=self.request.user,
                address_type='S',
                default=True,
            )
            if default_shipping_qs.exists():
                shipping_address = default_shipping_qs[0]
            else:
                messages.warning(
                    self.request, 'You have no default shipping address.')
                return redirect('main:checkout')
        else:
            shipping_address1 = form.cleaned_data.get(
                'shipping_address')
            shipping_address2 = form.cleaned_data.get(
                'shipping_address2')
            shipping_country = form.cleaned_data.get(
                'shipping_country')
            shipping_zip = form.cleaned_data.get(
                'shipping_zip')

            if form.validate_input(
                    [shipping_address1, shipping_country, shipping_zip]):
                shipping_address = Address(
                    user=self.request.user,
                    street_address=shipping_address1,
                    apartment_address=shipping_address2,
                    country=shipping_country,
                    zip_address=shipping_zip,
                    address_type='S',
                )
                set_default_shipping = form.cleaned_data.get(
                    'set_default_shipping')
                if set_default_shipping:
                    self.update_users_default_addresses(
                        address_type='S')
                    shipping_address.default = True
            else:
                messages.warning(
                    self.request,
                    'Please fill in the required shipping address fields.'
                )
                return redirect('main:checkout')
        return shipping_address

    def get_billing_address(self, form):
        use_default_billing = form.cleaned_data.get('use_default_billing')
        if use_default_billing:
            default_billing_qs = Address.objects.filter(
                user=self.request.user,
                address_type='B',
                default=True,
            )
            if default_billing_qs.exists():
                billing_address = default_billing_qs[0]
            else:
                messages.warning(
                    self.request, 'You have no default billing address.')
                return redirect('main:checkout')
        else:
            billing_address1 = form.cleaned_data.get(
                'billing_address')
            billing_address2 = form.cleaned_data.get(
                'billing_address2')
            billing_country = form.cleaned_data.get(
                'billing_country')
            billing_zip = form.cleaned_data.get(
                'billing_zip')

            if form.validate_input(
                    [billing_address1, billing_country, billing_zip]):
                billing_address = Address(
                    user=self.request.user,
                    street_address=billing_address1,
                    apartment_address=billing_address2,
                    country=billing_country,
                    zip_address=billing_zip,
                    address_type='B',
                )
                set_default_billing = form.cleaned_data.get(
                    'set_default_billing')
                if set_default_billing:
                    self.update_users_default_addresses(
                        address_type='B')
                    billing_address.default = True
            else:
                messages.warning(
                    self.request,
                    'Please fill in the required billing address fields.'
                )
                return redirect('main:checkout')
        return billing_address

    def update_users_default_addresses(self, address_type):
        user_default_addresses = Address.objects.filter(
            user=self.request.user,
            address_type=address_type,
            default=True,
        )
        user_default_addresses.update(default=False)
        for address in user_default_addresses:
            address.save()


class PaymentView(LoginRequiredMixin, View):

    def get(self, *args, **kwargs):
        try:
            order = Order.objects.get(
                user=self.request.user, ordered=False)
        except ObjectDoesNotExist:
            messages.warning(self.request, 'You have no active order.')
            return redirect('main:home')
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
        try:
            order = Order.objects.get(user=self.request.user, ordered=False)
            # token = self.request.POST.get('stripeToken')
            # amount = int(order.get_total() * 100)

            # Use Stripe's library to make requests
            # charge = stripe.Charge.create(
            #     amount=amount,  # cents
            #     currency="usd",
            #     source=token,
            # )

            # Create the payment
            payment = Payment()
            # payment.stripe_charge_id = charge['id']

            # TEMP: Create random payment number
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
            # TEMP: Create random reference code
            order.ref_code = self.create_ref_code()
            order.save()

            messages.success(self.request, 'Your order was successfully paid!')
            return redirect('main:home')
        except ObjectDoesNotExist:
            messages.warning(self.request, 'You have no active order.')
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

    @staticmethod
    def create_ref_code():
        return ''.join(random.choices(
            string.ascii_lowercase + string.digits, k=20))


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


class RequestRefundView(LoginRequiredMixin, View):

    def get(self, *args, **kwargs):
        form = RefundForm()
        context = {
            'form': form,
        }
        return render(self.request, 'refund_request.html', context)

    def post(self, *args, **kwargs):
        form = RefundForm(self.request.POST)
        if form.is_valid():
            ref_code = form.cleaned_data.get('ref_code')
            message = form.cleaned_data.get('message')
            email = form.cleaned_data.get('email')
            try:
                order = Order.objects.get(
                    ref_code=ref_code)
                order.refund_requested = True
                order.save()
            except ObjectDoesNotExist:
                messages.warning(self.request, 'This order does not exist.')
                return redirect('main:refund-request')

            refund = Refund()
            refund.message = message
            refund.email = email
            refund.order = order
            refund.save()
            messages.success(
                self.request, 'You refund request was received.')
            return redirect('main:refund-request')
