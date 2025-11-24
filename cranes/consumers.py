import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
from decimal import Decimal
from datetime import timedelta
from .models import (
    Crane, CraneMotorMeasurement, CraneIOStatus, 
    CraneLoadcellMeasurement, CraneAlarm
)

class DashboardConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.channel_layer.group_add("dashboard", self.channel_name)
        await self.accept()
        print("✅ Dashboard WebSocket connected")
        
        # Send initial data
        await self.send_initial_data()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard("dashboard", self.channel_name)
        print("🔴 Dashboard WebSocket disconnected")

    async def receive(self, text_data):
        """Handle messages from client"""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'subscribe':
                await self.send_initial_data()
            elif message_type == 'ping':
                await self.send(json.dumps({'type': 'pong'}))
                
        except json.JSONDecodeError:
            pass

    async def send_initial_data(self):
        """Send initial dashboard data"""
        data = await self.get_dashboard_data()
        await self.send(json.dumps({
            'type': 'initial_data',
            'data': data
        }, default=self.decimal_default))

    async def crane_data_update(self, event):
        """Send real-time crane data updates"""
        data = event['data']
        await self.send(json.dumps({
            'type': 'crane_update',
            'data': data
        }, default=self.decimal_default))

    async def alarm_update(self, event):
        """Send alarm updates"""
        await self.send(json.dumps({
            'type': 'alarm_update',
            'data': event['data']
        }, default=self.decimal_default))

    def decimal_default(self, obj):
        """Convert Decimal objects to float for JSON serialization"""
        if isinstance(obj, Decimal):
            return float(obj)
        raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")

    @database_sync_to_async
    def get_dashboard_data(self):
        """Get current dashboard data in correct format for frontend"""
        try:
            cranes = Crane.objects.filter(is_active=True)
            
            total_power = 0
            total_current = 0
            active_cranes = 0
            idle_cranes = 0
            
            crane_details = []
            
            for crane in cranes:
                # Get latest motor data
                latest_motor = CraneMotorMeasurement.objects.filter(
                    crane=crane
                ).order_by('-timestamp').first()
                
                # Get latest load data
                latest_load = CraneLoadcellMeasurement.objects.filter(
                    crane=crane
                ).order_by('-timestamp').first()
                
                # Get latest IO status for current operation
                latest_io = CraneIOStatus.objects.filter(
                    crane=crane
                ).order_by('-timestamp').first()
                
                # Determine crane status based on power
                if latest_motor and latest_motor.total_power and latest_motor.total_power > 1:
                    crane_status = 'working'
                    active_cranes += 1
                    total_power += float(latest_motor.total_power) if latest_motor.total_power else 0
                    total_current += float(latest_motor.total_current) if latest_motor.total_current else 0
                else:
                    crane_status = 'idle'
                    idle_cranes += 1
                
                # Get current operation from IO status
                current_operation = self.get_current_operation(latest_io) if latest_io else 'Idle'
                
                # Format crane data for frontend
                crane_details.append({
                    'id': crane.id,
                    'crane_name': crane.crane_name,
                    'status': crane_status.title(),
                    'current_load': float(latest_load.load) if latest_load else 0,
                    'capacity': float(latest_load.capacity) if latest_load else float(crane.capacity_tonnes * 1000),
                    'load_percentage': float(latest_load.load_percentage) if latest_load else 0,
                    'load_status': latest_load.status if latest_load else 'normal',
                    'device_ids': crane.device_ids if crane.device_ids else [],
                    'current_operation': current_operation,
                    'power': float(latest_motor.total_power) if latest_motor else 0,
                    'last_updated': latest_motor.timestamp.isoformat() if latest_motor else crane.updated_at.isoformat()
                })
            
            total_cranes = cranes.count()
            
            # Calculate OEE metrics (synchronous call)
            oee_metrics = self.calculate_oee_metrics()
            
            return {
                'quick_stats': {
                    'total_power': round(total_power, 1),
                    'total_current': round(total_current, 1),
                    'active_cranes': active_cranes,
                    'idle_cranes': idle_cranes,
                    'total_cranes': total_cranes,
                    'utilization': round((active_cranes / total_cranes) * 100, 1) if total_cranes > 0 else 0,
                },
                'oee_metrics': oee_metrics,
                'crane_details': crane_details
            }
            
        except Exception as e:
            print(f"Error in get_dashboard_data: {e}")
            return {'error': str(e)}

    def get_current_operation(self, io_status):
        """Get current operation from IO status"""
        if not io_status:
            return 'Idle'
        
        if io_status.hoist_up:
            return 'Hoist Up'
        elif io_status.hoist_down:
            return 'Hoist Down'
        elif io_status.ct_left:
            return 'CT Left'
        elif io_status.ct_right:
            return 'CT Right'
        elif io_status.lt_forward:
            return 'LT Forward'
        elif io_status.lt_reverse:
            return 'LT Reverse'
        elif io_status.start:
            return 'Starting'
        elif io_status.stop:
            return 'Stopping'
        else:
            return 'Idle'

    def calculate_oee_metrics(self):
        """Calculate OEE metrics - synchronous version"""
        return {
            'oee': 78.5,
            'availability': 85.0,
            'performance': 92.0,
            'quality': 98.5,
            'oee_change': 2.5,
            'availability_change': 1.2,
            'performance_change': -0.8
        }

class OperationsConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.channel_layer.group_add("operations", self.channel_name)
        await self.accept()
        print("✅ Operations WebSocket connected")
        
        # Send initial data immediately
        await self.send_initial_data()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard("operations", self.channel_name)
        print("🔴 Operations WebSocket disconnected")

    async def receive(self, text_data):
        """Handle messages from client"""
        try:
            data = json.loads(text_data)
            if data.get('type') == 'subscribe':
                await self.send_initial_data()
        except json.JSONDecodeError:
            pass

    async def send_initial_data(self):
        """Send initial operations data"""
        data = await self.get_operations_data()
        await self.send(json.dumps({
            'type': 'initial_data',
            'data': data
        }, default=self.decimal_default))

    async def operation_update(self, event):
        """Send new operation updates"""
        await self.send(json.dumps({
            'type': 'operation_update',
            'data': event['data']
        }, default=self.decimal_default))

    def decimal_default(self, obj):
        """Convert Decimal objects to float for JSON serialization"""
        if isinstance(obj, Decimal):
            return float(obj)
        raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")

    @database_sync_to_async
    def get_operations_data(self):
        """Get current operations data"""
        try:
            # Get recent IO operations from last 24 hours
            recent_operations = CraneIOStatus.objects.filter(
                timestamp__gte=timezone.now() - timedelta(hours=24)
            ).order_by('-timestamp')[:50]
            
            operations_list = []
            for op in recent_operations:
                operation_type = self.get_operation_type(op)
                if operation_type:
                    # Get load at the time of operation
                    load_at_op = CraneLoadcellMeasurement.objects.filter(
                        crane=op.crane,
                        timestamp__range=(
                            op.timestamp - timedelta(seconds=10),
                            op.timestamp + timedelta(seconds=10)
                        )
                    ).first()
                    
                    operations_list.append({
                        'timestamp': op.timestamp.isoformat(),
                        'crane_name': op.crane.crane_name,
                        'operation': operation_type,
                        'duration': 'N/A',
                        'load_kg': float(load_at_op.load) if load_at_op else 0
                    })
            
            # Get operation counts for summary
            operation_counts = {
                'hoist_up': CraneIOStatus.objects.filter(
                    hoist_up=True,
                    timestamp__gte=timezone.now() - timedelta(hours=24)
                ).count(),
                'hoist_down': CraneIOStatus.objects.filter(
                    hoist_down=True,
                    timestamp__gte=timezone.now() - timedelta(hours=24)
                ).count(),
                'ct_left': CraneIOStatus.objects.filter(
                    ct_left=True,
                    timestamp__gte=timezone.now() - timedelta(hours=24)
                ).count(),
                'ct_right': CraneIOStatus.objects.filter(
                    ct_right=True,
                    timestamp__gte=timezone.now() - timedelta(hours=24)
                ).count(),
                'lt_forward': CraneIOStatus.objects.filter(
                    lt_forward=True,
                    timestamp__gte=timezone.now() - timedelta(hours=24)
                ).count(),
                'lt_reverse': CraneIOStatus.objects.filter(
                    lt_reverse=True,
                    timestamp__gte=timezone.now() - timedelta(hours=24)
                ).count(),
                'stop': CraneIOStatus.objects.filter(
                    stop=True,
                    timestamp__gte=timezone.now() - timedelta(hours=24)
                ).count()
            }
            
            return {
                'recent_operations': operations_list,
                'operation_counts': operation_counts,
                'total_operations': len(operations_list)
            }
            
        except Exception as e:
            print(f"Error in get_operations_data: {e}")
            return {
                'recent_operations': [],
                'operation_counts': {},
                'total_operations': 0,
                'error': str(e)
            }
    
    def get_operation_type(self, io_status):
        """Get operation type from IO status"""
        if io_status.hoist_up:
            return 'Hoist Up'
        elif io_status.hoist_down:
            return 'Hoist Down'
        elif io_status.ct_left:
            return 'CT Left'
        elif io_status.ct_right:
            return 'CT Right'
        elif io_status.lt_forward:
            return 'LT Forward'
        elif io_status.lt_reverse:
            return 'LT Reverse'
        elif io_status.stop:
            return 'Stop'
        elif io_status.start:
            return 'Start'
        return None

class LoadMonitoringConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.channel_layer.group_add("load_monitoring", self.channel_name)
        await self.accept()
        print("✅ Load Monitoring WebSocket connected")
        
        # Send initial data immediately
        await self.send_initial_data()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard("load_monitoring", self.channel_name)
        print("🔴 Load Monitoring WebSocket disconnected")

    async def receive(self, text_data):
        """Handle messages from client"""
        try:
            data = json.loads(text_data)
            if data.get('type') == 'subscribe':
                await self.send_initial_data()
        except json.JSONDecodeError:
            pass

    async def load_update(self, event):
        """Send load data updates"""
        await self.send(json.dumps({
            'type': 'load_update',
            'data': event['data']
        }, default=self.decimal_default))

    async def send_initial_data(self):
        """Send initial load data"""
        data = await self.get_load_data()
        await self.send(json.dumps({
            'type': 'initial_data',
            'data': data
        }, default=self.decimal_default))

    def decimal_default(self, obj):
        """Convert Decimal objects to float for JSON serialization"""
        if isinstance(obj, Decimal):
            return float(obj)
        raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")

    @database_sync_to_async
    def get_load_data(self):
        """Get current load data"""
        try:
            cranes = Crane.objects.filter(is_active=True)
            current_loads = []
            load_history = []
            
            # Get current loads for all cranes
            for crane in cranes:
                latest_load = CraneLoadcellMeasurement.objects.filter(
                    crane=crane
                ).order_by('-timestamp').first()
                
                if latest_load:
                    current_loads.append({
                        'crane_name': crane.crane_name,
                        'load': float(latest_load.load),
                        'capacity': float(latest_load.capacity),
                        'percentage': float(latest_load.load_percentage),
                        'status': latest_load.status,
                        'timestamp': latest_load.timestamp.isoformat()
                    })
            
            # Get load history (last 50 records)
            recent_loads = CraneLoadcellMeasurement.objects.filter(
                timestamp__gte=timezone.now() - timedelta(hours=24)
            ).order_by('-timestamp')[:50]
            
            for load in recent_loads:
                # Find corresponding operation
                operation = CraneIOStatus.objects.filter(
                    crane=load.crane,
                    timestamp__range=(
                        load.timestamp - timedelta(seconds=5),
                        load.timestamp + timedelta(seconds=5)
                    )
                ).first()
                
                load_history.append({
                    'timestamp': load.timestamp.isoformat(),
                    'crane_name': load.crane.crane_name,
                    'operation': self.get_operation_type(operation) if operation else 'N/A',
                    'load_kg': float(load.load),
                    'capacity': float(load.capacity),
                    'percentage': float(load.load_percentage),
                    'status': load.status
                })
            
            # Calculate load statistics
            if current_loads:
                total_load = sum(item['load'] for item in current_loads)
                total_capacity = sum(item['capacity'] for item in current_loads)
                avg_capacity = (total_load / total_capacity * 100) if total_capacity > 0 else 0
                max_load = max(item['load'] for item in current_loads)
            else:
                total_load = 0
                avg_capacity = 0
                max_load = 0
            
            return {
                'current_loads': current_loads,
                'load_history': load_history,
                'load_statistics': {
                    'total_load': total_load,
                    'average_capacity': round(avg_capacity, 1),
                    'max_load': max_load,
                    'active_overloads': len([l for l in current_loads if l['status'] == 'overload'])
                }
            }
            
        except Exception as e:
            print(f"Error in get_load_data: {e}")
            return {
                'current_loads': [],
                'load_history': [],
                'load_statistics': {},
                'error': str(e)
            }
    
    def get_operation_type(self, io_status):
        """Get operation type from IO status"""
        if not io_status:
            return 'N/A'
        if io_status.hoist_up:
            return 'Hoist Up'
        elif io_status.hoist_down:
            return 'Hoist Down'
        elif io_status.ct_left:
            return 'CT Left'
        elif io_status.ct_right:
            return 'CT Right'
        elif io_status.lt_forward:
            return 'LT Forward'
        elif io_status.lt_reverse:
            return 'LT Reverse'
        return 'Unknown'

class EnergyMonitoringConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.channel_layer.group_add("energy_monitoring", self.channel_name)
        await self.accept()
        print("✅ Energy Monitoring WebSocket connected")
        
        # Send initial data immediately
        await self.send_initial_data()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard("energy_monitoring", self.channel_name)
        print("🔴 Energy Monitoring WebSocket disconnected")

    async def receive(self, text_data):
        """Handle messages from client"""
        try:
            data = json.loads(text_data)
            if data.get('type') == 'subscribe':
                await self.send_initial_data()
        except json.JSONDecodeError:
            pass

    async def energy_update(self, event):
        """Send energy data updates"""
        await self.send(json.dumps({
            'type': 'energy_update',
            'data': event['data']
        }, default=self.decimal_default))

    async def send_initial_data(self):
        """Send initial energy data"""
        data = await self.get_energy_data()
        await self.send(json.dumps({
            'type': 'initial_data',
            'data': data
        }, default=self.decimal_default))

    def decimal_default(self, obj):
        """Convert Decimal objects to float for JSON serialization"""
        if isinstance(obj, Decimal):
            return float(obj)
        raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")

    @database_sync_to_async
    def get_energy_data(self):
        """Get current energy data"""
        try:
            # Get latest motor measurements for all cranes
            latest_measurements = []
            energy_history = []
            cranes = Crane.objects.filter(is_active=True)
            
            # Current energy data
            for crane in cranes:
                latest_motor = CraneMotorMeasurement.objects.filter(
                    crane=crane
                ).order_by('-timestamp').first()
                
                if latest_motor:
                    latest_measurements.append({
                        'crane_name': crane.crane_name,
                        'total_power': float(latest_motor.total_power) if latest_motor.total_power else 0,
                        'total_current': float(latest_motor.total_current) if latest_motor.total_current else 0,
                        'hoist_power': float(latest_motor.hoist_power) if latest_motor.hoist_power else 0,
                        'ct_power': float(latest_motor.ct_power) if latest_motor.ct_power else 0,
                        'lt_power': float(latest_motor.lt_power) if latest_motor.lt_power else 0,
                        'timestamp': latest_motor.timestamp.isoformat()
                    })
            
            # Energy history (last 50 records)
            recent_energy = CraneMotorMeasurement.objects.filter(
                timestamp__gte=timezone.now() - timedelta(hours=24)
            ).order_by('-timestamp')[:50]
            
            for energy in recent_energy:
                energy_history.append({
                    'timestamp': energy.timestamp.isoformat(),
                    'crane_name': energy.crane.crane_name,
                    'motor_type': 'All Motors',
                    'power_kw': float(energy.total_power) if energy.total_power else 0,
                    'current_a': float(energy.total_current) if energy.total_current else 0,
                    'voltage_v': float(energy.hoist_voltage) if energy.hoist_voltage else 0,
                    'energy_kwh': 0,
                    'cost': 0,
                    'status': 'Normal'
                })
            
            # Calculate energy metrics
            total_power = sum(item['total_power'] for item in latest_measurements)
            total_current = sum(item['total_current'] for item in latest_measurements)
            
            # Simplified energy cost calculation
            energy_kwh = total_power * 0.25
            hourly_cost = energy_kwh * 0.15
            
            return {
                'current_energy': latest_measurements,
                'energy_history': energy_history,
                'energy_metrics': {
                    'total_power': round(total_power, 1),
                    'total_current': round(total_current, 1),
                    'total_energy_kwh': round(energy_kwh, 2),
                    'hourly_energy_cost': round(hourly_cost, 2),
                    'system_efficiency': 87.0,
                    'energy_per_ton': 1.2
                }
            }
            
        except Exception as e:
            print(f"Error in get_energy_data: {e}")
            return {
                'current_energy': [],
                'energy_history': [],
                'energy_metrics': {},
                'error': str(e)
            }

class AlarmConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.channel_layer.group_add("alarms", self.channel_name)
        await self.accept()
        print("✅ Alarms WebSocket connected")
        
        # Send recent alarms
        await self.send_recent_alarms()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard("alarms", self.channel_name)
        print("🔴 Alarms WebSocket disconnected")

    async def receive(self, text_data):
        """Handle client messages"""
        try:
            data = json.loads(text_data)
            if data.get('type') == 'acknowledge':
                alarm_id = data.get('alarm_id')
                await self.acknowledge_alarm(alarm_id)
        except json.JSONDecodeError:
            pass

    async def new_alarm(self, event):
        """Send new alarm notifications"""
        await self.send(json.dumps({
            'type': 'new_alarm',
            'data': event['data']
        }, default=self.decimal_default))

    async def send_recent_alarms(self):
        """Send recent unacknowledged alarms"""
        alarms = await self.get_recent_alarms()
        await self.send(json.dumps({
            'type': 'recent_alarms',
            'data': alarms
        }, default=self.decimal_default))

    def decimal_default(self, obj):
        """Convert Decimal objects to float for JSON serialization"""
        if isinstance(obj, Decimal):
            return float(obj)
        raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")

    @database_sync_to_async
    def get_recent_alarms(self):
        """Get recent unacknowledged alarms"""
        try:
            alarms = CraneAlarm.objects.filter(
                is_acknowledged=False,
                timestamp__gte=timezone.now() - timezone.timedelta(hours=24)
            ).order_by('-timestamp')[:10]
            
            alarm_list = []
            for alarm in alarms:
                alarm_list.append({
                    'id': alarm.id,
                    'crane_name': alarm.crane.crane_name,
                    'message': alarm.alarm_message,
                    'severity': alarm.alarm_severity,
                    'timestamp': alarm.timestamp.isoformat()
                })
            
            return alarm_list
            
        except Exception as e:
            return []

    @database_sync_to_async
    def acknowledge_alarm(self, alarm_id):
        """Acknowledge an alarm"""
        try:
            alarm = CraneAlarm.objects.get(id=alarm_id)
            alarm.is_acknowledged = True
            alarm.save()
            return True
        except CraneAlarm.DoesNotExist:
            return False