from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, viewsets
from django.db.models import Q

from .models import DNCSettings, DNCRegistry, DNCOverrideLog
from .serializers import (
    DNCSettingsSerializer,
    DNCRegistrySerializer,
    DNCOverrideLogSerializer
)

from .services import evaluate_dnc

from apps.customers.models import Customer
import csv
import io


# =====================================================
# 1. SETTINGS API
# =====================================================
class DNCSettingsView(APIView):
    def get(self, request):
        settings = DNCSettings.get_settings()
        serializer = DNCSettingsSerializer(settings)
        return Response(serializer.data)

    def post(self, request):
        settings = DNCSettings.get_settings()
        serializer = DNCSettingsSerializer(settings, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request):
        settings = DNCSettings.get_settings()
        serializer = DNCSettingsSerializer(settings, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# =====================================================
# 2. REGISTRY LIST & CREATE (STRICT VALIDATION)
# =====================================================
class DNCRegistryViewSet(viewsets.ModelViewSet):
    queryset = DNCRegistry.objects.all().order_by('-created_at')
    serializer_class = DNCRegistrySerializer

    def get_queryset(self):
        queryset = DNCRegistry.objects.all().order_by('-created_at')

        status_param = self.request.query_params.get('status')
        type_param = self.request.query_params.get('type')
        source_param = self.request.query_params.get('source')
        search_param = self.request.query_params.get('search')
        phone_param = self.request.query_params.get('phone')

        if status_param and status_param != 'All':
            queryset = queryset.filter(status__iexact=status_param)

        if type_param and type_param != 'All':
            if type_param == 'Phone':
                queryset = queryset.filter(dnc_type='Phone Only')
            elif type_param == 'Email':
                queryset = queryset.filter(dnc_type='Email Only')
            elif type_param == 'Both':
                queryset = queryset.filter(dnc_type='Both Phone & Email')

        if source_param and source_param != 'All':
            source_map = {
                'Government': 'Government Registry',
                'Customer': 'Customer Request',
                'Manual': 'Manual Entry',
                'System': 'System Generated'
            }
            queryset = queryset.filter(
                source__iexact=source_map.get(source_param, source_param)
            )

        if phone_param:
            queryset = queryset.filter(phone_number=phone_param)

        if search_param:
            queryset = queryset.filter(
                Q(customer_name__icontains=search_param) |
                Q(phone_number__icontains=search_param) |
                Q(email_address__icontains=search_param)
            )

        return queryset

    def create(self, request, *args, **kwargs):
        full_name = (request.data.get('name') or '').strip()
        phone = (request.data.get('phone') or '').strip()
        email = (request.data.get('email') or '').strip()

        if not full_name:
            return Response({"error": "Customer name is required"}, status=400)

        if not phone or not email:
            return Response({"error": "Phone and Email are required"}, status=400)

        customer = Customer.objects.filter(phone=phone, email=email).first()

        if not customer:
            return Response(
                {"error": "No customer found with the given phone and email"},
                status=400
            )

        db_name = f"{customer.first_name} {customer.last_name}".strip().lower()
        input_name = " ".join(full_name.split()).lower()

        if db_name != input_name:
            return Response(
                {"error": "Customer name does not match phone/email"},
                status=400
            )

        payload = {
            "customer": customer.id,
            "customer_name": f"{customer.first_name} {customer.last_name}",
            "phone_number": customer.phone,
            "email_address": customer.email,
            "dnc_type": request.data.get("dnc_type"),
            "source": request.data.get("source"),
            "status": request.data.get("status", "Active"),
            "allow_override_requests": request.data.get("allow_override_requests", False),
            "reason": request.data.get("reason"),
        }

        serializer = self.get_serializer(data=payload)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data, status=status.HTTP_201_CREATED)


