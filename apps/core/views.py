"""
Core views for system health checks, utilities, and error handling.
"""

import os
import sys
import django
import psutil
from datetime import datetime
from django.http import JsonResponse, HttpResponse
from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework import status
from drf_spectacular.utils import extend_schema
from .models import SystemConfiguration, AuditLog


@api_view(['GET'])
@permission_classes([])
def health_check(request):
    """
    Simple health check endpoint for load balancers and monitoring.
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        
        cache.set('health_check', 'ok', 10)
        cache_status = cache.get('health_check') == 'ok'
        
        if cache_status:
            return JsonResponse({
                'status': 'healthy',
                'timestamp': datetime.now().isoformat(),
                'version': getattr(settings, 'APP_VERSION', '1.0.0')
            })
        else:
            return JsonResponse({
                'status': 'unhealthy',
                'error': 'Cache not working'
            }, status=503)
            
    except Exception as e:
        return JsonResponse({
            'status': 'unhealthy',
            'error': str(e)
        }, status=503)


@api_view(['GET'])
@permission_classes([IsAdminUser])
@extend_schema(
    summary="Detailed Health Check",
    description="Comprehensive system health check with detailed metrics",
    tags=["System"]
)
def detailed_health_check(request):
    """
    Detailed health check with system metrics.
    """
    try:
        health_data = {
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'version': getattr(settings, 'APP_VERSION', '1.0.0'),
            'checks': {}
        }
        
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) FROM django_session")
                session_count = cursor.fetchone()[0]
            health_data['checks']['database'] = {
                'status': 'ok',
                'active_sessions': session_count
            }
        except Exception as e:
            health_data['checks']['database'] = {
                'status': 'error',
                'error': str(e)
            }
            health_data['status'] = 'unhealthy'
        
        # Cache check
        try:
            test_key = 'health_check_detailed'
            cache.set(test_key, 'test_value', 10)
            cache_value = cache.get(test_key)
            health_data['checks']['cache'] = {
                'status': 'ok' if cache_value == 'test_value' else 'error'
            }
        except Exception as e:
            health_data['checks']['cache'] = {
                'status': 'error',
                'error': str(e)
            }
            health_data['status'] = 'unhealthy'
        
        # System metrics
        try:
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            health_data['system'] = {
                'cpu_percent': psutil.cpu_percent(interval=1),
                'memory_percent': memory.percent,
                'disk_percent': disk.percent,
                'load_average': os.getloadavg() if hasattr(os, 'getloadavg') else None
            }
        except Exception as e:
            health_data['system'] = {'error': str(e)}
        
        # Django info
        health_data['django'] = {
            'version': django.get_version(),
            'debug': settings.DEBUG,
            'python_version': sys.version
        }
        
        return Response(health_data)
        
    except Exception as e:
        return Response({
            'status': 'unhealthy',
            'error': str(e)
        }, status=503)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def system_info(request):
    """
    Get system information and configuration.
    """
    try:
        info = {
            'application': {
                'name': 'Intelipro Insurance Policy Renewal System',
                'version': getattr(settings, 'APP_VERSION', '1.0.0'),
                'environment': getattr(settings, 'ENVIRONMENT', 'development'),
                'debug': settings.DEBUG,
            },
            'django': {
                'version': django.get_version(),
                'installed_apps': len(settings.INSTALLED_APPS),
                'middleware': len(settings.MIDDLEWARE),
            },
            'python': {
                'version': sys.version,
                'executable': sys.executable,
            },
            'database': {
                'engine': settings.DATABASES['default']['ENGINE'],
                'name': settings.DATABASES['default']['NAME'],
                'host': settings.DATABASES['default'].get('HOST', 'localhost'),
            },
            'cache': {
                'backend': settings.CACHES['default']['BACKEND'],
                'location': settings.CACHES['default'].get('LOCATION', 'N/A'),
            }
        }
        
        return Response(info)
        
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=500)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def system_status(request):
    """
    Get current system status and metrics.
    """
    try:
        # System metrics
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        status_data = {
            'timestamp': datetime.now().isoformat(),
            'uptime': datetime.now() - datetime.fromtimestamp(psutil.boot_time()),
            'cpu': {
                'percent': psutil.cpu_percent(interval=1),
                'count': psutil.cpu_count(),
                'load_average': os.getloadavg() if hasattr(os, 'getloadavg') else None
            },
            'memory': {
                'total': memory.total,
                'available': memory.available,
                'percent': memory.percent,
                'used': memory.used
            },
            'disk': {
                'total': disk.total,
                'used': disk.used,
                'free': disk.free,
                'percent': disk.percent
            },
            'processes': len(psutil.pids())
        }
        
        # Database stats
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) FROM django_session WHERE expire_date > NOW()")
                active_sessions = cursor.fetchone()[0]
                status_data['database'] = {
                    'active_sessions': active_sessions,
                    'connection_status': 'connected'
                }
        except Exception as e:
            status_data['database'] = {
                'connection_status': 'error',
                'error': str(e)
            }
        
        return Response(status_data)
        
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=500)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def system_config(request):
    """
    Get system configuration settings.
    """
    try:
        configs = SystemConfiguration.objects.filter(is_active=True)
        config_data = {}
        
        for config in configs:
            if config.category not in config_data:
                config_data[config.category] = {}
            config_data[config.category][config.key] = {
                'value': config.value,
                'description': config.description
            }
        
        return Response(config_data)
        
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=500)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def system_config_by_category(request, category):
    """
    Get system configuration for a specific category.
    """
    try:
        configs = SystemConfiguration.objects.filter(
            category=category,
            is_active=True
        )
        
        config_data = {}
        for config in configs:
            config_data[config.key] = {
                'value': config.value,
                'description': config.description
            }
        
        return Response({
            'category': category,
            'configs': config_data
        })
        
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def audit_logs(request):
    """
    Get audit logs with filtering and pagination.
    """
    try:
        logs = AuditLog.objects.all()
        
        # Filter by user
        user_id = request.GET.get('user_id')
        if user_id:
            logs = logs.filter(user_id=user_id)
        
        # Filter by action
        action = request.GET.get('action')
        if action:
            logs = logs.filter(action=action)
        
        # Filter by model
        model_name = request.GET.get('model')
        if model_name:
            logs = logs.filter(model_name=model_name)
        
        # Date range filtering
        date_from = request.GET.get('date_from')
        date_to = request.GET.get('date_to')
        if date_from:
            logs = logs.filter(created_at__gte=date_from)
        if date_to:
            logs = logs.filter(created_at__lte=date_to)
        
        # Pagination
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 20))
        offset = (page - 1) * page_size
        
        total_count = logs.count()
        logs = logs[offset:offset + page_size]
        
        log_data = []
        for log in logs:
            log_data.append({
                'id': log.id,
                'user': log.user.email if log.user else None,
                'action': log.action,
                'model_name': log.model_name,
                'object_id': log.object_id,
                'object_repr': log.object_repr,
                'changes': log.changes,
                'ip_address': log.ip_address,
                'created_at': log.created_at.isoformat()
            })
        
        return Response({
            'count': total_count,
            'page': page,
            'page_size': page_size,
            'results': log_data
        })
        
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=500)


# Error handlers
def bad_request(request, exception):
    """400 Bad Request handler"""
    return JsonResponse({
        'error': 'Bad Request',
        'message': 'The request could not be understood by the server.'
    }, status=400)


def permission_denied(request, exception):
    """403 Permission Denied handler"""
    return JsonResponse({
        'error': 'Permission Denied',
        'message': 'You do not have permission to access this resource.'
    }, status=403)


def page_not_found(request, exception):
    """404 Not Found handler"""
    return JsonResponse({
        'error': 'Not Found',
        'message': 'The requested resource was not found.'
    }, status=404)


def server_error(request):
    """500 Server Error handler"""
    return JsonResponse({
        'error': 'Internal Server Error',
        'message': 'An unexpected error occurred. Please try again later.'
    }, status=500) 