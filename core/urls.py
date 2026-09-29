from django.urls import path

from accounts import views as accounts
from cart import views as cart
from catalog import views as catalog
from orders import views as orders

urlpatterns = [
    # session & sign-in
    path("auth/csrf", accounts.CsrfView.as_view()),
    path("auth/config", accounts.AuthConfigView.as_view()),
    path("auth/me", accounts.MeView.as_view()),
    path("auth/signup", accounts.SignupView.as_view()),
    path("auth/signin", accounts.SigninView.as_view()),
    path("auth/signout", accounts.SignoutView.as_view()),
    path("auth/otp/send", accounts.OtpSendView.as_view()),
    path("auth/otp/verify", accounts.OtpVerifyView.as_view()),
    path("auth/google/start", accounts.GoogleStartView.as_view()),
    path("auth/google/callback", accounts.GoogleCallbackView.as_view()),
    path("auth/password/forgot", accounts.ForgotPasswordView.as_view()),
    path("auth/password/reset", accounts.ResetPasswordView.as_view()),
    path("auth/password/change", accounts.ChangePasswordView.as_view()),
    path("auth/notifications", accounts.NotificationsView.as_view()),
    path("shell", accounts.ShellView.as_view()),
    # catalog & content
    path("products", catalog.ProductListView.as_view()),
    path("products/<slug:slug>", catalog.ProductDetailView.as_view()),
    path("products/<slug:slug>/reviews", catalog.ProductReviewsView.as_view()),
    path("categories", catalog.CategoryListView.as_view()),
    path("brands", catalog.BrandListView.as_view()),
    path("bundles", catalog.BundleListView.as_view()),
    path("settings", catalog.StoreSettingsView.as_view()),
    path("pages", catalog.PageListView.as_view()),
    path("pages/<slug:slug>", catalog.PageDetailView.as_view()),
    path("contact", catalog.ContactView.as_view()),
    path("newsletter", catalog.NewsletterView.as_view()),
    # cart
    path("cart", cart.CartView.as_view()),
    path("cart/bundle", cart.BundleView.as_view()),
    path("cart/items/<int:pk>", cart.CartItemView.as_view()),
    path("cart/promo", cart.PromoView.as_view()),
    # orders & payments
    path("checkout", orders.CheckoutView.as_view()),
    path("orders", orders.OrderListView.as_view()),
    path("orders/track", orders.TrackOrderView.as_view()),
    path("orders/<str:pk>", orders.OrderDetailView.as_view()),
    path("rentals/<int:pk>/extend", orders.ExtendRentalView.as_view()),
    path("payments/start", orders.StartPaymentView.as_view()),
    path("payments/return", orders.PaymentReturnView.as_view()),
    path("payments/webhook", orders.PaymentWebhookView.as_view()),
    # account
    path("wishlist", accounts.WishlistView.as_view()),
    path("addresses", accounts.AddressListView.as_view()),
    path("addresses/<int:pk>", accounts.AddressDetailView.as_view()),
    path("payment-methods", accounts.PaymentMethodListView.as_view()),
    path("payment-methods/<int:pk>", accounts.PaymentMethodDetailView.as_view()),
]
