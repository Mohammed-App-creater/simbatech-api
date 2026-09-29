from django.urls import path

from accounts import views as accounts
from cart import views as cart
from catalog import views as catalog
from orders import views as orders

urlpatterns = [
    # session
    path("auth/csrf", accounts.CsrfView.as_view()),
    path("auth/me", accounts.MeView.as_view()),
    path("auth/signup", accounts.SignupView.as_view()),
    path("auth/signin", accounts.SigninView.as_view()),
    path("auth/signout", accounts.SignoutView.as_view()),
    path("shell", accounts.ShellView.as_view()),
    # catalog
    path("products", catalog.ProductListView.as_view()),
    path("products/<slug:slug>", catalog.ProductDetailView.as_view()),
    path("categories", catalog.CategoryListView.as_view()),
    path("brands", catalog.BrandListView.as_view()),
    path("newsletter", catalog.NewsletterView.as_view()),
    # cart
    path("cart", cart.CartView.as_view()),
    path("cart/items/<int:pk>", cart.CartItemView.as_view()),
    path("cart/promo", cart.PromoView.as_view()),
    # orders
    path("checkout", orders.CheckoutView.as_view()),
    path("orders", orders.OrderListView.as_view()),
    path("orders/<str:pk>", orders.OrderDetailView.as_view()),
    path("rentals/<int:pk>/extend", orders.ExtendRentalView.as_view()),
    # account
    path("wishlist", accounts.WishlistView.as_view()),
    path("addresses", accounts.AddressListView.as_view()),
    path("addresses/<int:pk>", accounts.AddressDetailView.as_view()),
]
