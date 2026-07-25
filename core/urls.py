"""
URL configuration for core project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

schema_view = get_schema_view(
   openapi.Info(
      title="Real Estate API",
      default_version='v1',
      description="Backend API documentation for the Real Estate mobile app and admin dashboard.",
      contact=openapi.Contact(email="support@realestate.com"),
   ),
   public=True,
   permission_classes=(permissions.AllowAny,),
)

from django.views.generic import RedirectView

urlpatterns = [
    path('', RedirectView.as_view(url='/api/v1/', permanent=False)),
    path('admin/', admin.site.urls),
    path("api/v1/", include([
        path('auth/', include('accounts.urls')),
        path('profiles/', include('profiles.urls')),
        path('agents/', include('agents.urls')),
        path('buyers/', include('buyers.urls')),
        path('chat/', include('chat.urls')),
        path('notifications/', include('notifications.urls')),
        path('admin-portal/', include('admin_portal.urls')),
    
    # Swagger & ReDoc Documentation
        path('', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
        path('api/api.json', schema_view.without_ui(cache_timeout=0), name='schema-swagger-ui'),
        path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
    ]))

]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

