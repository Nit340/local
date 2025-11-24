import json
import paho.mqtt.client as mqtt
from django.utils import timezone
from datetime import datetime
from django.conf import settings
from decimal import Decimal
from .models import (
    Crane, CraneMotorMeasurement, CraneIOStatus, 
    CraneLoadcellMeasurement, CraneAlarm, MQTTMessageLog,
    CraneGatewayMapping, CraneConfiguration
)

class CraneMQTTClient:
    def __init__(self):
        self.client = mqtt.Client()
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect
        
        self.broker_host = settings.MQTT_BROKER_HOST
        self.broker_port = settings.MQTT_BROKER_PORT
        self.keepalive = settings.MQTT_KEEPALIVE
        
        self.connected = False
        # Store crane capacities to avoid database lookups
        self.crane_capacities = {}

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            print("✅ MQTT Connected successfully")
            self.connected = True
            # Subscribe to all crane topics from database
            self.subscribe_to_crane_topics()
            # Preload crane capacities
            self.preload_crane_capacities()
        else:
            print(f"❌ MQTT Connection failed with code {rc}")
            self.connected = False

    def on_disconnect(self, client, userdata, rc):
        print("🔴 MQTT Disconnected")
        self.connected = False

    def on_message(self, client, userdata, msg):
        try:
            topic = msg.topic
            payload = msg.payload.decode('utf-8')
            
            print(f"📨 Received message on topic: {topic}")
            print(f"Payload: {payload}")
            
            # Process the message based on topic
            self.process_message(topic, payload)
            
        except Exception as e:
            print(f"❌ Error processing MQTT message: {e}")

    def preload_crane_capacities(self):
        """Preload crane capacities from database"""
        try:
            cranes = Crane.objects.filter(is_active=True)
            for crane in cranes:
                # Get capacity from configuration or use default
                try:
                    config = CraneConfiguration.objects.get(crane=crane)
                    self.crane_capacities[crane.id] = float(config.max_load_capacity)
                except CraneConfiguration.DoesNotExist:
                    # Use crane capacity as fallback
                    self.crane_capacities[crane.id] = float(crane.capacity_tonnes * 1000)
            
            print(f"✅ Preloaded capacities for {len(self.crane_capacities)} cranes")
        except Exception as e:
            print(f"❌ Error preloading crane capacities: {e}")

    def get_crane_capacity(self, crane):
        """Get capacity for crane, with caching"""
        if crane.id in self.crane_capacities:
            return self.crane_capacities[crane.id]
        
        # If not in cache, get from database
        try:
            config = CraneConfiguration.objects.get(crane=crane)
            capacity = float(config.max_load_capacity)
            self.crane_capacities[crane.id] = capacity
            return capacity
        except CraneConfiguration.DoesNotExist:
            # Use crane capacity as fallback
            capacity = float(crane.capacity_tonnes * 1000)
            self.crane_capacities[crane.id] = capacity
            return capacity

    def update_crane_capacity(self, crane, new_capacity):
        """Update capacity in cache and database"""
        try:
            capacity_float = float(new_capacity)
            self.crane_capacities[crane.id] = capacity_float
            
            # Update in database
            config, created = CraneConfiguration.objects.get_or_create(
                crane=crane,
                defaults={'max_load_capacity': capacity_float}
            )
            if not created:
                config.max_load_capacity = capacity_float
                config.save()
            
            print(f"✅ Updated capacity for {crane.crane_name}: {capacity_float} kg")
        except Exception as e:
            print(f"❌ Error updating crane capacity: {e}")

    def subscribe_to_crane_topics(self):
        """Subscribe to all active crane topics from database"""
        try:
            active_mappings = CraneGatewayMapping.objects.filter(is_active=True)
            for mapping in active_mappings:
                topic = mapping.mqtt_topic
                self.client.subscribe(topic)
                print(f"🔔 Subscribed to topic: {topic}")
                
        except Exception as e:
            print(f"❌ Error subscribing to topics: {e}")

    def process_message(self, topic, payload):
        """Process MQTT message and store in appropriate table"""
        try:
            payload_data = json.loads(payload)
            
            # Find crane from topic
            crane = self.get_crane_from_topic(topic)
            if not crane:
                print(f"❌ No crane found for topic: {topic}")
                return

            # Extract timestamp from payload
            timestamp = self.extract_timestamp(payload_data)
            
            # Process based on message content
            if self.is_motor_data(payload_data):
                self.process_motor_data(crane, payload_data, timestamp)
            if self.is_io_status(payload_data):
                self.process_io_status(crane, payload_data, timestamp)
            if self.is_loadcell_data(payload_data):
                self.process_loadcell_data(crane, payload_data, timestamp)
            if self.is_alarm_data(payload_data):
                self.process_alarm_data(crane, payload_data, timestamp)
                
        except json.JSONDecodeError:
            print(f"❌ Invalid JSON payload: {payload}")
        except Exception as e:
            print(f"❌ Error processing message: {e}")

    def get_crane_from_topic(self, topic):
        """Get crane object from MQTT topic"""
        try:
            mapping = CraneGatewayMapping.objects.filter(mqtt_topic=topic).first()
            return mapping.crane if mapping else None
        except Exception as e:
            print(f"❌ Error getting crane from topic: {e}")
            return None

    def extract_timestamp(self, payload_data):
        """Extract timestamp from payload"""
        try:
            if isinstance(payload_data, dict):
                for key, value in payload_data.items():
                    if isinstance(value, list) and len(value) >= 3:
                        unix_timestamp = value[2]
                        return datetime.fromtimestamp(unix_timestamp, tz=timezone.utc)
            
            # Fallback to current time
            return timezone.now()
        except:
            return timezone.now()

    def is_motor_data(self, payload_data):
        """Check if payload contains motor data"""
        motor_keys = ['hoist_voltage', 'hoist_current', 'hoist_power', 'hoist_frequency',
                     'ct_voltage', 'ct_current', 'ct_power', 'ct_frequency',
                     'lt_voltage', 'lt_current', 'lt_power', 'lt_frequency']
        return any(key.lower() in (k.lower() for k in payload_data.keys()) for key in motor_keys)

    def is_io_status(self, payload_data):
        """Check if payload contains IO status data"""
        io_keys = ['start', 'stop', 'hoist_up', 'hoist_down', 'ct_left', 'ct_right', 
                  'lt_forward', 'lt_reverse']
        return any(key.lower() in (k.lower() for k in payload_data.keys()) for key in io_keys)

    def is_loadcell_data(self, payload_data):
        """Check if payload contains loadcell data"""
        return 'load' in payload_data

    def is_alarm_data(self, payload_data):
        """Check if payload contains alarm data"""
        alarm_keys = ['alarm_one', 'alarm_two', 'alarm_three']
        return any(key.lower() in (k.lower() for k in payload_data.keys()) for key in alarm_keys)

    def process_motor_data(self, crane, payload_data, timestamp):
        """Process and store motor measurement data"""
        try:
            motor_data = {
                'crane': crane,
                'timestamp': timestamp,
            }
            
            # Extract motor values from payload
            for key, value in payload_data.items():
                if isinstance(value, list) and len(value) >= 2:
                    actual_value = value[1]  # Second element is the value
                    
                    key_lower = key.lower()
                    if 'hoist_voltage' in key_lower:
                        motor_data['hoist_voltage'] = float(actual_value)
                    elif 'hoist_current' in key_lower:
                        motor_data['hoist_current'] = float(actual_value)
                    elif 'hoist_power' in key_lower:
                        motor_data['hoist_power'] = float(actual_value)
                    elif 'hoist_frequency' in key_lower:
                        motor_data['hoist_frequency'] = float(actual_value)
                    elif 'ct_voltage' in key_lower:
                        motor_data['ct_voltage'] = float(actual_value)
                    elif 'ct_current' in key_lower:
                        motor_data['ct_current'] = float(actual_value)
                    elif 'ct_power' in key_lower:
                        motor_data['ct_power'] = float(actual_value)
                    elif 'ct_frequency' in key_lower:
                        motor_data['ct_frequency'] = float(actual_value)
                    elif 'lt_voltage' in key_lower:
                        motor_data['lt_voltage'] = float(actual_value)
                    elif 'lt_current' in key_lower:
                        motor_data['lt_current'] = float(actual_value)
                    elif 'lt_power' in key_lower:
                        motor_data['lt_power'] = float(actual_value)
                    elif 'lt_frequency' in key_lower:
                        motor_data['lt_frequency'] = float(actual_value)
            
            # Create motor measurement record
            CraneMotorMeasurement.objects.create(**motor_data)
            print(f"✅ Motor data saved for crane: {crane.crane_name}")
            
        except Exception as e:
            print(f"❌ Error processing motor data: {e}")

    def process_io_status(self, crane, payload_data, timestamp):
        """Process and store IO status data"""
        try:
            io_data = {
                'crane': crane,
                'timestamp': timestamp,
            }
            
            # Extract IO values from payload
            for key, value in payload_data.items():
                if isinstance(value, list) and len(value) >= 2:
                    actual_value = value[1]  # Second element is the value
                    
                    key_lower = key.lower()
                    if 'start' in key_lower:
                        io_data['start'] = bool(actual_value)
                    elif 'stop' in key_lower:
                        io_data['stop'] = bool(actual_value)
                    elif 'hoist_up' in key_lower:
                        io_data['hoist_up'] = bool(actual_value)
                    elif 'hoist_down' in key_lower:
                        io_data['hoist_down'] = bool(actual_value)
                    elif 'ct_left' in key_lower:
                        io_data['ct_left'] = bool(actual_value)
                    elif 'ct_right' in key_lower:
                        io_data['ct_right'] = bool(actual_value)
                    elif 'lt_forward' in key_lower:
                        io_data['lt_forward'] = bool(actual_value)
                    elif 'lt_reverse' in key_lower:
                        io_data['lt_reverse'] = bool(actual_value)
            
            # Create IO status record
            CraneIOStatus.objects.create(**io_data)
            print(f"✅ IO status saved for crane: {crane.crane_name}")
            
        except Exception as e:
            print(f"❌ Error processing IO status: {e}")

    def process_loadcell_data(self, crane, payload_data, timestamp):
        """Process and store loadcell data"""
        try:
            loadcell_data = {
                'crane': crane,
                'timestamp': timestamp,
            }
            
            # Extract load values from payload
            for key, value in payload_data.items():
                if isinstance(value, list) and len(value) >= 2:
                    actual_value = value[1]  # Second element is the value
                    
                    key_lower = key.lower()
                    if 'load' in key_lower:
                        loadcell_data['load'] = float(actual_value)
                    elif 'capacity' in key_lower:
                        # Update capacity if provided in payload
                        self.update_crane_capacity(crane, actual_value)
                        loadcell_data['capacity'] = float(actual_value)
            
            # If capacity not provided in payload, use stored capacity
            if 'capacity' not in loadcell_data:
                loadcell_data['capacity'] = self.get_crane_capacity(crane)
            
            # Create loadcell measurement record
            CraneLoadcellMeasurement.objects.create(**loadcell_data)
            print(f"✅ Loadcell data saved for crane: {crane.crane_name}")
            
        except Exception as e:
            print(f"❌ Error processing loadcell data: {e}")

    def process_alarm_data(self, crane, payload_data, timestamp):
        """Process and store alarm data"""
        try:
            alarm_data = {
                'crane': crane,
                'timestamp': timestamp,
                'alarm_message': '',
            }
            
            # Extract alarm values from payload
            for key, value in payload_data.items():
                if isinstance(value, list) and len(value) >= 2:
                    actual_value = value[1]  # Second element is the value
                    
                    key_lower = key.lower()
                    if 'alarm_one' in key_lower:
                        alarm_data['alarm_one'] = bool(actual_value)
                    elif 'alarm_two' in key_lower:
                        alarm_data['alarm_two'] = bool(actual_value)
                    elif 'alarm_three' in key_lower:
                        alarm_data['alarm_three'] = bool(actual_value)
            
            # Set alarm message based on active alarms
            active_alarms = []
            if alarm_data.get('alarm_one'):
                active_alarms.append('Alarm One')
            if alarm_data.get('alarm_two'):
                active_alarms.append('Alarm Two')
            if alarm_data.get('alarm_three'):
                active_alarms.append('Alarm Three')
                
            if active_alarms:
                alarm_data['alarm_message'] = f"Active alarms: {', '.join(active_alarms)}"
                alarm_data['alarm_severity'] = 'high'
            
            # Create alarm record
            CraneAlarm.objects.create(**alarm_data)
            print(f"✅ Alarm data saved for crane: {crane.crane_name}")
            
        except Exception as e:
            print(f"❌ Error processing alarm data: {e}")

    def connect(self):
        """Connect to MQTT broker"""
        try:
            print(f"🔗 Connecting to MQTT broker: {self.broker_host}:{self.broker_port}")
            self.client.connect(self.broker_host, self.broker_port, self.keepalive)
            self.client.loop_start()
        except Exception as e:
            print(f"❌ MQTT connection error: {e}")

    def disconnect(self):
        """Disconnect from MQTT broker"""
        try:
            self.client.loop_stop()
            self.client.disconnect()
            print("🔴 MQTT disconnected")
        except Exception as e:
            print(f"❌ MQTT disconnection error: {e}")

    def add_crane_topic(self, topic, crane_name):
        """Dynamically add a new crane topic subscription"""
        try:
            self.client.subscribe(topic)
            print(f"🔔 Added subscription to topic: {topic} for crane: {crane_name}")
        except Exception as e:
            print(f"❌ Error adding crane topic: {e}")

# Global MQTT client instance
mqtt_client = CraneMQTTClient()