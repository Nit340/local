from rest_framework import serializers
from .models import (
    Crane, CraneMotorMeasurement, CraneIOStatus,
    CraneLoadcellMeasurement, CraneAlarm, CraneConfiguration,
    IoTGateway, CraneGatewayMapping
)

class CraneSerializer(serializers.ModelSerializer):
    class Meta:
        model = Crane
        fields = '__all__'

class CraneMotorMeasurementSerializer(serializers.ModelSerializer):
    crane_name = serializers.CharField(source='crane.crane_name', read_only=True)
    
    class Meta:
        model = CraneMotorMeasurement
        fields = '__all__'

class CraneIOStatusSerializer(serializers.ModelSerializer):
    crane_name = serializers.CharField(source='crane.crane_name', read_only=True)
    
    class Meta:
        model = CraneIOStatus
        fields = '__all__'

class CraneLoadcellMeasurementSerializer(serializers.ModelSerializer):
    crane_name = serializers.CharField(source='crane.crane_name', read_only=True)
    
    class Meta:
        model = CraneLoadcellMeasurement
        fields = '__all__'

class CraneAlarmSerializer(serializers.ModelSerializer):
    crane_name = serializers.CharField(source='crane.crane_name', read_only=True)
    
    class Meta:
        model = CraneAlarm
        fields = '__all__'

class CraneConfigurationSerializer(serializers.ModelSerializer):
    crane_name = serializers.CharField(source='crane.crane_name', read_only=True)
    
    class Meta:
        model = CraneConfiguration
        fields = '__all__'

class IoTGatewaySerializer(serializers.ModelSerializer):
    class Meta:
        model = IoTGateway
        fields = '__all__'

class CraneGatewayMappingSerializer(serializers.ModelSerializer):
    crane_name = serializers.CharField(source='crane.crane_name', read_only=True)
    gateway_name = serializers.CharField(source='gateway.gateway_name', read_only=True)
    
    class Meta:
        model = CraneGatewayMapping
        fields = '__all__'