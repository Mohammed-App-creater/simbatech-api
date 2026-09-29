from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.errors import ApiError

from .dto import brand_list, category_list, product_dto, product_queryset
from .models import NewsletterSubscriber, Product


class ProductListView(APIView):
    """
    GET /api/products?q=&mode=buy|rent&dept=&brand=&min=&max=&sort=featured|price-asc|price-desc|rating
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


class CategoryListView(APIView):
    def get(self, request):
        return Response({"items": category_list()})


class BrandListView(APIView):
    def get(self, request):
        return Response({"items": brand_list()})


class NewsletterSerializer(serializers.Serializer):
    email = serializers.EmailField(error_messages={"invalid": "Enter a valid email address", "required": "Enter your email address"})


class NewsletterView(APIView):
    def post(self, request):
        s = NewsletterSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        NewsletterSubscriber.objects.get_or_create(email=s.validated_data["email"].strip().lower())
        return Response({"ok": True}, status=status.HTTP_201_CREATED)
