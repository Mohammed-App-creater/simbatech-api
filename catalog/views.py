from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.errors import ApiError
from orders.serializers import ContactSerializer, ReviewSerializer

from .dto import brand_list, bundle_list, category_list, page_dto, product_dto, product_queryset, reviews_payload, store_dto
from .models import ContactMessage, NewsletterSubscriber, Page, Product, Review


class ProductListView(APIView):
    """
    GET /api/products?q=&mode=buy|rent&dept=&brand=&min=&max=&deals=1&sort=featured|price-asc|price-desc|rating
    The catalog is small, so filtering happens in memory on the full list.
    """

    def get(self, request):
        params = request.query_params
        q = (params.get("q") or "").strip().lower()
        mode = params.get("mode")
        depts = params.getlist("dept")
        brands = params.getlist("brand")
        sort = params.get("sort") or "featured"
        try:
            lo = int(params.get("min") or 0)
            hi = int(params.get("max")) if params.get("max") else None
        except ValueError:
            raise ApiError("min and max must be whole numbers", 422)

        items = [product_dto(p) for p in product_queryset()]
        if q:
            items = [p for p in items if any(q in s.lower() for s in (p["name"], p["cat"], p["dept"], p["brand"], p["description"]))]
        if mode == "rent":
            items = [p for p in items if p.get("rent")]
        elif mode == "buy":
            items = [p for p in items if not p["rentOnly"]]
        if params.get("deals") in ("1", "true"):
            items = [p for p in items if p.get("was")]
        if depts:
            items = [p for p in items if p["dept"] in depts or p["cat"] in depts]
        if brands:
            items = [p for p in items if p["brand"] in brands]
        items = [p for p in items if p["buy"] >= lo and (hi is None or p["buy"] <= hi)]
        if sort == "price-asc":
            items.sort(key=lambda p: p["buy"])
        elif sort == "price-desc":
            items.sort(key=lambda p: -p["buy"])
        elif sort == "rating":
            items.sort(key=lambda p: -float(p["rating"]))
        return Response({"items": items, "count": len(items)})


class ProductDetailView(APIView):
    def get(self, request, slug):
        product = product_queryset().filter(slug=slug).first()
        if not product:
            raise ApiError("Product not found", 404)
        return Response(product_dto(product))


class ProductReviewsView(APIView):
    def _product(self, slug):
        product = Product.objects.filter(slug=slug).first()
        if not product:
            raise ApiError("Product not found", 404)
        return product

    def get(self, request, slug):
        user = request.user if request.user.is_authenticated else None
        return Response(reviews_payload(self._product(slug), user))

    def post(self, request, slug):
        """
        Write (or update) your review. Signed-in customers only, one review per product.
        A new or edited review waits for staff approval before it shows on the site.
        """
        if not request.user.is_authenticated:
            raise ApiError("Please sign in to write a review", 401)
        product = self._product(slug)
        s = ReviewSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        Review.objects.update_or_create(product=product, user=request.user, defaults={**s.validated_data, "status": Review.Status.PENDING})
        product.recompute_rating()
        return Response(reviews_payload(product, request.user), status=status.HTTP_201_CREATED)

    def delete(self, request, slug):
        if not request.user.is_authenticated:
            raise ApiError("Please sign in first", 401)
        product = self._product(slug)
        Review.objects.filter(product=product, user=request.user).delete()
        product.recompute_rating()
        return Response(reviews_payload(product, request.user))


class CategoryListView(APIView):
    def get(self, request):
        return Response({"items": category_list()})


class BrandListView(APIView):
    def get(self, request):
        return Response({"items": brand_list()})


class BundleListView(APIView):
    def get(self, request):
        return Response({"items": bundle_list()})


class StoreSettingsView(APIView):
    def get(self, request):
        return Response(store_dto())


class PageListView(APIView):
    def get(self, request):
        return Response({"items": [{"slug": p.slug, "title": p.title, "summary": p.summary} for p in Page.objects.all()]})


class PageDetailView(APIView):
    def get(self, request, slug):
        page = Page.objects.filter(slug=slug).first()
        if not page:
            raise ApiError("Page not found", 404)
        return Response(page_dto(page))


class ContactView(APIView):
    def post(self, request):
        s = ContactSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        ContactMessage.objects.create(**s.validated_data)
        return Response({"ok": True}, status=status.HTTP_201_CREATED)


class NewsletterSerializer(serializers.Serializer):
    email = serializers.EmailField(error_messages={"invalid": "Enter a valid email address", "required": "Enter your email address"})


class NewsletterView(APIView):
    def post(self, request):
        s = NewsletterSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        NewsletterSubscriber.objects.get_or_create(email=s.validated_data["email"].strip().lower())
        return Response({"ok": True}, status=status.HTTP_201_CREATED)
