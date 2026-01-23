from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from .models import SurveySettings, IntegrationCredential
from .serializers import SurveySettingsSerializer, IntegrationCredentialSerializer

class SurveySettingsViewSet(viewsets.ModelViewSet):
    serializer_class = SurveySettingsSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ['get', 'patch', 'head', 'options'] 

    def get_queryset(self):
        return SurveySettings.objects.filter(owner=self.request.user)

    def list(self, request, *args, **kwargs):
        settings_obj, created = SurveySettings.objects.get_or_create(owner=request.user)
        serializer = self.get_serializer(settings_obj)
        return Response(serializer.data)


class IntegrationViewSet(viewsets.ModelViewSet):
    serializer_class = IntegrationCredentialSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return IntegrationCredential.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)