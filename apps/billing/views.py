from rest_framework import viewsets
from django.http import HttpResponse
from io import BytesIO
from django.utils.dateparse import parse_date
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Count, Q,Sum,Max
from django.db.models.functions import TruncDate
from .models import BillingPeriod, Invoice,CommunicationLog, Vendor, Campaign, UsageCharge, PlatformCharge
from .serializers import BillingDashboardSerializer, InvoiceSerializer,VendorCardSerializer,VendorTableSerializer,CommunicationLogSerializer,DeliveryStatusSerializer,CampaignSerializer

def create_pdf_response(filename, elements):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4))
    doc.build(elements)
    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}.pdf"'
    return response

def get_header_style():
    return TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0f172a')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ])

class BillingViewSet(viewsets.ViewSet):
    
    @action(detail=False, methods=['get'])
    def dashboard(self, request):
        # 1. Capture inputs from the frontend dropdowns
        month = request.query_params.get('month')
        year = request.query_params.get('year')
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        usage_charges = []
        platform_charges = []
        invoices = Invoice.objects.all()
        if start_date and end_date:
            s_date = parse_date(start_date)
            e_date = parse_date(end_date)
            invoices = invoices.filter(date__range=[s_date, e_date])
            if s_date:
                period = BillingPeriod.objects.filter(month=s_date.month, year=s_date.year).first()
                if period:
                    usage_charges = period.usage_charges.all()
                    platform_charges = period.platform_charges.all()

        elif month and year:
            invoices = invoices.filter(date__month=month, date__year=year)
            period = BillingPeriod.objects.filter(month=month, year=year).first()
            if period:
                usage_charges = period.usage_charges.all()
                platform_charges = period.platform_charges.all()

        # 4. Calculate Totals
        usage_total = sum(u.total_cost for u in usage_charges)
        platform_total = sum(p.cost for p in platform_charges)
        grand_total = usage_total + platform_total

        data = {
            "period": f"{month}/{year}" if month else "Custom Range",
            "portal_usage_utilization_charges": usage_charges,
            "platform_charges": platform_charges,
            "invoices": invoices.order_by('-date')[:5], 
            "total_usage_cost": usage_total,
            "total_platform_cost": platform_total,
            "grand_total": grand_total
        }
        
        serializer = BillingDashboardSerializer(data)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def download_pdf(self, request):
        # 1. Get Filters
        month = request.query_params.get('month', 12)
        year = request.query_params.get('year', 2025)
        
        # 2. Fetch Data
        period, _ = BillingPeriod.objects.get_or_create(month=month, year=year)
        usage = period.usage_charges.all()
        platform = period.platform_charges.all()
        invoices = Invoice.objects.filter(date__month=month, date__year=year)

        # 3. Build PDF Elements
        elements = []
        styles = getSampleStyleSheet()
        elements.append(Paragraph(f"Billing Statement - {month}/{year}", styles['Title']))
        elements.append(Spacer(1, 20))

        # --- Table 1: Usage Charges ---
        elements.append(Paragraph("Usage Charges", styles['Heading2']))
        data1 = [['Service', 'Count', 'Cost']]
        for u in usage:
            data1.append([u.get_service_name_display(), str(u.count), f"{u.total_cost}"])
        
        t1 = Table(data1, colWidths=[200, 100, 100])
        t1.setStyle(get_header_style())
        elements.append(t1)
        elements.append(Spacer(1, 20))

        # --- Table 2: Platform Charges ---
        elements.append(Paragraph("Platform Charges", styles['Heading2']))
        data2 = [['Service', 'Period', 'Cost']]
        for p in platform:
            data2.append([p.name, p.billing_cycle, f"{p.cost}"])
        
        t2 = Table(data2, colWidths=[200, 100, 100])
        t2.setStyle(get_header_style())
        elements.append(t2)
        elements.append(Spacer(1, 20))

        elements.append(Paragraph("Invoices", styles['Heading2']))
        data3 = [['Invoice #', 'Date', 'Amount', 'Status']]
        for inv in invoices:
            data3.append([inv.invoice_number, str(inv.date), f"{inv.amount}", inv.status.title()])
        
        t3 = Table(data3, colWidths=[150, 100, 100, 100])
        t3.setStyle(get_header_style())
        elements.append(t3)

        return create_pdf_response(f"Billing_Statement_{month}_{year}", elements)

