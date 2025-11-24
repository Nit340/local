from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/dashboard/$', consumers.DashboardConsumer.as_asgi()),
    re_path(r'ws/operations/$', consumers.OperationsConsumer.as_asgi()),
    re_path(r'ws/load-monitoring/$', consumers.LoadMonitoringConsumer.as_asgi()),
    re_path(r'ws/energy-monitoring/$', consumers.EnergyMonitoringConsumer.as_asgi()),
    re_path(r'ws/alarms/$', consumers.AlarmConsumer.as_asgi()),
]