# =====================================================
# 3. OVERRIDE API (GLOBAL + ENTRY LEVEL ENFORCED)
# =====================================================
class DNCOverrideView(APIView):
    def get(self, request):
        logs = DNCOverrideLog.objects.all().order_by('-created_at')
        serializer = DNCOverrideLogSerializer(logs, many=True)
        return Response(serializer.data)

    def post(self, request):
        if not request.user.is_authenticated:
            return Response(
                {"error": "Authentication required"},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # ✅ FIX: fail-safe ID handling
        entry_id = request.data.get('dnc_entry_id') or request.data.get('entry_id')
        override_type = request.data.get('override_type')
        reason = request.data.get('reason')
        end_date = request.data.get('end_date')

        try:
            dnc_entry = DNCRegistry.objects.get(id=entry_id)

            settings = DNCSettings.get_settings()

            # ✅ FIX: correct settings field
            if not settings.allow_overrides:
                return Response(
                    {"error": "DNC override is disabled globally"},
                    status=status.HTTP_403_FORBIDDEN
                )

            if not dnc_entry.allow_override_requests:
                return Response(
                    {"error": "Override not allowed for this DNC entry"},
                    status=status.HTTP_403_FORBIDDEN
                )

            authorized_by = (
                request.user.username
                or request.user.email
                or str(request.user.id)
                or "System User"
            )

            DNCOverrideLog.objects.create(
                dnc_entry=dnc_entry,
                override_type=override_type,
                reason=reason,
                end_date=end_date if override_type == 'Temporary Override' else None,
                authorized_by=authorized_by
            )

            if override_type == 'Permanent Override':
                dnc_entry.status = 'Inactive'
                dnc_entry.save()

            return Response(
                {"status": "success", "authorized_by": authorized_by},
                status=status.HTTP_200_OK
            )

        except DNCRegistry.DoesNotExist:
            return Response({"error": "Entry not found"}, status=404)


# =====================================================
# 4. DNC EVALUATION API
# =====================================================
class DNCEvaluateView(APIView):
    def post(self, request):
        phone_number = request.data.get("phone_number")
        request_override = request.data.get("request_override", False)
        reason = request.data.get("reason")

        if not phone_number:
            return Response(
                {"error": "phone_number is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        result = evaluate_dnc(
            phone_number=phone_number,
            user=request.user if request.user.is_authenticated else None,
            request_override=request_override,
            source="dnc-api",
            reason=reason,
        )

        return Response(result, status=status.HTTP_200_OK)


# =====================================================
# 5. STATISTICS API
# =====================================================
class DNCStatisticsView(APIView):
    def get(self, request):
        return Response({
            "active_entries": DNCRegistry.objects.filter(status='Active').count(),
            "phone_entries": DNCRegistry.objects.filter(dnc_type__icontains='Phone', status='Active').count(),
            "email_entries": DNCRegistry.objects.filter(dnc_type__icontains='Email', status='Active').count(),
            "gov_entries": DNCRegistry.objects.filter(source='Government Registry').count(),
        })


# =====================================================
# 6. BULK UPLOAD API
# =====================================================
class BulkUploadView(APIView):
    def post(self, request):
        file = request.FILES.get('file')
        if not file:
            return Response({'error': 'No file provided'}, status=400)

        reader = csv.DictReader(io.StringIO(file.read().decode('utf-8')))
        count = 0

        for row in reader:
            phone = row.get('Phone', '').strip()
            email = row.get('Email', '').strip()

            customer = Customer.objects.filter(phone=phone, email=email).first()
            if not customer:
                continue

            DNCRegistry.objects.create(
                customer=customer,
                customer_name=f"{customer.first_name} {customer.last_name}",
                phone_number=customer.phone,
                email_address=customer.email,
                dnc_type=row.get('DNC Type', 'Phone Only'),
                source=row.get('Source', 'Manual Entry'),
                reason=row.get('Reason', 'Bulk Upload'),
                status='Active'
            )
            count += 1

        return Response({
            'status': 'success',
            'message': f'{count} records uploaded and verified'
        })
