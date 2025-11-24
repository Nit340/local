from rest_framework import status
from rest_framework.decorators import api_view, action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ViewSet
from django.utils import timezone
from datetime import datetime, timedelta
from django.db.models import Q, Sum, Avg, Max, Min, Count, F, DurationField
from django.db.models.functions import TruncHour, TruncDay, Cast
from .models import (
    Crane, CraneMotorMeasurement, CraneIOStatus, 
    CraneLoadcellMeasurement, CraneAlarm, CraneConfiguration,
    CraneGatewayMapping, IoTGateway
)
from .serializers import (
    CraneSerializer, CraneMotorMeasurementSerializer, 
    CraneIOStatusSerializer, CraneLoadcellMeasurementSerializer,
    CraneAlarmSerializer, CraneConfigurationSerializer,
    IoTGatewaySerializer, CraneGatewayMappingSerializer
)
from .mqtt_client import mqtt_client

class DashboardView(APIView):
    """
    Dashboard Overview - Real-time view of all crane operations
    """
    def get(self, request):
        try:
            # Get latest data for all cranes
            cranes = Crane.objects.filter(is_active=True)
            
            # Calculate overall statistics
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
                
                # Calculate crane status
                if latest_motor:
                    if latest_motor.total_power and latest_motor.total_power > 0:
                        crane.status = 'working'
                        active_cranes += 1
                        total_power += latest_motor.total_power
                        total_current += latest_motor.total_current or 0
                    else:
                        crane.status = 'idle'
                        idle_cranes += 1
                else:
                    crane.status = 'idle'
                    idle_cranes += 1
                
                crane.save()
                
                crane_details.append({
                    'id': crane.id,
                    'name': crane.crane_name,
                    'status': crane.status,
                    'current_load': latest_load.load if latest_load else 0,
                    'capacity': latest_load.capacity if latest_load else crane.capacity_tonnes * 1000,
                    'load_percentage': latest_load.load_percentage if latest_load else 0,
                    'load_status': latest_load.status if latest_load else 'normal',
                    'device_ids': crane.device_ids,
                    'last_updated': latest_motor.timestamp if latest_motor else crane.updated_at
                })
            
            total_cranes = cranes.count()
            
            # Calculate OEE (simplified calculation)
            # In real implementation, this would be more complex
            availability = 85.0  # Placeholder
            performance = 94.0   # Placeholder
            quality = 99.0       # Placeholder
            oee = (availability * performance * quality) / 10000
            
            response_data = {
                'quick_stats': {
                    'total_power': round(total_power, 1),
                    'total_current': round(total_current, 1),
                    'active_cranes': active_cranes,
                    'idle_cranes': idle_cranes,
                    'total_cranes': total_cranes,
                    'utilization': round((active_cranes / total_cranes) * 100, 1) if total_cranes > 0 else 0,
                },
                'oee_metrics': {
                    'oee': round(oee, 1),
                    'availability': availability,
                    'performance': performance,
                    'quality': quality,
                    'oee_change': 3.8,  # Placeholder
                    'availability_change': -25,  # Placeholder
                    'performance_change': -16,   # Placeholder
                },
                'crane_details': crane_details
            }
            
            return Response(response_data)
            
        except Exception as e:
            return Response(
                {'error': f'Error fetching dashboard data: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class OperationsView(APIView):
    """
    Operations Log - Complete record of all crane operations
    """
    def get(self, request):
        try:
            crane_id = request.GET.get('crane_id')
            operation_type = request.GET.get('operation_type')
            date_range = request.GET.get('date_range', 'today')
            
            # Build filters
            filters = Q()
            if crane_id and crane_id != 'all':
                filters &= Q(crane_id=crane_id)
            
            # Get operations from IO status (simplified approach)
            # In real implementation, you'd use crane_motion_operations table
            io_operations = CraneIOStatus.objects.filter(filters)
            
            # Apply date range filter
            if date_range == 'today':
                today = timezone.now().date()
                io_operations = io_operations.filter(timestamp__date=today)
            elif date_range == 'yesterday':
                yesterday = timezone.now().date() - timedelta(days=1)
                io_operations = io_operations.filter(timestamp__date=yesterday)
            elif date_range == 'week':
                week_ago = timezone.now() - timedelta(days=7)
                io_operations = io_operations.filter(timestamp__gte=week_ago)
            
            # Calculate operation counts
            hoist_up_count = io_operations.filter(hoist_up=True).count()
            hoist_down_count = io_operations.filter(hoist_down=True).count()
            ct_left_count = io_operations.filter(ct_left=True).count()
            ct_right_count = io_operations.filter(ct_right=True).count()
            lt_forward_count = io_operations.filter(lt_forward=True).count()
            lt_reverse_count = io_operations.filter(lt_reverse=True).count()
            stop_count = io_operations.filter(stop=True).count()
            
            # Calculate total duration (simplified)
            total_duration = timedelta()
            
            # Get operations log for table
            operations_log = []
            for io_op in io_operations.order_by('-timestamp')[:100]:  # Last 100 operations
                operation_type = self.get_operation_type(io_op)
                if operation_type:
                    operations_log.append({
                        'timestamp': io_op.timestamp,
                        'crane_id': io_op.crane.id,
                        'crane_name': io_op.crane.crane_name,
                        'operation': operation_type,
                        'duration': 'N/A',  # Would need motion_operations table
                        'load_kg': 'N/A'    # Would need to join with load data
                    })
            
            response_data = {
                'operation_counts': {
                    'hoist': {
                        'total': hoist_up_count + hoist_down_count,
                        'up': hoist_up_count,
                        'down': hoist_down_count
                    },
                    'ct': {
                        'total': ct_left_count + ct_right_count,
                        'left': ct_left_count,
                        'right': ct_right_count
                    },
                    'lt': {
                        'total': lt_forward_count + lt_reverse_count,
                        'forward': lt_forward_count,
                        'reverse': lt_reverse_count
                    },
                    'switch': stop_count,
                    'total_duration': str(total_duration).split('.')[0],  # Remove microseconds
                    'total_load': '287.5T'  # Placeholder
                },
                'operations_log': operations_log
            }
            
            return Response(response_data)
            
        except Exception as e:
            return Response(
                {'error': f'Error fetching operations data: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def get_operation_type(self, io_status):
        """Determine operation type from IO status"""
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

class LoadMonitoringView(APIView):
    """
    Load Monitoring - Current load across all cranes
    """
    def get(self, request):
        try:
            crane_id = request.GET.get('crane_id', 'all')
            load_status = request.GET.get('load_status', 'all')
            date_range = request.GET.get('date_range', 'today')
            
            # Build filters
            filters = Q()
            if crane_id != 'all':
                filters &= Q(crane_id=crane_id)
            if load_status != 'all':
                filters &= Q(status=load_status)
            
            # Apply date range
            load_data = CraneLoadcellMeasurement.objects.filter(filters)
            
            if date_range == 'today':
                today = timezone.now().date()
                load_data = load_data.filter(timestamp__date=today)
            elif date_range == 'yesterday':
                yesterday = timezone.now().date() - timedelta(days=1)
                load_data = load_data.filter(timestamp__date=yesterday)
            elif date_range == 'week':
                week_ago = timezone.now() - timedelta(days=7)
                load_data = load_data.filter(timestamp__gte=week_ago)
            
            # Get current load stats
            current_loads = []
            total_load = 0
            total_capacity = 0
            max_capacity = 0
            max_capacity_crane = None
            
            cranes = Crane.objects.filter(is_active=True)
            for crane in cranes:
                latest_load = CraneLoadcellMeasurement.objects.filter(
                    crane=crane
                ).order_by('-timestamp').first()
                
                if latest_load:
                    current_loads.append({
                        'crane_id': crane.id,
                        'crane_name': crane.crane_name,
                        'load': latest_load.load,
                        'capacity': latest_load.capacity,
                        'percentage': latest_load.load_percentage,
                        'status': latest_load.status
                    })
                    
                    total_load += latest_load.load
                    total_capacity += latest_load.capacity
                    
                    if latest_load.load > max_capacity:
                        max_capacity = latest_load.load
                        max_capacity_crane = crane.crane_name
            
            avg_capacity = (total_load / total_capacity * 100) if total_capacity > 0 else 0
            
            # Check for active overloads
            active_overloads = CraneLoadcellMeasurement.objects.filter(
                status='overload',
                timestamp__gte=timezone.now() - timedelta(minutes=5)  # Last 5 minutes
            ).count()
            
            # Get load history for table
            load_history = []
            for load in load_data.order_by('-timestamp')[:50]:  # Last 50 records
                # Find corresponding operation
                operation = CraneIOStatus.objects.filter(
                    crane=load.crane,
                    timestamp__range=(
                        load.timestamp - timedelta(seconds=5),
                        load.timestamp + timedelta(seconds=5)
                    )
                ).first()
                
                load_history.append({
                    'timestamp': load.timestamp,
                    'crane_id': load.crane.id,
                    'crane_name': load.crane.crane_name,
                    'operation': self.get_operation_type(operation) if operation else 'N/A',
                    'load_kg': load.load,
                    'capacity': load.capacity,
                    'percentage': round(load.load_percentage, 1),
                    'status': load.status
                })
            
            response_data = {
                'current_stats': {
                    'current_load': round(total_load, 1),
                    'average_capacity': round(avg_capacity, 1),
                    'max_capacity': round(max_capacity, 1),
                    'max_capacity_crane': max_capacity_crane,
                    'overall_status': 'Normal' if active_overloads == 0 else f'{active_overloads} Active Overloads'
                },
                'current_loads': current_loads,
                'load_history': load_history
            }
            
            return Response(response_data)
            
        except Exception as e:
            return Response(
                {'error': f'Error fetching load data: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
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

class EnergyMonitoringView(APIView):
    """
    Energy Monitoring - Comprehensive energy consumption analysis
    """
    def get(self, request):
        try:
            crane_id = request.GET.get('crane_id', 'all')
            motor_type = request.GET.get('motor_type', 'all')
            date_range = request.GET.get('date_range', 'today')
            
            # Build filters
            filters = Q()
            if crane_id != 'all':
                filters &= Q(crane_id=crane_id)
            
            # Apply date range
            energy_data = CraneMotorMeasurement.objects.filter(filters)
            
            if date_range == 'today':
                today = timezone.now().date()
                energy_data = energy_data.filter(timestamp__date=today)
            elif date_range == 'yesterday':
                yesterday = timezone.now().date() - timedelta(days=1)
                energy_data = energy_data.filter(timestamp__date=yesterday)
            elif date_range == 'week':
                week_ago = timezone.now() - timedelta(days=7)
                energy_data = energy_data.filter(timestamp__gte=week_ago)
            
            # Calculate energy metrics
            total_power = energy_data.aggregate(
                avg_power=Avg('total_power')
            )['avg_power'] or 0
            
            # Calculate total energy (kWh) - simplified
            # In real implementation, you'd integrate power over time
            total_energy = total_power * 24  # Placeholder calculation
            
            # Get configuration for cost calculation
            config = CraneConfiguration.objects.first()
            tariff_rate = config.tariff_rate if config else 0.15
            hourly_cost = total_power * tariff_rate
            
            # Calculate energy per ton (simplified)
            total_load_moved = 1000  # Placeholder - would come from lift cycles
            energy_per_ton = total_energy / total_load_moved if total_load_moved > 0 else 0
            
            system_efficiency = 87.0  # Placeholder
            
            # Get energy history for table
            energy_history = []
            for motor_data in energy_data.order_by('-timestamp')[:50]:  # Last 50 records
                # Add entries for each motor type
                motors = []
                if motor_data.hoist_power:
                    motors.append({
                        'motor_type': 'Hoist',
                        'power': motor_data.hoist_power,
                        'current': motor_data.hoist_current,
                        'voltage': motor_data.hoist_voltage
                    })
                if motor_data.ct_power:
                    motors.append({
                        'motor_type': 'CT',
                        'power': motor_data.ct_power,
                        'current': motor_data.ct_current,
                        'voltage': motor_data.ct_voltage
                    })
                if motor_data.lt_power:
                    motors.append({
                        'motor_type': 'LT',
                        'power': motor_data.lt_power,
                        'current': motor_data.lt_current,
                        'voltage': motor_data.lt_voltage
                    })
                
                for motor in motors:
                    if motor_type == 'all' or motor_type.lower() == motor['motor_type'].lower():
                        energy_history.append({
                            'timestamp': motor_data.timestamp,
                            'crane_id': motor_data.crane.id,
                            'crane_name': motor_data.crane.crane_name,
                            'motor_type': motor['motor_type'],
                            'power_kw': round(motor['power'], 2),
                            'current_a': round(motor['current'], 2) if motor['current'] else 0,
                            'voltage_v': round(motor['voltage'], 2) if motor['voltage'] else 0,
                            'energy_kwh': round(total_energy, 2),
                            'cost': round(hourly_cost, 2),
                            'status': 'Normal'
                        })
            
            response_data = {
                'energy_metrics': {
                    'total_power': round(total_power, 1),
                    'hourly_energy_cost': round(hourly_cost, 2),
                    'system_efficiency': system_efficiency,
                    'energy_per_ton': round(energy_per_ton, 2)
                },
                'energy_history': energy_history
            }
            
            return Response(response_data)
            
        except Exception as e:
            return Response(
                {'error': f'Error fetching energy data: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class CraneManagementView(ViewSet):
    """
    Crane Management - CRUD operations for cranes and gateways
    """
    
    def list_cranes(self, request):
        """Get all cranes"""
        cranes = Crane.objects.filter(is_active=True)
        serializer = CraneSerializer(cranes, many=True)
        return Response(serializer.data)
    
    def create_crane(self, request):
        """Create new crane"""
        serializer = CraneSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def update_crane(self, request, pk=None):
        """Update crane"""
        try:
            crane = Crane.objects.get(pk=pk)
            serializer = CraneSerializer(crane, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Crane.DoesNotExist:
            return Response(
                {'error': 'Crane not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
    
    def add_gateway(self, request):
        """Add IoT gateway"""
        serializer = IoTGatewaySerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def map_crane_gateway(self, request):
        """Map crane to gateway with MQTT topic"""
        serializer = CraneGatewayMappingSerializer(data=request.data)
        if serializer.is_valid():
            mapping = serializer.save()
            
            # Subscribe to the new topic
            mqtt_client.add_crane_topic(mapping.mqtt_topic, mapping.crane.crane_name)
            
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# Utility endpoints
@api_view(['GET'])
def get_crane_list(request):
    """Get list of all cranes for dropdowns"""
    cranes = Crane.objects.filter(is_active=True).values('id', 'crane_name')
    return Response(list(cranes))

@api_view(['GET'])
def get_recent_alarms(request):
    """Get recent alarms"""
    alarms = CraneAlarm.objects.filter(
        is_acknowledged=False
    ).order_by('-timestamp')[:10]
    serializer = CraneAlarmSerializer(alarms, many=True)
    return Response(serializer.data)

@api_view(['POST'])
def acknowledge_alarm(request, alarm_id):
    """Acknowledge an alarm"""
    try:
        alarm = CraneAlarm.objects.get(id=alarm_id)
        alarm.is_acknowledged = True
        alarm.save()
        return Response({'status': 'Alarm acknowledged'})
    except CraneAlarm.DoesNotExist:
        return Response(
            {'error': 'Alarm not found'}, 
            status=status.HTTP_404_NOT_FOUND
        )