class InvoiceViewSet(viewsets.ModelViewSet):
    queryset = Invoice.objects.all()
    serializer_class = InvoiceSerializer
class CommunicationStatsViewSet(viewsets.ViewSet):
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        start_date_str = request.query_params.get('start_date')
        end_date_str = request.query_params.get('end_date')
        logs = CommunicationLog.objects.all()
        if start_date_str and end_date_str:
            start_date = parse_date(start_date_str)
            end_date = parse_date(end_date_str)
            if start_date and end_date:
                logs = logs.filter(timestamp__date__range=[start_date, end_date])

        totals = logs.aggregate(
            sms=Count('id', filter=Q(type='sms')),
            email=Count('id', filter=Q(type='email')),
            whatsapp=Count('id', filter=Q(type='whatsapp'))
        )

        daily_stats = (
            logs.annotate(date=TruncDate('timestamp'))
            .values('date')
            .annotate(
                sms=Count('id', filter=Q(type='sms')),
                email=Count('id', filter=Q(type='email')),
                whatsapp=Count('id', filter=Q(type='whatsapp'))
            )
            .order_by('-date')
        )
        detailed_communication_statistics = []
        for entry in daily_stats:
            total_daily = entry['sms'] + entry['email'] + entry['whatsapp']
            detailed_communication_statistics.append({
                "date": entry['date'],
                "sms": entry['sms'],
                "email": entry['email'],
                "whatsapp": entry['whatsapp'],
                "total": total_daily
            })
        return Response({
            "summary_cards": {
                "sms_count": totals['sms'] or 0,       
                "email_count": totals['email'] or 0,
                "whatsapp_count": totals['whatsapp'] or 0
            },
            "detailed_communication_statistics": detailed_communication_statistics
        })

    @action(detail=False, methods=['get'])
    def download_pdf(self, request):
        # 1. Get Filters
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        logs = CommunicationLog.objects.all()
        if start_date and end_date:
            logs = logs.filter(timestamp__date__range=[parse_date(start_date), parse_date(end_date)])

        # 2. Aggregate Data (Group by Date)
        daily_stats = (
            logs.annotate(date=TruncDate('timestamp'))
            .values('date')
            .annotate(
                sms=Count('id', filter=Q(type='sms')),
                email=Count('id', filter=Q(type='email')),
                whatsapp=Count('id', filter=Q(type='whatsapp'))
            ).order_by('-date')
        )

        # 3. Build PDF Elements
        elements = []
        styles = getSampleStyleSheet()
        elements.append(Paragraph("Communication Statistics Report", styles['Title']))
        
        filter_text = f"Period: {start_date} to {end_date}" if start_date else "Period: All Time"
        elements.append(Paragraph(filter_text, styles['Normal']))
        elements.append(Spacer(1, 20))

        # --- Stats Table ---
        data = [['Date', 'SMS', 'Email', 'WhatsApp', 'Total']]
        for item in daily_stats:
            total = item['sms'] + item['email'] + item['whatsapp']
            data.append([
                str(item['date']), 
                str(item['sms']), 
                str(item['email']), 
                str(item['whatsapp']), 
                str(total)
            ])

        table = Table(data, colWidths=[120, 80, 80, 80, 80])
        table.setStyle(get_header_style())
        elements.append(table)

        return create_pdf_response("Stats_Report", elements)

