import json
import paho.mqtt.client as mqtt
from django.utils import timezone
from datetime import datetime
from django.conf import settings
from decimal import Decimal
from .models import (
    Crane, CraneMotorMeasurement, CraneIOStatus, 
    CraneLoadcellMeasurement, CraneAlarm, MQTTMessageLog,
    CraneGatewayMapping, CraneConfiguration, DataPointMapping
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
        self.field_mappings = {}

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
            
            print(f"🔍 START PROCESSING MESSAGE")
            print(f"📨 Topic: {topic}")
            print(f"📦 Full Payload: {json.dumps(payload_data, indent=2)}")
            
            # Find crane from topic
            crane = self.get_crane_from_topic(topic)
            if not crane:
                print(f"❌ No crane found for topic: {topic}")
                return

            # Extract timestamp from payload
            timestamp = self.extract_timestamp(payload_data)
            print(f"⏰ Using timestamp: {timestamp}")
            
            # FIRST check for array format (from your MQTT sender)
            if self.is_array_format(payload_data):
                print(f"📊 Detected array format - processing multiple fields")
                self.process_array_format_data(crane, payload_data, timestamp)
            # THEN check for embedded JSON format
            elif self.has_embedded_json_format(payload_data):
                print(f"🔄 Detected embedded JSON format")
                self.process_embedded_json_data(crane, payload_data, timestamp)
            # THEN check for single field with direct value
            elif self.is_single_field_format(payload_data):
                print(f"🔧 Detected single field format")
                self.process_single_field_data(crane, payload_data, timestamp)
            else:
                print(f"❓ Unknown payload format - no data processors matched")
                
            print(f"✅ FINISHED PROCESSING MESSAGE\n")
            
        except json.JSONDecodeError:
            print(f"❌ Invalid JSON payload: {payload}")
        except Exception as e:
            print(f"❌ Error processing message: {e}")
            import traceback
            traceback.print_exc()

    def is_array_format(self, payload_data):
        """Check if payload contains array format [name, value, timestamp]"""
        if not isinstance(payload_data, dict):
            return False
            
        for key, value in payload_data.items():
            if isinstance(value, list) and len(value) >= 3:
                return True
        return False

    def has_embedded_json_format(self, payload_data):
        """Check if payload contains fields with embedded JSON strings"""
        for key, value in payload_data.items():
            if isinstance(value, str) and value.startswith('{') and 'timestamp' in value:
                return True
        return False

    def is_single_field_format(self, payload_data):
        """Check if payload contains single field with direct value"""
        return len(payload_data) == 1 and 'device_token' not in payload_data

    def process_array_format_data(self, crane, payload_data, timestamp):
        """Process data in array format [name, value, timestamp]"""
        try:
            print(f"📊 PROCESSING ARRAY FORMAT DATA for crane: {crane.crane_name}")
            
            # Initialize data containers
            motor_data = {}
            io_data = {}
            loadcell_data = {}
            alarm_data = {}
            
            # Process each field
            for field_name, field_value in payload_data.items():
                if isinstance(field_value, list) and len(field_value) >= 3:
                    actual_name = field_value[0] if len(field_value) > 0 else field_name
                    actual_value = field_value[1] if len(field_value) > 1 else 0
                    field_timestamp = field_value[2] if len(field_value) > 2 else timestamp.timestamp()
                    
                    print(f"📊 Processing field: {actual_name} = {actual_value}")
                    
                    # Route to appropriate processor
                    self.route_array_field_data(crane, actual_name, actual_value, 
                                              datetime.fromtimestamp(field_timestamp, tz=timezone.utc),
                                              motor_data, io_data, loadcell_data, alarm_data)
            
            # Save all collected data
            self.save_collected_data(crane, motor_data, io_data, loadcell_data, alarm_data)
            
            # Log the message
            self.log_mqtt_message(crane, payload_data, 'array_format_data', timestamp)
            
        except Exception as e:
            print(f"❌ Error processing array format data: {e}")
            import traceback
            traceback.print_exc()

    def route_array_field_data(self, crane, field_name, field_value, timestamp, 
                              motor_data, io_data, loadcell_data, alarm_data):
        """Route array field data to appropriate container"""
        field_lower = field_name.lower()
        
        try:
            # Motor voltage fields
            if any(voltage_field in field_lower for voltage_field in ['hoist_voltage', 'ct_voltage', 'lt_voltage']):
                if 'timestamp' not in motor_data:
                    motor_data['timestamp'] = timestamp
                    motor_data['crane'] = crane
                motor_data[field_name] = float(field_value)
            
            # Motor current fields  
            elif any(current_field in field_lower for current_field in ['hoist_current', 'ct_current', 'lt_current']):
                if 'timestamp' not in motor_data:
                    motor_data['timestamp'] = timestamp
                    motor_data['crane'] = crane
                motor_data[field_name] = float(field_value)
            
            # Motor power fields
            elif any(power_field in field_lower for power_field in ['hoist_power', 'ct_power', 'lt_power']):
                if 'timestamp' not in motor_data:
                    motor_data['timestamp'] = timestamp
                    motor_data['crane'] = crane
                motor_data[field_name] = float(field_value)
            
            # Motor frequency fields
            elif any(freq_field in field_lower for freq_field in ['hoist_frequency', 'ct_frequency', 'lt_frequency']):
                if 'timestamp' not in motor_data:
                    motor_data['timestamp'] = timestamp
                    motor_data['crane'] = crane
                motor_data[field_name] = float(field_value)
            
            # IO Status fields
            elif any(io_field in field_lower for io_field in [
                'hoist_up', 'hoist_down', 'ct_left', 'ct_right', 
                'lt_forward', 'lt_reverse', 'start', 'stop'
            ]):
                if 'timestamp' not in io_data:
                    io_data['timestamp'] = timestamp
                    io_data['crane'] = crane
                io_data[field_name] = bool(int(field_value))
            
            # Alarm fields
            elif any(alarm_field in field_lower for alarm_field in ['alarm_one', 'alarm_two', 'alarm_three']):
                if 'timestamp' not in alarm_data:
                    alarm_data['timestamp'] = timestamp
                    alarm_data['crane'] = crane
                    alarm_data['alarm_message'] = ''
                alarm_data[field_name] = bool(int(field_value))
            
            # Load field
            elif 'load' in field_lower:
                if 'timestamp' not in loadcell_data:
                    loadcell_data['timestamp'] = timestamp
                    loadcell_data['crane'] = crane
                loadcell_data['load'] = float(field_value)
                loadcell_data['capacity'] = self.get_crane_capacity(crane)
            
            # Capacity field
            elif 'capacity' in field_lower:
                self.update_crane_capacity(crane, field_value)
                print(f"📊 Capacity updated: {field_value} kg")
            
            else:
                print(f"⚠️ Unknown field type: {field_name}")
                
        except Exception as e:
            print(f"❌ Error routing array field data for {field_name}: {e}")

    def save_collected_data(self, crane, motor_data, io_data, loadcell_data, alarm_data):
        """Save all collected data to database"""
        try:
            # Save motor data
            if len(motor_data) > 2:  # More than just crane and timestamp
                # Map field names to database columns
                mapped_motor_data = {
                    'crane': motor_data['crane'],
                    'timestamp': motor_data['timestamp'],
                }
                
                for field_name, value in motor_data.items():
                    if field_name not in ['crane', 'timestamp']:
                        field_lower = field_name.lower()
                        if 'hoist_voltage' in field_lower:
                            mapped_motor_data['hoist_voltage'] = value
                        elif 'hoist_current' in field_lower:
                            mapped_motor_data['hoist_current'] = value
                        elif 'hoist_power' in field_lower:
                            mapped_motor_data['hoist_power'] = value
                        elif 'hoist_frequency' in field_lower:
                            mapped_motor_data['hoist_frequency'] = value
                        elif 'ct_voltage' in field_lower:
                            mapped_motor_data['ct_voltage'] = value
                        elif 'ct_current' in field_lower:
                            mapped_motor_data['ct_current'] = value
                        elif 'ct_power' in field_lower:
                            mapped_motor_data['ct_power'] = value
                        elif 'ct_frequency' in field_lower:
                            mapped_motor_data['ct_frequency'] = value
                        elif 'lt_voltage' in field_lower:
                            mapped_motor_data['lt_voltage'] = value
                        elif 'lt_current' in field_lower:
                            mapped_motor_data['lt_current'] = value
                        elif 'lt_power' in field_lower:
                            mapped_motor_data['lt_power'] = value
                        elif 'lt_frequency' in field_lower:
                            mapped_motor_data['lt_frequency'] = value
                
                CraneMotorMeasurement.objects.create(**mapped_motor_data)
                print(f"✅ Motor data saved for crane: {crane.crane_name}")
            
            # Save IO data
            if len(io_data) > 2:
                CraneIOStatus.objects.create(**io_data)
                print(f"✅ IO status saved for crane: {crane.crane_name}")
            
            # Save loadcell data
            if 'load' in loadcell_data:
                CraneLoadcellMeasurement.objects.create(**loadcell_data)
                print(f"⚖️ Loadcell data saved: {loadcell_data['load']} kg")
            
            # Save alarm data
            if len(alarm_data) > 2:
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
                
                CraneAlarm.objects.create(**alarm_data)
                print(f"🚨 Alarm data saved for crane: {crane.crane_name}")
                
        except Exception as e:
            print(f"❌ Error saving collected data: {e}")

    def process_embedded_json_data(self, crane, payload_data, timestamp):
        """Process embedded JSON format data"""
        try:
            print(f"🔄 PROCESSING EMBEDDED JSON DATA for crane: {crane.crane_name}")
            
            # Process each field that contains embedded JSON
            for field_name, field_value in payload_data.items():
                if isinstance(field_value, str) and field_value.startswith('{'):
                    print(f"🔄 Parsing embedded JSON field: {field_name} = {field_value}")
                    
                    try:
                        # Clean and parse the embedded JSON
                        cleaned_str = self.clean_embedded_json(field_value)
                        embedded_data = json.loads(cleaned_str)
                        print(f"✅ Parsed embedded data: {embedded_data}")
                        
                        # Extract the actual value and timestamp
                        actual_value = embedded_data.get(field_name, 0)
                        embedded_timestamp = embedded_data.get('timestamp', timestamp.timestamp())
                        actual_timestamp = datetime.fromtimestamp(embedded_timestamp, tz=timezone.utc)
                        
                        print(f"📊 Extracted - Field: {field_name}, Value: {actual_value}, TS: {actual_timestamp}")
                        
                        # Process the single field
                        self.process_single_field(crane, field_name, actual_value, actual_timestamp)
                        
                    except Exception as e:
                        print(f"❌ Error parsing embedded JSON in {field_name}: {e}")
            
            # Log the message
            self.log_mqtt_message(crane, payload_data, 'embedded_json_data', timestamp)
            
        except Exception as e:
            print(f"❌ Error processing embedded JSON data: {e}")

    def process_single_field_data(self, crane, payload_data, timestamp):
        """Process single field with direct value"""
        try:
            print(f"🔧 PROCESSING SINGLE FIELD DATA for crane: {crane.crane_name}")
            
            for field_name, field_value in payload_data.items():
                if field_name not in ['device_token', 'topic', 'timestamp']:
                    print(f"📊 Processing single field: {field_name} = {field_value}")
                    self.process_single_field(crane, field_name, field_value, timestamp)
            
            # Log the message
            self.log_mqtt_message(crane, payload_data, 'single_field_data', timestamp)
            
        except Exception as e:
            print(f"❌ Error processing single field data: {e}")

    def process_single_field(self, crane, field_name, field_value, timestamp):
        """Process a single field"""
        field_lower = field_name.lower()
        
        try:
            # Motor data fields
            if any(motor_field in field_lower for motor_field in [
                'hoist_voltage', 'hoist_current', 'hoist_power', 'hoist_frequency',
                'ct_voltage', 'ct_current', 'ct_power', 'ct_frequency', 
                'lt_voltage', 'lt_current', 'lt_power', 'lt_frequency'
            ]):
                motor_data = {
                    'crane': crane,
                    'timestamp': timestamp,
                    field_name: float(field_value)
                }
                CraneMotorMeasurement.objects.create(**motor_data)
                print(f"✅ Motor field saved: {field_name} = {field_value}")
            
            # IO Status fields
            elif any(io_field in field_lower for io_field in [
                'hoist_up', 'hoist_down', 'ct_left', 'ct_right', 
                'lt_forward', 'lt_reverse', 'start', 'stop'
            ]):
                io_data = {
                    'crane': crane,
                    'timestamp': timestamp,
                    field_name: bool(int(field_value))
                }
                CraneIOStatus.objects.create(**io_data)
                print(f"✅ IO field saved: {field_name} = {field_value}")
            
            # Load field
            elif 'load' in field_lower:
                loadcell_data = {
                    'crane': crane,
                    'timestamp': timestamp,
                    'load': float(field_value),
                    'capacity': self.get_crane_capacity(crane)
                }
                CraneLoadcellMeasurement.objects.create(**loadcell_data)
                print(f"⚖️ Load field saved: {field_value} kg")
            
            # Capacity field
            elif 'capacity' in field_lower:
                self.update_crane_capacity(crane, field_value)
                print(f"📊 Capacity updated: {field_value} kg")
            
            # Alarm fields
            elif any(alarm_field in field_lower for alarm_field in ['alarm_one', 'alarm_two', 'alarm_three']):
                if int(field_value) == 1:  # Only save active alarms
                    alarm_data = {
                        'crane': crane,
                        'timestamp': timestamp,
                        field_name: True,
                        'alarm_message': f'{field_name} activated',
                        'alarm_severity': 'high'
                    }
                    CraneAlarm.objects.create(**alarm_data)
                    print(f"🚨 Alarm field saved: {field_name} = {field_value}")
            
            else:
                print(f"⚠️ Unknown field type: {field_name}")
                
        except Exception as e:
            print(f"❌ Error processing single field {field_name}: {e}")

    def clean_embedded_json(self, json_string):
        """Clean embedded JSON string to make it valid JSON"""
        try:
            # Remove outer braces temporarily
            inner_content = json_string.strip('{}')
            
            # Split by commas to handle key-value pairs
            pairs = inner_content.split(',')
            cleaned_pairs = []
            
            for pair in pairs:
                if ':' in pair:
                    key, value = pair.split(':', 1)
                    # Clean key and value
                    key = key.strip()
                    value = value.strip()
                    
                    # Ensure key is quoted
                    if not key.startswith('"'):
                        key = f'"{key}"'
                    
                    # Handle value types
                    if value.replace('.', '').replace('-', '').isdigit():
                        # It's a number, leave as is
                        cleaned_pairs.append(f'{key}:{value}')
                    else:
                        # It's probably a string, quote it
                        if not value.startswith('"'):
                            value = f'"{value}"'
                        cleaned_pairs.append(f'{key}:{value}')
            
            # Reconstruct JSON
            return '{' + ','.join(cleaned_pairs) + '}'
        except Exception as e:
            print(f"❌ Error cleaning JSON: {e}")
            return '{}'

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
            # First try to get timestamp from payload
            if 'timestamp' in payload_data:
                unix_timestamp = payload_data['timestamp']
                return datetime.fromtimestamp(unix_timestamp, tz=timezone.utc)
            
            # Fallback to current time
            return timezone.now()
        except:
            return timezone.now()

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

    def log_mqtt_message(self, crane, payload_data, message_type, timestamp):
        """Log the MQTT message for debugging"""
        try:
            # Find gateway from crane mapping
            gateway = None
            mapping = CraneGatewayMapping.objects.filter(crane=crane, is_active=True).first()
            if mapping:
                gateway = mapping.gateway
            
            MQTTMessageLog.objects.create(
                crane=crane,
                gateway=gateway,
                topic="processed_topic",
                payload=payload_data,
                message_type=message_type,
                timestamp=timestamp
            )
            print(f"📝 Message logged to database - Type: {message_type}")
        except Exception as e:
            print(f"❌ Error logging message: {e}")

# Global MQTT client instance
mqtt_client = CraneMQTTClient()