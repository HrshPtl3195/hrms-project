from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Include URLs from each app
    path('', include('core.urls')),  # Common pages
    path('hr-admin/', include('hr_admin.urls')),
    path('office-admin/', include('office_admin.urls')),
    path('employee/', include('employee.urls')),
    path('hybrid/', include('hybrid.urls')),
]