class VendorStatsViewSet(viewsets.ViewSet):
    def list(self, request):
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        month = request.query_params.get('month')
        year = request.query_params.get('year')
        vendors = Vendor.objects.all()
        raw_data = []
        
        for vendor in vendors:
            # 2. Base Query
            logs = CommunicationLog.objects.filter(vendor=vendor)
            
            # 3. APPLY FILTERS (This was missing)
            if start_date and end_date:
                s_date = parse_date(start_date)
                e_date = parse_date(end_date)
                if s_date and e_date:
                    logs = logs.filter(timestamp__date__range=[s_date, e_date])
            elif month and year:
                logs = logs.filter(timestamp__month=month, timestamp__year=year)
            
            # 4. Calculate Stats on the FILTERED logs
            total = logs.count()
            delivered = logs.filter(status='delivered').count()
            failed = logs.filter(status='failed').count()
            pending = logs.filter(status='pending').count()
            
            # 3. Calculate Rates & Costs
            delivery_rate = (delivered / total * 100) if total > 0 else 0
            total_cost = logs.aggregate(Sum('cost'))['cost__sum'] or 0.00
            last_activity = logs.aggregate(Max('timestamp'))['timestamp__max']
            type_map = {'sms': 'SMS Provider', 'email': 'Email Provider', 'whatsapp': 'WhatsApp Provider'}
            display_type = type_map.get(vendor.service_type, vendor.service_type.capitalize())
            
            # Performance Badge Logic
            if delivery_rate >= 95: perf_label = "Excellent"
            elif delivery_rate >= 90: perf_label = "Good"
            elif delivery_rate >= 80: perf_label = "Average"
            else: perf_label = "Poor"

            # 5. Build the raw dictionary
            raw_data.append({
                "id": vendor.id,
                "vendor_id": vendor.vendor_id,
                "name": vendor.name,
                "service_type": vendor.service_type,
                "contact_name": vendor.contact_name,
                "contact_email": vendor.contact_email,
                "cost_per_message": vendor.cost_per_message,
                "status": vendor.status,
                "total_communications": total,
                "delivery_rate": round(delivery_rate, 1),
                "delivered": delivered,
                "failed": failed,
                "pending": pending,
                "total_cost": total_cost,
                "last_activity": last_activity.date() if last_activity else None,
                "display_type": display_type,
                "performance_label": perf_label,
                "success_rate_label": perf_label
            })
            
        # 6. Serialize into two different formats
        cards_data = VendorCardSerializer(raw_data, many=True).data
        table_data = VendorTableSerializer(raw_data, many=True).data
        
        return Response({
            "vendor_cards": cards_data,
            "vendor_summary_table": table_data
        })

    @action(detail=False, methods=['get'])
    def download_pdf(self, request):
        """Generates PDF for Vendor Tab (Now with Filters!)"""
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        month = request.query_params.get('month')
        year = request.query_params.get('year')

        vendors = Vendor.objects.all()
        
        elements = []
        styles = getSampleStyleSheet()
        elements.append(Paragraph("Vendor Performance Report", styles['Title']))
        
        # Add filter text to PDF
        filter_text = "All Time"
        if start_date and end_date: filter_text = f"{start_date} to {end_date}"
        elif month and year: filter_text = f"{month}/{year}"
        elements.append(Paragraph(f"Period: {filter_text}", styles['Normal']))
        elements.append(Spacer(1, 20))

        data = [['Vendor', 'Type', 'Total Comm.', 'Success Rate', 'Total Cost']]
        
        for v in vendors:
            logs = CommunicationLog.objects.filter(vendor=v)
            
            # APPLY FILTERS TO PDF TOO
            if start_date and end_date:
                s_date = parse_date(start_date)
                e_date = parse_date(end_date)
                if s_date and e_date:
                    logs = logs.filter(timestamp__date__range=[s_date, e_date])
            elif month and year:
                logs = logs.filter(timestamp__month=month, timestamp__year=year)

            total = logs.count()
            delivered = logs.filter(status='delivered').count()
            rate = (delivered / total * 100) if total > 0 else 0
            cost = logs.aggregate(Sum('cost'))['cost__sum'] or 0

            data.append([
                v.name,
                v.service_type.upper(),
                str(total),
                f"{rate:.1f}%",
                f"{cost}"
            ])

        table = Table(data, colWidths=[180, 100, 80, 80, 80])
        table.setStyle(get_header_style())
        elements.append(table)

        return create_pdf_response("Vendor_Report", elements)
    
