from django.utils import timezone
from datetime import timedelta
from django.db.models import Sum, Avg
from ..models import CraneIOStatus, CraneLoadcellMeasurement

class OEECalculator:
    """
    Calculate Overall Equipment Effectiveness (OEE)
    """
    
    @staticmethod
    def calculate_oee(crane, start_time, end_time, planned_production_time=None):
        """
        Calculate OEE metrics: Availability, Performance, Quality
        """
        if planned_production_time is None:
            planned_production_time = end_time - start_time
        
        # Calculate Availability
        availability = OEECalculator.calculate_availability(
            crane, start_time, end_time, planned_production_time
        )
        
        # Calculate Performance
        performance = OEECalculator.calculate_performance(
            crane, start_time, end_time
        )
        
        # Calculate Quality (simplified - assume 99% for now)
        quality = OEECalculator.calculate_quality(crane, start_time, end_time)
        
        # Calculate OEE
        oee = (availability * performance * quality) / 10000
        
        return {
            'availability': availability,
            'performance': performance,
            'quality': quality,
            'oee': oee
        }
    
    @staticmethod
    def calculate_availability(crane, start_time, end_time, planned_production_time):
        """Calculate availability percentage"""
        total_operation_time = OEECalculator._get_total_operation_time(crane, start_time, end_time)
        
        if planned_production_time.total_seconds() > 0:
            availability = (total_operation_time.total_seconds() / planned_production_time.total_seconds()) * 100
            return min(availability, 100)
        return 0
    
    @staticmethod
    def _get_total_operation_time(crane, start_time, end_time):
        """Calculate total time crane was operating"""
        io_data = CraneIOStatus.objects.filter(
            crane=crane,
            timestamp__range=(start_time, end_time)
        )
        
        operation_time = timedelta()
        operation_start = None
        
        for io_point in io_data:
            is_operating = any([
                io_point.hoist_up, io_point.hoist_down,
                io_point.ct_left, io_point.ct_right,
                io_point.lt_forward, io_point.lt_reverse
            ])
            
            if is_operating and operation_start is None:
                operation_start = io_point.timestamp
            elif not is_operating and operation_start is not None:
                operation_time += io_point.timestamp - operation_start
                operation_start = None
        
        # Add final operation if still operating at end
        if operation_start is not None:
            operation_time += end_time - operation_start
        
        return operation_time
    
    @staticmethod
    def calculate_performance(crane, start_time, end_time):
        """Calculate performance percentage"""
        # Simplified calculation - compare actual cycles to ideal cycles
        actual_cycles = CraneIOStatus.objects.filter(
            crane=crane,
            timestamp__range=(start_time, end_time),
            hoist_up=True
        ).count()
        
        # Assume ideal cycle time (placeholder)
        ideal_cycles_per_hour = 60  # 60 cycles per hour
        total_hours = (end_time - start_time).total_seconds() / 3600
        
        if total_hours > 0:
            ideal_cycles = ideal_cycles_per_hour * total_hours
            if ideal_cycles > 0:
                performance = (actual_cycles / ideal_cycles) * 100
                return min(performance, 100)
        
        return 0
    
    @staticmethod
    def calculate_quality(crane, start_time, end_time):
        """Calculate quality percentage"""
        # Simplified - in real implementation, track good vs total parts
        # For now, return a high percentage as placeholder
        return 99.0