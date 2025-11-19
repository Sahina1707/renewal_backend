from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('summary/', views.dashboard_summary, name='dashboard-summary'),
    path('filter/', views.dashboard_filtered, name='dashboard-filter'),

    path('ai/chat/', views.ai_chat, name='ai-chat'),
    path('ai/suggestions/', views.ai_suggestions, name='ai-suggestions'),
    path('ai/analytics/', views.ai_analytics, name='ai-analytics'),
    path('ai/conversations/', views.ai_conversations, name='ai-conversations'),
    path('ai/conversations/<str:session_id>/messages/', views.ai_conversation_messages, name='ai-conversation-messages'),
    path('ai/status/', views.ai_status, name='ai-status'),
]
