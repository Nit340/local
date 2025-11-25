from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from django.http import HttpResponseRedirect
from django.contrib import messages
from .models import (
    Crane, IoTGateway, CraneGatewayMapping, CraneMotorMeasurement,
    CraneIOStatus, CraneLoadcellMeasurement, CraneAlarm, CraneConfiguration,
    CraneHourlyKPIs, CraneDailyKPIs, MQTTMessageLog  ,DataPointMapping
)

@admin.register(Crane)
class CraneAdmin(admin.ModelAdmin):
    list_display = [
        'crane_name', 'crane_type', 'capacity_tonnes', 'location', 
        'status', 'is_active', 'device_count', 'last_updated'
    ]
    list_filter = ['status', 'is_active', 'crane_type', 'location']
    search_fields = ['crane_name', 'location']
    readonly_fields = ['created_at', 'updated_at']
    
    def device_count(self, obj):
        return len(obj.device_ids) if obj.device_ids else 0
    device_count.short_description = 'Devices'
    
    def last_updated(self, obj):
        return obj.updated_at.strftime('%Y-%m-%d %H:%M:%S')
    last_updated.short_description = 'Last Updated'

@admin.register(IoTGateway)
class IoTGatewayAdmin(admin.ModelAdmin):
    list_display = [
        'gateway_name', 'gateway_type', 'ip_address', 'status', 
        'last_heartbeat', 'crane_count', 'is_online'
    ]
    list_filter = ['status', 'gateway_type']
    
    def crane_count(self, obj):
        return obj.cranegatewaymapping_set.filter(is_active=True).count()
    crane_count.short_description = 'Active Cranes'
    
    def is_online(self, obj):
        if obj.last_heartbeat:
            time_diff = timezone.now() - obj.last_heartbeat
            if time_diff.total_seconds() < 300:
                return format_html('<span style="color: green;">● Online</span>')
        return format_html('<span style="color: red;">● Offline</span>')
    is_online.short_description = 'Connection Status'

@admin.register(CraneGatewayMapping)
class CraneGatewayMappingAdmin(admin.ModelAdmin):
    list_display = ['crane', 'gateway', 'mqtt_topic', 'is_active', 'created_at']
    list_filter = ['is_active', 'gateway', 'crane']

@admin.register(CraneMotorMeasurement)
class CraneMotorMeasurementAdmin(admin.ModelAdmin):
    list_display = [
        'crane', 'timestamp', 'total_power', 'total_current'
    ]
    list_filter = ['crane', 'timestamp']
    date_hierarchy = 'timestamp'

@admin.register(CraneIOStatus)
class CraneIOStatusAdmin(admin.ModelAdmin):
    list_display = [
        'crane', 'timestamp', 'active_operations', 'start', 'stop'
    ]
    list_filter = ['crane', 'timestamp']
    date_hierarchy = 'timestamp'
    
    def active_operations(self, obj):
        operations = []
        if obj.hoist_up: operations.append('Hoist Up')
        if obj.hoist_down: operations.append('Hoist Down')
        if obj.ct_left: operations.append('CT Left')
        if obj.ct_right: operations.append('CT Right')
        if obj.lt_forward: operations.append('LT Forward')
        if obj.lt_reverse: operations.append('LT Reverse')
        return ', '.join(operations) if operations else 'Idle'
    active_operations.short_description = 'Active Operations'

@admin.register(CraneLoadcellMeasurement)
class CraneLoadcellMeasurementAdmin(admin.ModelAdmin):
    list_display = [
        'crane', 'timestamp', 'load', 'capacity', 'load_percentage', 
        'status_display'
    ]
    list_filter = ['crane', 'status', 'timestamp']
    date_hierarchy = 'timestamp'
    
    def status_display(self, obj):
        color_map = {
            'normal': 'green',
            'warning': 'orange',
            'overload': 'red'
        }
        color = color_map.get(obj.status, 'black')
        return format_html('<span style="color: {};">{}</span>', color, obj.status.title())
    status_display.short_description = 'Status'

@admin.register(CraneAlarm)
class CraneAlarmAdmin(admin.ModelAdmin):
    list_display = [
        'crane', 'timestamp', 'alarm_severity_display', 'alarm_message_short',
        'is_acknowledged', 'alarm_count'
    ]
    list_filter = ['alarm_severity', 'is_acknowledged', 'crane', 'timestamp']
    date_hierarchy = 'timestamp'
    
    def alarm_severity_display(self, obj):
        color_map = {
            'low': 'blue',
            'medium': 'orange',
            'high': 'red',
            'critical': 'darkred'
        }
        color = color_map.get(obj.alarm_severity, 'black')
        return format_html('<span style="color: {}; font-weight: bold;">{}</span>', color, obj.alarm_severity.title())
    alarm_severity_display.short_description = 'Severity'
    
    def alarm_message_short(self, obj):
        return obj.alarm_message[:50] + '...' if len(obj.alarm_message) > 50 else obj.alarm_message
    alarm_message_short.short_description = 'Message'
    
    def alarm_count(self, obj):
        count = 0
        if obj.alarm_one: count += 1
        if obj.alarm_two: count += 1
        if obj.alarm_three: count += 1
        return count
    alarm_count.short_description = 'Active Alarms'

@admin.register(CraneConfiguration)
class CraneConfigurationAdmin(admin.ModelAdmin):
    list_display = [
        'crane', 'tariff_rate', 'currency', 'target_energy_per_ton',
        'max_load_capacity', 'warning_threshold', 'overload_threshold'
    ]
    list_filter = ['currency']

@admin.register(CraneHourlyKPIs)
class CraneHourlyKPIsAdmin(admin.ModelAdmin):
    list_display = [
        'crane', 'hour_start', 'total_lifts', 'total_mass_moved_tonnes',
        'total_energy_kwh', 'hourly_energy_cost', 'oee'
    ]
    list_filter = ['crane', 'hour_start']
    date_hierarchy = 'hour_start'

@admin.register(CraneDailyKPIs)
class CraneDailyKPIsAdmin(admin.ModelAdmin):
    list_display = [
        'crane', 'date', 'shift', 'total_lifts', 'total_mass_moved_tonnes',
        'total_energy_kwh', 'total_energy_cost', 'oee'
    ]
    list_filter = ['crane', 'date', 'shift']
    date_hierarchy = 'date'

@admin.register(MQTTMessageLog)
class MQTTMessageLogAdmin(admin.ModelAdmin):
    list_display = [
        'topic', 'crane', 'gateway', 'message_type', 'timestamp'
    ]
    list_filter = ['message_type', 'topic', 'timestamp']
    date_hierarchy = 'timestamp'

@admin.register(DataPointMapping)
class DataPointMappingAdmin(admin.ModelAdmin):
    list_display = [
        'crane', 'incoming_field_name', 'mapped_field_name', 
        'field_type', 'is_active', 'created_at'
    ]
    list_filter = ['crane', 'field_type', 'is_active', 'created_at']
    search_fields = ['incoming_field_name', 'mapped_field_name', 'crane__crane_name']
    list_editable = ['is_active']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('crane', 'is_active')
        }),
        ('Field Mapping', {
            'fields': ('incoming_field_name', 'mapped_field_name', 'field_type')
        }),
        ('Additional Information', {
            'fields': ('description',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_readonly_fields(self, request, obj=None):
        if obj:  # editing an existing object
            return self.readonly_fields + ('crane', 'incoming_field_name')
        return self.readonly_fields