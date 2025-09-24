from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()

app_name = 'case_history'

urlpatterns = [
    path('', views.CaseListView.as_view(), name='case-list'),
    path('<str:case_number>/', views.CaseDetailView.as_view(), name='case-detail'),
    path('<str:case_number>/status/', views.CaseStatusUpdateView.as_view(), name='case-status-update'),
    path('<str:case_number>/assign/', views.CaseAssignmentView.as_view(), name='case-assign'),
    path('<str:case_number>/close/', views.CaseCloseView.as_view(), name='case-close'),
    
    path('<str:case_number>/history/', views.CaseHistoryListView.as_view(), name='case-history-list'),
    
    path('<str:case_number>/comments/', views.CaseCommentListView.as_view(), name='case-comment-list'),
    path('<str:case_number>/comments/<int:pk>/', views.CaseCommentDetailView.as_view(), name='case-comment-detail'),
    
    path('<str:case_number>/timeline/', views.case_timeline_view, name='case-timeline'),
    path('<str:case_number>/stats/', views.case_stats_view, name='case-stats'),
    
    path('', include(router.urls)),
]
