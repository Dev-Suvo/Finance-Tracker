from django.urls import path, include
from tracker.admin import admin_site

urlpatterns = [
    path('api/', include('tracker.urls')),
    path('admin/', admin_site.urls),
]