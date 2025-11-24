from django.core.management.base import BaseCommand
from cranes.services.kpi_manager import KPIManager

class Command(BaseCommand):
    help = 'Calculate and store hourly KPIs for all cranes'
    
    def handle(self, *args, **options):
        self.stdout.write('Calculating hourly KPIs...')
        KPIManager.calculate_hourly_kpis()
        self.stdout.write(
            self.style.SUCCESS('Successfully calculated hourly KPIs')
        )