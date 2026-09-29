from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("core.urls")),
]

admin.site.site_header = "Simbatech admin"
admin.site.site_title = "Simbatech"
admin.site.index_title = "Store management"
