from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views, views_data_management

router = DefaultRouter()


urlpatterns = [
    # Dashboard
    path('dashboard/', views.DashboardView.as_view(), name='dashboard'),
    
    # Operations
    path('operations/', views.OperationsView.as_view(), name='operations'),
    
    # Load Monitoring
    path('load-monitoring/', views.LoadMonitoringView.as_view(), name='load-monitoring'),
    
    # Energy Monitoring
    path('energy-monitoring/', views.EnergyMonitoringView.as_view(), name='energy-monitoring'),
    
    # Utility endpoints
    path('crane-list/', views.get_crane_list, name='crane-list'),
    path('recent-alarms/', views.get_recent_alarms, name='recent-alarms'),
    path('acknowledge-alarm/<int:alarm_id>/', views.acknowledge_alarm, name='acknowledge-alarm'),
    
    # Data Management
    path('data/export/', views_data_management.data_export, name='data-export'),
    path('data/cleanup/', views_data_management.data_cleanup, name='data-cleanup'),
    path('system/health/', views_data_management.system_health, name='system-health'),
    
    # Include router URLs
    path('', include(router.urls)),
]