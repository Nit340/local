from django.core.management.base import BaseCommand
from cranes.services.kpi_manager import KPIManager

class Command(BaseCommand):
    help = 'Calculate and store daily KPIs for all cranes'
    
    def handle(self, *args, **options):
        self.stdout.write('Calculating daily KPIs...')
        KPIManager.calculate_daily_kpis()
        self.stdout.write(
            self.style.SUCCESS('Successfully calculated daily KPIs')
        )