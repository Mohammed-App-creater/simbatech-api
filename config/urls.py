from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path


def health(request):
    """Answers the hosting platform's checks on / (and anyone opening the API's address)."""
    return JsonResponse({"ok": True, "service": "simbatech-api"})


urlpatterns = [
    path("", health),
    path("admin/", admin.site.urls),
    path("api/", include("core.urls")),
]

admin.site.site_header = "Simbatech admin"
admin.site.site_title = "Simbatech"
admin.site.index_title = "Store management"
