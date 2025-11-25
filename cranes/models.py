from django.db import models
from django.utils import timezone

class Crane(models.Model):
    CRANE_STATUS = [
        ('working', 'Working'),
        ('idle', 'Idle'),
        ('maintenance', 'Maintenance'),
        ('error', 'Error'),
    ]
    
    crane_name = models.CharField(max_length=100, unique=True)
    crane_type = models.CharField(max_length=50, default='EOT')
    capacity_tonnes = models.DecimalField(max_digits=10, decimal_places=2)
    location = models.CharField(max_length=100)
    status = models.CharField(max_length=20, choices=CRANE_STATUS, default='idle')
    is_active = models.BooleanField(default=True)
    device_ids = models.JSONField(default=list)  # Store as list of device IDs
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.crane_name

class IoTGateway(models.Model):
    GATEWAY_STATUS = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('error', 'Error'),
    ]
    
    gateway_name = models.CharField(max_length=100, unique=True)
    gateway_type = models.CharField(max_length=50)
    ip_address = models.GenericIPAddressField()
    status = models.CharField(max_length=20, choices=GATEWAY_STATUS, default='active')
    last_heartbeat = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.gateway_name

class CraneGatewayMapping(models.Model):
    crane = models.ForeignKey(Crane, on_delete=models.CASCADE)
    gateway = models.ForeignKey(IoTGateway, on_delete=models.CASCADE)
    mqtt_topic = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['crane'],
                condition=models.Q(is_active=True),
                name='unique_active_crane_mapping'
            )
        ]

    def __str__(self):
        return f"{self.crane.crane_name} - {self.gateway.gateway_name}"

class CraneMotorMeasurement(models.Model):
    crane = models.ForeignKey(Crane, on_delete=models.CASCADE)
    
    # Hoist Motor Data
    hoist_voltage = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    hoist_current = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    hoist_power = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    hoist_frequency = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    
    # CT Motor Data
    ct_voltage = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    ct_current = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    ct_power = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    ct_frequency = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    
    # LT Motor Data
    lt_voltage = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    lt_current = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    lt_power = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    lt_frequency = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    
    # Calculated totals
    total_power = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    total_current = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    timestamp = models.DateTimeField()
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        indexes = [
            models.Index(fields=['crane', 'timestamp']),
            models.Index(fields=['timestamp']),
        ]

    def save(self, *args, **kwargs):
        # Calculate total power and current
        total_power = 0
        total_current = 0
        
        if self.hoist_power:
            total_power += self.hoist_power
        if self.ct_power:
            total_power += self.ct_power
        if self.lt_power:
            total_power += self.lt_power
            
        if self.hoist_current:
            total_current += self.hoist_current
        if self.ct_current:
            total_current += self.ct_current
        if self.lt_current:
            total_current += self.lt_current
            
        self.total_power = total_power
        self.total_current = total_current
        
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.crane.crane_name} - Motor Data - {self.timestamp}"

class CraneIOStatus(models.Model):
    crane = models.ForeignKey(Crane, on_delete=models.CASCADE)
    
    # General IO
    start = models.BooleanField(default=False)
    stop = models.BooleanField(default=False)
    
    # Hoist Motor IO
    hoist_up = models.BooleanField(default=False)
    hoist_down = models.BooleanField(default=False)
    
    # CT Motor IO
    ct_left = models.BooleanField(default=False)
    ct_right = models.BooleanField(default=False)
    
    # LT Motor IO
    lt_forward = models.BooleanField(default=False)
    lt_reverse = models.BooleanField(default=False)
    
    timestamp = models.DateTimeField()
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        indexes = [
            models.Index(fields=['crane', 'timestamp']),
            models.Index(fields=['timestamp']),
        ]

    def __str__(self):
        return f"{self.crane.crane_name} - IO Status - {self.timestamp}"

class CraneLoadcellMeasurement(models.Model):
    LOAD_STATUS = [
        ('normal', 'Normal'),
        ('warning', 'Warning'),
        ('overload', 'Overload'),
    ]
    
    crane = models.ForeignKey(Crane, on_delete=models.CASCADE)
    load = models.DecimalField(max_digits=10, decimal_places=2)
    capacity = models.DecimalField(max_digits=10, decimal_places=2)
    load_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    status = models.CharField(max_length=20, choices=LOAD_STATUS, default='normal')
    
    timestamp = models.DateTimeField()
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        indexes = [
            models.Index(fields=['crane', 'timestamp']),
            models.Index(fields=['timestamp']),
        ]

    def save(self, *args, **kwargs):
        # Calculate load percentage
        if self.capacity and self.capacity > 0:
            self.load_percentage = (self.load / self.capacity) * 100
            
            # Determine status based on percentage
            if self.load_percentage >= 95:
                self.status = 'overload'
            elif self.load_percentage >= 80:
                self.status = 'warning'
            else:
                self.status = 'normal'
        
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.crane.crane_name} - Load: {self.load}kg - {self.status}"

class CraneAlarm(models.Model):
    ALARM_SEVERITY = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    
    crane = models.ForeignKey(Crane, on_delete=models.CASCADE)
    alarm_one = models.BooleanField(default=False)
    alarm_two = models.BooleanField(default=False)
    alarm_three = models.BooleanField(default=False)
    alarm_message = models.TextField(blank=True)
    alarm_severity = models.CharField(max_length=20, choices=ALARM_SEVERITY, default='low')
    alarm_type = models.CharField(max_length=50, blank=True)
    is_acknowledged = models.BooleanField(default=False)
    
    timestamp = models.DateTimeField()
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        indexes = [
            models.Index(fields=['crane', 'timestamp']),
            models.Index(fields=['timestamp']),
        ]

    def __str__(self):
        return f"{self.crane.crane_name} - Alarm - {self.alarm_severity}"

