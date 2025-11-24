from django.utils import timezone
from datetime import datetime, timedelta
from ..models import Crane, CraneHourlyKPIs, CraneDailyKPIs
from .operation_calculator import OperationCalculator
from .energy_calculator import EnergyCalculator
from .oee_calculator import OEECalculator

class KPIManager:
    """
    Manage KPI calculations and storage
    """
    
    @staticmethod
    def calculate_hourly_kpis():
        """Calculate and store hourly KPIs for all cranes"""
        current_time = timezone.now()
        hour_start = current_time.replace(minute=0, second=0, microsecond=0)
        hour_end = hour_start + timedelta(hours=1)
        
        cranes = Crane.objects.filter(is_active=True)
        
        for crane in cranes:
            KPIManager._calculate_crane_hourly_kpis(crane, hour_start, hour_end)
    
    @staticmethod
    def _calculate_crane_hourly_kpis(crane, hour_start, hour_end):
        """Calculate hourly KPIs for a specific crane"""
        try:
            # Calculate operation durations
            operations = OperationCalculator.calculate_operation_durations(
                crane, hour_start, hour_end
            )
            
            # Count lifts
            lift_count = OperationCalculator.count_lifts(crane, hour_start, hour_end)
            
            # Calculate total mass moved
            total_mass_tonnes = OperationCalculator.calculate_total_mass_moved(
                crane, hour_start, hour_end
            )
            
            # Calculate energy consumption
            energy_kwh = EnergyCalculator.calculate_energy_consumption(
                crane, hour_start, hour_end
            )
            
            # Get crane configuration for cost calculation
            config = crane.craneconfiguration
            tariff_rate = config.tariff_rate if config else 0.15
            hourly_cost = EnergyCalculator.calculate_energy_cost(energy_kwh, tariff_rate)
            
            # Calculate energy per ton
            energy_per_ton = EnergyCalculator.calculate_energy_per_ton(
                energy_kwh, total_mass_tonnes
            )
            
            # Calculate system efficiency
            target_energy_per_ton = config.target_energy_per_ton if config else 1.0
            system_efficiency = EnergyCalculator.calculate_system_efficiency(
                energy_per_ton, target_energy_per_ton
            )
            
            # Calculate OEE
            oee_metrics = OEECalculator.calculate_oee(crane, hour_start, hour_end)
            
            # Create or update hourly KPI record
            kpi, created = CraneHourlyKPIs.objects.update_or_create(
                crane=crane,
                hour_start=hour_start,
                hour_end=hour_end,
                defaults={
                    # Operation times
                    'hoist_up_time': operations['hoist_up'],
                    'hoist_down_time': operations['hoist_down'],
                    'ct_left_time': operations['ct_left'],
                    'ct_right_time': operations['ct_right'],
                    'lt_forward_time': operations['lt_forward'],
                    'lt_reverse_time': operations['lt_reverse'],
                    'stop_time': operations['stop'],
                    'total_motion_time': sum(operations.values(), timedelta()),
                    
                    # Operation counts
                    'hoist_up_count': OperationCalculator._count_operations(
                        crane, hour_start, hour_end, 'hoist_up'
                    ),
                    'hoist_down_count': OperationCalculator._count_operations(
                        crane, hour_start, hour_end, 'hoist_down'
                    ),
                    'ct_left_count': OperationCalculator._count_operations(
                        crane, hour_start, hour_end, 'ct_left'
                    ),
                    'ct_right_count': OperationCalculator._count_operations(
                        crane, hour_start, hour_end, 'ct_right'
                    ),
                    'lt_forward_count': OperationCalculator._count_operations(
                        crane, hour_start, hour_end, 'lt_forward'
                    ),
                    'lt_reverse_count': OperationCalculator._count_operations(
                        crane, hour_start, hour_end, 'lt_reverse'
                    ),
                    'stop_count': OperationCalculator._count_operations(
                        crane, hour_start, hour_end, 'stop'
                    ),
                    
                    # Lifting data
                    'total_lifts': lift_count,
                    'total_mass_moved_tonnes': total_mass_tonnes,
                    'average_load_per_lift': total_mass_tonnes / lift_count if lift_count > 0 else 0,
                    
                    # Energy metrics
                    'total_energy_kwh': energy_kwh,
                    'hourly_energy_cost': hourly_cost,
                    'energy_per_ton': energy_per_ton,
                    'system_efficiency': system_efficiency,
                    
                    # OEE metrics
                    'availability': oee_metrics['availability'],
                    'performance': oee_metrics['performance'],
                    'quality': oee_metrics['quality'],
                    'oee': oee_metrics['oee'],
                }
            )
            
            print(f"✅ Hourly KPIs calculated for {crane.crane_name} at {hour_start}")
            
        except Exception as e:
            print(f"❌ Error calculating hourly KPIs for {crane.crane_name}: {e}")
    
    @staticmethod
    def calculate_daily_kpis():
        """Calculate and store daily KPIs for all cranes"""
        current_time = timezone.now()
        date = current_time.date()
        
        cranes = Crane.objects.filter(is_active=True)
        
        for crane in cranes:
            KPIManager._calculate_crane_daily_kpis(crane, date)
    
    @staticmethod
    def _calculate_crane_daily_kpis(crane, date):
        """Calculate daily KPIs for a specific crane"""
        try:
            day_start = timezone.make_aware(datetime.combine(date, datetime.min.time()))
            day_end = day_start + timedelta(days=1)
            
            # Get hourly KPIs for the day
            hourly_kpis = CraneHourlyKPIs.objects.filter(
                crane=crane,
                hour_start__range=(day_start, day_end)
            )
            
            if not hourly_kpis.exists():
                return
            
            # Aggregate daily metrics from hourly data
            daily_data = hourly_kpis.aggregate(
                total_operation_time=Sum('total_motion_time'),
                total_lifts=Sum('total_lifts'),
                total_mass_moved_tonnes=Sum('total_mass_moved_tonnes'),
                total_energy_kwh=Sum('total_energy_kwh'),
                total_energy_cost=Sum('hourly_energy_cost'),
                avg_energy_per_ton=Avg('energy_per_ton'),
                avg_efficiency=Avg('system_efficiency'),
                avg_availability=Avg('availability'),
                avg_performance=Avg('performance'),
                avg_quality=Avg('quality'),
                avg_oee=Avg('oee'),
                peak_load=Max('total_mass_moved_tonnes'),
                avg_power_demand=Avg('total_energy_kwh') * 4  # Convert to kW (kWh/0.25h)
            )
            
            # Create or update daily KPI record
            kpi, created = CraneDailyKPIs.objects.update_or_create(
                crane=crane,
                date=date,
                shift='day',  # You can modify this for shift-based calculations
                defaults={
                    'total_operation_time': daily_data['total_operation_time'] or timedelta(),
                    'total_lifts': daily_data['total_lifts'] or 0,
                    'total_mass_moved_tonnes': daily_data['total_mass_moved_tonnes'] or 0,
                    'total_energy_kwh': daily_data['total_energy_kwh'] or 0,
                    'total_energy_cost': daily_data['total_energy_cost'] or 0,
                    'average_energy_per_ton': daily_data['avg_energy_per_ton'] or 0,
                    'average_efficiency': daily_data['avg_efficiency'] or 0,
                    'availability': daily_data['avg_availability'] or 0,
                    'performance': daily_data['avg_performance'] or 0,
                    'quality': daily_data['avg_quality'] or 0,
                    'oee': daily_data['avg_oee'] or 0,
                    'peak_load': daily_data['peak_load'] or 0,
                    'average_power_demand': daily_data['avg_power_demand'] or 0,
                }
            )
            
            print(f"✅ Daily KPIs calculated for {crane.crane_name} on {date}")
            
        except Exception as e:
            print(f"❌ Error calculating daily KPIs for {crane.crane_name}: {e}")