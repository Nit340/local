from django.utils import timezone
from datetime import timedelta
from django.db.models import Sum, Avg
from ..models import CraneMotorMeasurement

class EnergyCalculator:
    """
    Calculate energy consumption and related metrics
    """
    
    @staticmethod
    def calculate_energy_consumption(crane, start_time, end_time):
        """
        Calculate total energy consumption in kWh
        Using trapezoidal integration of power over time
        """
        power_data = CraneMotorMeasurement.objects.filter(
            crane=crane,
            timestamp__range=(start_time, end_time)
        ).order_by('timestamp')
        
        total_energy_kwh = 0
        prev_time = None
        prev_power = 0
        
        for measurement in power_data:
            if prev_time is not None:
                # Calculate time difference in hours
                time_diff_hours = (measurement.timestamp - prev_time).total_seconds() / 3600
                
                # Calculate energy using trapezoidal rule
                avg_power = (prev_power + measurement.total_power) / 2
                energy = avg_power * time_diff_hours
                total_energy_kwh += energy
            
            prev_time = measurement.timestamp
            prev_power = measurement.total_power or 0
        
        return total_energy_kwh
    
    @staticmethod
    def calculate_energy_cost(energy_kwh, tariff_rate):
        """Calculate energy cost"""
        return energy_kwh * tariff_rate
    
    @staticmethod
    def calculate_energy_per_ton(energy_kwh, total_mass_tonnes):
        """Calculate energy consumption per tonne"""
        if total_mass_tonnes > 0:
            return energy_kwh / total_mass_tonnes
        return 0
    
    @staticmethod
    def calculate_system_efficiency(actual_energy_per_ton, target_energy_per_ton):
        """Calculate system efficiency percentage"""
        if target_energy_per_ton > 0:
            efficiency = (target_energy_per_ton / actual_energy_per_ton) * 100
            return min(efficiency, 100)  # Cap at 100%
        return 0