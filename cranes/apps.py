from django.apps import AppConfig

class CranesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'cranes'

    def ready(self):
        # Don't start MQTT during migrations
        import sys
        if 'migrate' in sys.argv or 'makemigrations' in sys.argv:
            return
            
        # Start MQTT client only during normal operation
        try:
            from .mqtt_client import mqtt_client
            mqtt_client.connect()
        except Exception as e:
            print(f"❌ Error starting MQTT client: {e}")