class CraneConfiguration(models.Model):
    crane = models.OneToOneField(Crane, on_delete=models.CASCADE)
    tariff_rate = models.DecimalField(max_digits=8, decimal_places=4, default=0.15)
    currency = models.CharField(max_length=10, default='USD')
    target_energy_per_ton = models.DecimalField(max_digits=10, decimal_places=4, default=1.0)
    max_load_capacity = models.DecimalField(max_digits=10, decimal_places=2)
    warning_threshold = models.DecimalField(max_digits=5, decimal_places=2, default=80.0)
    overload_threshold = models.DecimalField(max_digits=5, decimal_places=2, default=95.0)
    
    # OEE Targets
    target_availability = models.DecimalField(max_digits=5, decimal_places=2, default=90.0)
    target_performance = models.DecimalField(max_digits=5, decimal_places=2, default=95.0)
    target_quality = models.DecimalField(max_digits=5, decimal_places=2, default=99.0)
    
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.crane.crane_name} - Configuration"

class MQTTMessageLog(models.Model):
    crane = models.ForeignKey(Crane, on_delete=models.CASCADE, null=True, blank=True)
    gateway = models.ForeignKey(IoTGateway, on_delete=models.CASCADE, null=True, blank=True)
    topic = models.CharField(max_length=255)
    payload = models.JSONField()
    message_type = models.CharField(max_length=50, blank=True)
    timestamp = models.DateTimeField()
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        indexes = [
            models.Index(fields=['crane', 'timestamp']),
            models.Index(fields=['topic']),
        ]

    def __str__(self):
        return f"{self.topic} - {self.timestamp}"
class CraneHourlyKPIs(models.Model):
    crane = models.ForeignKey(Crane, on_delete=models.CASCADE)
    
    hour_start = models.DateTimeField()
    hour_end = models.DateTimeField()
    
    # Operation Times
    hoist_up_time = models.DurationField(null=True, blank=True)
    hoist_down_time = models.DurationField(null=True, blank=True)
    ct_left_time = models.DurationField(null=True, blank=True)
    ct_right_time = models.DurationField(null=True, blank=True)
    lt_forward_time = models.DurationField(null=True, blank=True)
    lt_reverse_time = models.DurationField(null=True, blank=True)
    stop_time = models.DurationField(null=True, blank=True)
    total_motion_time = models.DurationField(null=True, blank=True)
    
    # Operation Counts
    hoist_up_count = models.IntegerField(default=0)
    hoist_down_count = models.IntegerField(default=0)
    ct_left_count = models.IntegerField(default=0)
    ct_right_count = models.IntegerField(default=0)
    lt_forward_count = models.IntegerField(default=0)
    lt_reverse_count = models.IntegerField(default=0)
    stop_count = models.IntegerField(default=0)
    
    # Lifting Data
    total_lifts = models.IntegerField(default=0)
    total_mass_moved_tonnes = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    average_load_per_lift = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Energy Metrics
    total_energy_kwh = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    hourly_energy_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    energy_per_ton = models.DecimalField(max_digits=10, decimal_places=4, default=0)
    system_efficiency = models.DecimalField(max_digits=10, decimal_places=4, default=0)
    
    # OEE Metrics
    availability = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    performance = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    quality = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    oee = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Power Metrics
    average_power = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    peak_power = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    created_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        indexes = [
            models.Index(fields=['crane', 'hour_start']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['crane', 'hour_start'],
                name='unique_crane_hourly_kpis'
            )
        ]

class CraneDailyKPIs(models.Model):
    crane = models.ForeignKey(Crane, on_delete=models.CASCADE)
    
    date = models.DateField()
    shift = models.CharField(max_length=20)  # 'morning', 'evening', 'night', 'day'
    
    # Operation Summary
    total_operation_time = models.DurationField(null=True, blank=True)
    total_lifts = models.IntegerField(default=0)
    total_mass_moved_tonnes = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Energy Summary
    total_energy_kwh = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    total_energy_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    average_energy_per_ton = models.DecimalField(max_digits=10, decimal_places=4, default=0)
    average_efficiency = models.DecimalField(max_digits=10, decimal_places=4, default=0)
    
    # Performance Metrics
    peak_load = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    average_power_demand = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # OEE Metrics
    availability = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    performance = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    quality = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    oee = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['crane', 'date']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['crane', 'date', 'shift'],
                name='unique_crane_daily_kpis'
            )
        ]

class DataPointMapping(models.Model):
    FIELD_TYPE_CHOICES = [
        ('motor_voltage', 'Motor Voltage'),
        ('motor_current', 'Motor Current'),
        ('motor_power', 'Motor Power'),
        ('motor_frequency', 'Motor Frequency'),
        ('load', 'Load'),
        ('capacity', 'Capacity'),
        ('io_status', 'IO Status'),
        ('alarm', 'Alarm'),
    ]
    
    crane = models.ForeignKey(Crane, on_delete=models.CASCADE)
    incoming_field_name = models.CharField(max_length=100, help_text="Field name from MQTT payload")
    mapped_field_name = models.CharField(max_length=100, help_text="Field name in our system")
    field_type = models.CharField(max_length=50, choices=FIELD_TYPE_CHOICES)
    description = models.TextField(blank=True, help_text="Optional description of this data point")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['crane', 'incoming_field_name']
        verbose_name = "Data Point Mapping"
        verbose_name_plural = "Data Point Mappings"
    
    def __str__(self):
        return f"{self.crane.crane_name}: {self.incoming_field_name} → {self.mapped_field_name}"