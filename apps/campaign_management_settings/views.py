import csv
import json
from django.http import HttpResponse
from django.db.models import Count, Q
from openpyxl import Workbook
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework import generics, status
from rest_framework.response import Response

from .models import CampaignSetting
from .serializers import (
    CampaignSettingSerializer, 
    EmailOptionSerializer, 
    SMSOptionSerializer, 
    WhatsAppOptionSerializer
)

from apps.email_provider.models import EmailProviderConfig
from apps.sms_provider.models import SmsProvider
from apps.whatsapp_provider.models import WhatsAppProvider
from apps.sms_provider.models import SmsMessage 
from apps.whatsapp_provider.models import WhatsAppMessage

class ProviderOptionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        email_opts = EmailProviderConfig.objects.all() 
        sms_opts = SmsProvider.objects.all()
        wa_opts = WhatsAppProvider.objects.all()

        return Response({
            "email_providers": EmailOptionSerializer(email_opts, many=True).data,
            "sms_providers": SMSOptionSerializer(sms_opts, many=True).data,
            "whatsapp_providers": WhatsAppOptionSerializer(wa_opts, many=True).data
        })
class CampaignSettingsView(generics.RetrieveUpdateAPIView):
    serializer_class = CampaignSettingSerializer
    permission_classes = [IsAuthenticated]
    queryset = CampaignSetting.objects.all()

    def get_object(self):
        obj, created = CampaignSetting.objects.get_or_create(user=self.request.user)
        return obj

    def delete(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete() 
        new_settings = CampaignSetting.objects.create(user=request.user)
        serializer = self.get_serializer(new_settings)
        return Response(serializer.data, status=status.HTTP_200_OK)
class DownloadReportView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_sms_report_data(self,request):
        sms_stats = SmsMessage.objects.filter(provider__created_by=request.user).values('campaign__name').annotate(
            total=Count('id'),
            delivered=Count('id', filter=Q(status='delivered')),
            failed=Count('id', filter=Q(status='failed')),
            sent=Count('id', filter=Q(status='sent'))
        )

        report_data = []
        for item in sms_stats:
            report_data.append({
                "campaign_name": item['campaign__name'] or "Ad-hoc / System Message",
                "channel": "SMS",
                "total_sent": item['total'],
                "delivered": item['delivered'],
                "failed": item['failed'],
                "engagement": "N/A",  
                "status": "Completed"
            })
        return report_data

    def _get_whatsapp_report_data(self,request):
        wa_stats = WhatsAppMessage.objects.filter(
        provider__created_by=request.user).values('campaign__name').annotate(
        total=Count('id'),
        delivered=Count('id', filter=Q(status='delivered')),
        read=Count('id', filter=Q(status='read')),
        failed=Count('id', filter=Q(status='failed'))
    )

        report_data = []
        for item in wa_stats:
            report_data.append({
                "campaign_name": item['campaign__name'] or "Ad-hoc / System Message",
                "channel": "WhatsApp",
                "total_sent": item['total'],
                "delivered": item['delivered'],
                "failed": item['failed'],
                "engagement": item['read'],
                "status": "Completed"
            })
        return report_data

    def get(self, request):
        try:
            settings = CampaignSetting.objects.get(user=request.user)
            export_format = settings.export_format
        except CampaignSetting.DoesNotExist:
            return Response(
                {"error": "Campaign settings not found for this user."},
                status=status.HTTP_404_NOT_FOUND
            )
        report_data = self._get_sms_report_data(request) + self._get_whatsapp_report_data(request)

        if not report_data:
            return Response(
                {"message": "No campaign data found to export."},
                status=status.HTTP_404_NOT_FOUND
            )

        headers = ["campaign_name", "channel", "total_sent", "delivered", "failed", "engagement", "status"]

        if export_format == 'JSON':
            response = HttpResponse(
                json.dumps(report_data, indent=4, default=str),
                content_type='application/json'
            )
            response['Content-Disposition'] = 'attachment; filename="campaign_report.json"'
            return response

        elif export_format == 'CSV':
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename="campaign_report.csv"'

            writer = csv.writer(response)
            writer.writerow(headers)
            for row in report_data:
                writer.writerow([row.get(header, "") for header in headers])
            return response

        elif export_format == 'XLSX':
            response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            response['Content-Disposition'] = 'attachment; filename="campaign_report.xlsx"'

            wb = Workbook()
            ws = wb.active
            ws.title = "Campaign Performance"

            ws.append(headers)

            for row in report_data:
                ws.append([row.get(header, "") for header in headers])

            wb.save(response)
            return response

        return Response(
            {"error": "Invalid export format specified in settings."},
            status=status.HTTP_400_BAD_REQUEST
        )