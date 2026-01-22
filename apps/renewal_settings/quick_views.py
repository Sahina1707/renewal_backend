from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from .services import QuickMessageService, limitReachedException

class QuickMessageSendView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        Endpoint to send a Quick Message.
        Payload:
        {
            "recipient_phone": "1234567890",
            "template_text": "Hi {{customerName}}...", 
            "context": {"customerName": "Arjun", "policyNumber": "123"},
            "channel": "whatsapp" | "sms"
        }
        """
        # 1. Validate Input
        phone = request.data.get('recipient_phone')
        text = request.data.get('template_text')
        context = request.data.get('context', {})
        channel = request.data.get('channel', 'whatsapp')

        if not phone or not text:
            return Response({"error": "Recipient phone and template text are required."}, status=400)

        # 2. Call Service
        service = QuickMessageService()
        
        try:
            result = service.send_quick_message(
                recipient_phone=phone,
                template_text=text,
                context=context,
                channel=channel
            )
            return Response({"message": "Message sent successfully", "provider_response": result}, status=200)

        except limitReachedException as e:
            return Response({"error": str(e)}, status=429) # Too Many Requests
        except Exception as e:
             return Response({"error": str(e)}, status=500)
