from django.urls import path
from .views import get_suggestions, send_request_get_response

app_name = 'case_logs_chatbot'

urlpatterns = [
    path('suggestions/', get_suggestions, name='get_suggestions'),
    path('chat/', send_request_get_response, name='send_request_get_response'),
]
