from rest_framework import generics, status, filters
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny 
from django.shortcuts import get_object_or_404
from rest_framework.parsers import FormParser, JSONParser 
from apps.renewals.models import RenewalCase
from apps.templates.models import Template
from .models import WhatsAppMessage
from .serializers import (
    WhatsAppChatListSerializer, 
    WhatsAppMessageSerializer, 
    StartNewChatSerializer,
    WhatsAppTemplateSerializer
)
# --- FIX 1: Import the service ---
from .services import send_agent_message 

# --- 1. The Main Dashboard List (Left Sidebar) ---
class WhatsAppChatListView(generics.ListAPIView):
    """
    API for the Left Sidebar Chat List.
    Supports: Filtering (Status, Priority) AND Searching (Name, Phone, Policy, Message Text).
    Endpoint: GET /api/whatsapp/chats/?search=anything
    """
    serializer_class = WhatsAppChatListSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    
    # --- SEARCH CONFIGURATION ---
    search_fields = [
        'customer__first_name', 
        'customer__last_name', 
        'customer__phone', 
        'policy__policy_number', 
        'case_number',
        'whatsapp_messages__content'  # <--- THIS enables searching inside chat history!
    ]


    def get_queryset(self):
        # Use distinct() to avoid duplicate results if a search term appears in multiple messages
        queryset = RenewalCase.objects.all().select_related('customer', 'policy').distinct()
        
        status_param = self.request.query_params.get('status')
        priority_param = self.request.query_params.get('priority')

        if status_param and status_param != 'All Status':
            queryset = queryset.filter(status__iexact=status_param.lower().replace(" ", "_"))
            
        if priority_param and priority_param != 'All Priority':
            queryset = queryset.filter(priority__iexact=priority_param.lower())

        return queryset.order_by('-updated_at')


# --- 2. Chat History & Sending Messages ---
class WhatsAppMessageListView(generics.ListCreateAPIView):
    serializer_class = WhatsAppMessageSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        case_number = self.kwargs['case_number']
        return WhatsAppMessage.objects.filter(case__case_number=case_number).order_by('created_at')

    # --- FIX 2: Logic placed correctly here ---
    def perform_create(self, serializer):
        case_number = self.kwargs['case_number']
        case = get_object_or_404(RenewalCase, case_number=case_number)
        
        # 1. Save to DB
        instance = serializer.save(
            case=case,
            sender_type='agent',
            sender_user=self.request.user
        )
        
        # 2. Send Real Message via Twilio
        # Uses the service you created
        if case.customer and case.customer.phone:
            send_agent_message(
                to_number=case.customer.phone, 
                message_content=instance.content
            )


# --- 3. Start New Chat (Modal) ---
class StartNewChatView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = StartNewChatSerializer(data=request.data)
        if serializer.is_valid():
            data = serializer.validated_data
            policy_number = data.get('policy_number')
            initial_message = data.get('initial_message')
            
            try:
                case = RenewalCase.objects.get(policy__policy_number=policy_number)
            except RenewalCase.DoesNotExist:
                return Response({
                    "success": False,
                    "message": f"No active renewal case found for policy {policy_number}"
                }, status=status.HTTP_404_NOT_FOUND)

            # Create the first WhatsApp Message in the DB
            if initial_message:
                WhatsAppMessage.objects.create(
                    case=case,
                    sender_type='agent',
                    sender_user=request.user,
                    content=initial_message,
                    is_read=True
                )
                
                # --- FIX 3: Also send the *Initial* message via Twilio ---
                if case.customer and case.customer.phone:
                    send_agent_message(
                        to_number=case.customer.phone,
                        message_content=initial_message
                    )

            return Response({
                "success": True, 
                "message": "Chat located successfully",
                "case_number": case.case_number 
            }, status=status.HTTP_200_OK)
            
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# --- 4. Message Updates (Starring) ---
class WhatsAppMessageUpdateView(generics.RetrieveUpdateDestroyAPIView):
    queryset = WhatsAppMessage.objects.all()
    serializer_class = WhatsAppMessageSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'id'


# --- 5. Template List ---
class WhatsAppTemplateListView(generics.ListAPIView):
    queryset = Template.objects.filter(channel='whatsapp')
    serializer_class = WhatsAppTemplateSerializer
    permission_classes = [IsAuthenticated]


# --- 6. Customer Lookup ---
class CustomerLookupView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        phone = request.query_params.get('phone')
        if not phone:
            return Response({"error": "Phone number required"}, status=status.HTTP_400_BAD_REQUEST)

        # 1. Find ALL cases matching this phone number (not just .first())
        cases = RenewalCase.objects.filter(customer__phone__icontains=phone).select_related('customer', 'policy')

        if not cases.exists():
            return Response({"found": False, "message": "No customer found"})

        # 2. Build a List of Results
        results = []
        for case in cases:
            results.append({
                "found": True,
                "customer_name": case.customer.full_name,
                "policy_number": case.policy.policy_number,
                "premium_amount": case.policy.premium_amount,
                "renewal_date": case.policy.end_date
            })

        # 3. Return the List (Frontend will map this to a dropdown)
        return Response(results, status=status.HTTP_200_OK)

class TwilioWebhookView(APIView):
    """
    Receives incoming WhatsApp messages from Twilio.
    """
    permission_classes = [AllowAny] # Twilio doesn't have your login token
    parser_classes = [FormParser,JSONParser]   # Twilio sends data as 'Form', not JSON

    def post(self, request):
        data = request.data
        
        # 1. Get Data from Twilio
        # Twilio sends 'From' as 'whatsapp:+919999999999'
        raw_from = data.get('From', '') 
        body = data.get('Body', '')
        message_sid = data.get('MessageSid', '')

        if not raw_from:
            return Response({"status": "ignored"}, status=status.HTTP_200_OK)

        # 2. Clean Phone Number (Remove 'whatsapp:' and '+')
        # We need to match it with your Database format
        clean_phone = raw_from.replace('whatsapp:', '').replace('+', '')
        # E.g., "919999999999"

        # 3. Find the Customer & Active Case
        # We look for a case connected to this phone number
        case = RenewalCase.objects.filter(
            customer__phone__icontains=clean_phone[-10:] # Search last 10 digits to be safe
        ).order_by('-updated_at').first()

        if not case:
            print(f"Received message from {clean_phone} but no Case found.")
            # We still return 200 so Twilio doesn't retry
            return Response({"status": "no_case_found"}, status=status.HTTP_200_OK)

        # 4. Save Message to Database
        WhatsAppMessage.objects.create(
            case=case,
            sender_type='customer', # &lt;--- It's from the Customer
            content=body,
            wa_message_id=message_sid,
            is_read=False
        )
        
        print(f"New reply saved from {clean_phone}: {body}")

        return Response({"status": "success"}, status=status.HTTP_200_OK)