class DeliveryStatusViewSet(viewsets.ViewSet):
    @action(detail=False, methods=['get'])
    def individual_cases(self, request):
        logs = CommunicationLog.objects.select_related('vendor', 'customer', 'case').all().order_by('-timestamp')

        # Filter Logic
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        month = request.query_params.get('month')
        year = request.query_params.get('year')

        if start_date and end_date:
            s_date = parse_date(start_date)
            e_date = parse_date(end_date)
            if s_date and e_date:
                logs = logs.filter(timestamp__date__range=[s_date, e_date])
        
        elif month and year:
            logs = logs.filter(timestamp__month=month, timestamp__year=year)

        logs = logs[:50]

        serializer = DeliveryStatusSerializer(logs, many=True)
        return Response(serializer.data)
    @action(detail=False, methods=['get'])
    def campaigns(self, request):
        campaigns = Campaign.objects.all().order_by('-date')
        
        # Filter Logic
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        month = request.query_params.get('month')
        year = request.query_params.get('year')

        if start_date and end_date:
            s_date = parse_date(start_date)
            e_date = parse_date(end_date)
            if s_date and e_date:
                campaigns = campaigns.filter(date__range=[s_date, e_date])
        elif month and year:
            campaigns = campaigns.filter(date__month=month, date__year=year)

        serializer = CampaignSerializer(campaigns, many=True)
        return Response(serializer.data)
    @action(detail=False, methods=['get'])
    def download_pdf(self, request):
        logs = CommunicationLog.objects.select_related('vendor', 'customer', 'case').all().order_by('-timestamp')
        
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        month = request.query_params.get('month')
        year = request.query_params.get('year')
        
        filter_text = "All Records"

        if start_date and end_date:
            s_date = parse_date(start_date)
            e_date = parse_date(end_date)
            if s_date and e_date:
                logs = logs.filter(timestamp__date__range=[s_date, e_date])
                filter_text = f"{start_date} to {end_date}"
        elif month and year:
            logs = logs.filter(timestamp__month=month, timestamp__year=year)
            filter_text = f"{month}/{year}"
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=landscape(A4))
        elements = []
        styles = getSampleStyleSheet()
        elements.append(Paragraph("Delivery Status Report", styles['Title']))
        elements.append(Paragraph(f"Period: {filter_text}", styles['Normal']))
        elements.append(Spacer(1, 20))
        data = [['Case ID', 'Customer', 'Type', 'Status', 'Vendor', 'Cost']]
        for log in logs[:200]: 
            case_id = log.case.case_number if log.case else "-"
            if log.customer:
                cust_info = f"{log.customer.full_name}\n({log.customer.customer_code})"
            else:
                cust_info = "Unknown"

            row = [
                case_id,
                cust_info,
                log.type.upper(),
                log.status.title(),
                log.vendor.name if log.vendor else "-",
                f"{log.cost}"
            ]
            data.append(row)
        table = Table(data, colWidths=[90, 150, 70, 80, 120, 60])
        
        style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0f172a')), 
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),               
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),                      
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),                
        ])
        for i, row in enumerate(data[1:], start=1):
            status = row[3].lower()
            if 'failed' in status:
                style.add('TEXTCOLOR', (3, i), (3, i), colors.red)
            elif 'delivered' in status:
                style.add('TEXTCOLOR', (3, i), (3, i), colors.green)

        table.setStyle(style)
        elements.append(table)
        doc.build(elements)
        buffer.seek(0)
        response = HttpResponse(buffer, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="Delivery_Status_{filter_text}.pdf"'
        return response