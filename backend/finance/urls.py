from django.urls import path, include
from django.http import HttpResponseRedirect, JsonResponse
from django.conf import settings
from tracker.admin import admin_site


def landing_redirect(request):
    """{% url 'landing' %} in admin templates — send users to the frontend site."""
    return HttpResponseRedirect(settings.FRONTEND_URL)


def health(request):
    """Always-200 liveness endpoint for cron-job.org / uptime monitors.
    Monitors treat any non-2xx (including /landing/'s 302) as a failure,
    which previously got the keep-alive job auto-disabled."""
    return JsonResponse({'status': 'ok'})


urlpatterns = [
    path('api/', include('tracker.urls')),
    path('admin/', admin_site.urls),
    path('landing/', landing_redirect, name='landing'),
    path('health/', health, name='health'),
]