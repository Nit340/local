from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from datetime import datetime, timedelta
from django.db.models import Q
from .models import CraneMotorMeasurement, CraneIOStatus, CraneLoadcellMeasurement, CraneAlarm
from .serializers import (
    CraneMotorMeasurementSerializer, CraneIOStatusSerializer,
    CraneLoadcellMeasurementSerializer, CraneAlarmSerializer
)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def data_export(request):
    """
    Export crane data in various formats
    """
    data_type = request.GET.get('type', 'motor')
    crane_id = request.GET.get('crane_id')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    format_type = request.GET.get('format', 'json')
    
    # Build filters
    filters = Q()
    if crane_id:
        filters &= Q(crane_id=crane_id)
    if start_date:
        start_dt = datetime.fromisoformat(start_date)
        filters &= Q(timestamp__gte=start_dt)
    if end_date:
        end_dt = datetime.fromisoformat(end_date)
        filters &= Q(timestamp__lte=end_dt)
    
    # Get data based on type
    if data_type == 'motor':
        queryset = CraneMotorMeasurement.objects.filter(filters).order_by('-timestamp')
        serializer_class = CraneMotorMeasurementSerializer
    elif data_type == 'io':
        queryset = CraneIOStatus.objects.filter(filters).order_by('-timestamp')
        serializer_class = CraneIOStatusSerializer
    elif data_type == 'load':
        queryset = CraneLoadcellMeasurement.objects.filter(filters).order_by('-timestamp')
        serializer_class = CraneLoadcellMeasurementSerializer
    elif data_type == 'alarms':
        queryset = CraneAlarm.objects.filter(filters).order_by('-timestamp')
        serializer_class = CraneAlarmSerializer
    else:
        return Response({'error': 'Invalid data type'}, status=status.HTTP_400_BAD_REQUEST)
    
    # Apply limit
    limit = int(request.GET.get('limit', 1000))
    queryset = queryset[:limit]
    
    # Serialize data
    serializer = serializer_class(queryset, many=True)
    
    if format_type == 'csv':
        # Generate CSV response
        import csv
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{data_type}_data_{timezone.now().date()}.csv"'
        
        if serializer.data:
            writer = csv.writer(response)
            # Write header
            writer.writerow(serializer.data[0].keys())
            # Write data
            for row in serializer.data:
                writer.writerow(row.values())
        
        return response
    
    else:  # JSON format
        return Response({
            'metadata': {
                'type': data_type,
                'count': len(serializer.data),
                'exported_at': timezone.now().isoformat(),
                'filters': {
                    'crane_id': crane_id,
                    'start_date': start_date,
                    'end_date': end_date
                }
            },
            'data': serializer.data
        })

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def data_cleanup(request):
    """
    Clean up old data based on retention policy
    """
    try:
        data_type = request.data.get('type', 'all')
        retention_days = int(request.data.get('retention_days', 30))
        
        cutoff_date = timezone.now() - timedelta(days=retention_days)
        deleted_count = 0
        
        if data_type in ['motor', 'all']:
            count, _ = CraneMotorMeasurement.objects.filter(timestamp__lt=cutoff_date).delete()
            deleted_count += count
        
        if data_type in ['io', 'all']:
            count, _ = CraneIOStatus.objects.filter(timestamp__lt=cutoff_date).delete()
            deleted_count += count
        
        if data_type in ['load', 'all']:
            count, _ = CraneLoadcellMeasurement.objects.filter(timestamp__lt=cutoff_date).delete()
            deleted_count += count
        
        if data_type in ['alarms', 'all']:
            count, _ = CraneAlarm.objects.filter(
                timestamp__lt=cutoff_date,
                is_acknowledged=True
            ).delete()
            deleted_count += count
        
        return Response({
            'message': f'Successfully deleted {deleted_count} records older than {retention_days} days',
            'deleted_count': deleted_count,
            'cutoff_date': cutoff_date.isoformat()
        })
        
    except Exception as e:
        return Response(
            {'error': f'Error during data cleanup: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def system_health(request):
    """
    Get system health and data statistics
    """
    try:
        # Data statistics
        total_motor_records = CraneMotorMeasurement.objects.count()
        total_io_records = CraneIOStatus.objects.count()
        total_load_records = CraneLoadcellMeasurement.objects.count()
        total_alarm_records = CraneAlarm.objects.count()
        
        # Recent data check
        recent_threshold = timezone.now() - timedelta(minutes=5)
        recent_motor_data = CraneMotorMeasurement.objects.filter(
            timestamp__gte=recent_threshold
        ).exists()
        
        # Active alarms
        active_alarms = CraneAlarm.objects.filter(is_acknowledged=False).count()
        
        # Crane status
        active_cranes = Crane.objects.filter(is_active=True).count()
        working_cranes = Crane.objects.filter(status='working').count()
        
        # Database size estimation (SQLite specific)
        import sqlite3
        from django.conf import settings
        db_path = settings.DATABASES['default']['NAME']
        
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()")
            db_size = cursor.fetchone()[0]
        
        return Response({
            'data_statistics': {
                'motor_measurements': total_motor_records,
                'io_status': total_io_records,
                'load_measurements': total_load_records,
                'alarms': total_alarm_records,
                'total_records': total_motor_records + total_io_records + total_load_records + total_alarm_records
            },
            'system_status': {
                'recent_data_flow': recent_motor_data,
                'active_alarms': active_alarms,
                'active_cranes': active_cranes,
                'working_cranes': working_cranes,
                'database_size_mb': round(db_size / (1024 * 1024), 2)
            },
            'timestamp': timezone.now().isoformat()
        })
        
    except Exception as e:
        return Response(
            {'error': f'Error checking system health: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )