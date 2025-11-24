from django.core.management.base import BaseCommand
from cranes.models import Crane, CraneConfiguration, IoTGateway, CraneGatewayMapping

class Command(BaseCommand):
    help = 'Initialize the crane monitoring system with sample data'
    
    def handle(self, *args, **options):
        self.stdout.write('Initializing Crane Monitoring System...')
        
        # Create sample cranes
        cranes_data = [
            {
                'crane_name': 'CRN-001',
                'crane_type': 'EOT',
                'capacity_tonnes': 5.0,
                'location': 'Workshop Bay 1',
                'device_ids': ['DEV-001', 'DEV-002']
            },
            {
                'crane_name': 'CRN-002', 
                'crane_type': 'EOT',
                'capacity_tonnes': 10.0,
                'location': 'Workshop Bay 2',
                'device_ids': ['DEV-003', 'DEV-004']
            }
        ]
        
        for crane_data in cranes_data:
            crane, created = Crane.objects.get_or_create(
                crane_name=crane_data['crane_name'],
                defaults=crane_data
            )
            
            if created:
                # Create configuration
                CraneConfiguration.objects.create(
                    crane=crane,
                    max_load_capacity=crane_data['capacity_tonnes'] * 1000,
                    tariff_rate=0.15,
                    currency='USD',
                    target_energy_per_ton=1.0
                )
                self.stdout.write(
                    self.style.SUCCESS(f'Created crane: {crane.crane_name}')
                )
        
        # Create IoT Gateway
        gateway, created = IoTGateway.objects.get_or_create(
            gateway_name='Gateway-01',
            defaults={
                'gateway_type': 'Modbus-MQTT',
                'ip_address': '192.168.1.100',
                'status': 'active'
            }
        )
        
        if created:
            self.stdout.write(
                self.style.SUCCESS(f'Created gateway: {gateway.gateway_name}')
            )
        
        # Create mappings
        for crane in Crane.objects.all():
            mapping, created = CraneGatewayMapping.objects.get_or_create(
                crane=crane,
                gateway=gateway,
                defaults={
                    'mqtt_topic': f'crane/{crane.crane_name.lower()}/data'
                }
            )
            
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'Created mapping: {crane.crane_name} -> {gateway.gateway_name}')
                )
        
        self.stdout.write(
            self.style.SUCCESS('System initialization completed successfully!')
        )