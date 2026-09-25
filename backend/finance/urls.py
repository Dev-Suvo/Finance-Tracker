from django.urls import path, include
from django.http import HttpResponseRedirect
from django.conf import settings
from tracker.admin import admin_site


def landing_redirect(request):
    """{% url 'landing' %} in admin templates — send users to the frontend site."""
    return HttpResponseRedirect(settings.FRONTEND_URL)


urlpatterns = [
    path('api/', include('tracker.urls')),
    path('admin/', admin_site.urls),
    path('landing/', landing_redirect, name='landing'),
]