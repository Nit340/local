from django.utils import timezone
from datetime import timedelta
from django.db.models import Q, Sum, Avg, Max, Min, Count
from ..models import CraneIOStatus, CraneMotorMeasurement, CraneLoadcellMeasurement

class OperationCalculator:
    """
    Calculate operation durations, lifts, and motion statistics
    """
    
    @staticmethod
    def calculate_operation_durations(crane, start_time, end_time):
        """
        Calculate operation durations for a crane within a time range
        """
        io_data = CraneIOStatus.objects.filter(
            crane=crane,
            timestamp__range=(start_time, end_time)
        ).order_by('timestamp')
        
        operations = {
            'hoist_up': timedelta(),
            'hoist_down': timedelta(),
            'ct_left': timedelta(),
            'ct_right': timedelta(),
            'lt_forward': timedelta(),
            'lt_reverse': timedelta(),
            'stop': timedelta()
        }
        
        current_operation = None
        operation_start = None
        
        for io_point in io_data:
            # Determine current operation
            new_operation = OperationCalculator._get_active_operation(io_point)
            
            if current_operation != new_operation:
                # End previous operation
                if current_operation and operation_start:
                    duration = io_point.timestamp - operation_start
                    if current_operation in operations:
                        operations[current_operation] += duration
                
                # Start new operation
                current_operation = new_operation
                operation_start = io_point.timestamp
        
        return operations
    
    @staticmethod
    def _get_active_operation(io_status):
        """Get the currently active operation from IO status"""
        if io_status.hoist_up:
            return 'hoist_up'
        elif io_status.hoist_down:
            return 'hoist_down'
        elif io_status.ct_left:
            return 'ct_left'
        elif io_status.ct_right:
            return 'ct_right'
        elif io_status.lt_forward:
            return 'lt_forward'
        elif io_status.lt_reverse:
            return 'lt_reverse'
        elif io_status.stop:
            return 'stop'
        return None
    
    @staticmethod
    def count_lifts(crane, start_time, end_time):
        """
        Count hoist up cycles (lifts) within time range
        """
        io_data = CraneIOStatus.objects.filter(
            crane=crane,
            timestamp__range=(start_time, end_time),
            hoist_up=True
        ).order_by('timestamp')
        
        lift_count = 0
        last_hoist_up = None
        
        for io_point in io_data:
            if last_hoist_up is None:
                last_hoist_up = io_point.timestamp
            else:
                # If more than 5 seconds between hoist up signals, count as new lift
                if (io_point.timestamp - last_hoist_up).total_seconds() > 5:
                    lift_count += 1
                last_hoist_up = io_point.timestamp
        
        return lift_count
    
    @staticmethod
    def calculate_total_mass_moved(crane, start_time, end_time):
        """
        Calculate total mass moved during lifts
        """
        lifts = CraneLoadcellMeasurement.objects.filter(
            crane=crane,
            timestamp__range=(start_time, end_time)
        ).order_by('timestamp')
        
        total_mass_kg = 0
        last_load = 0
        
        for lift in lifts:
            if lift.load > last_load:  # Load increasing - lifting
                total_mass_kg += lift.load
            last_load = lift.load
        
        return total_mass_kg / 1000  # Convert to tonnes
    
    @staticmethod
    def _count_operations(crane, start_time, end_time, operation_type):
        """Count specific operation types within time range"""
        filter_kwargs = {
            'crane': crane,
            'timestamp__range': (start_time, end_time),
            operation_type: True
        }
        return CraneIOStatus.objects.filter(**filter_kwargs).count()