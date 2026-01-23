from rest_framework import viewsets, permissions
from rest_framework.exceptions import ValidationError
from .models import Competitor
from .serializers import CompetitorSerializer
from apps.renewal_settings.models import RenewalSettings
from .services import refresh_all_cases

class CompetitorViewSet(viewsets.ModelViewSet):
    queryset = Competitor.objects.all().order_by('name')
    serializer_class = CompetitorSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        name = serializer.validated_data.get("name")
        if Competitor.objects.filter(name__iexact=name).exists():
            raise ValidationError({"name": "Competitor with this name already exists."})

        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        name = serializer.validated_data.get("name")
        competitor_id = self.get_object().id

        if Competitor.objects.filter(name__iexact=name).exclude(id=competitor_id).exists():
            raise ValidationError({"name": "Competitor with this name already exists."})

        serializer.save(updated_by=self.request.user)
from .models import RenewalCase
from .serializers import RenewalCaseSerializer


class RenewalCaseViewSet(viewsets.ModelViewSet):
    """
    Added ONLY to support:
    1) Auto refresh
    2) Edit case ON / OFF
    """

    queryset = RenewalCase.objects.all().order_by("-created_at")
    serializer_class = RenewalCaseSerializer
    permission_classes = [permissions.IsAuthenticated]

    # FEATURE 1: AUTO REFRESH
    def list(self, request, *args, **kwargs):
        # Fix: Robust lookup instead of get_settings()
        settings = RenewalSettings.objects.filter(enable_call_integration=True).first()
        if not settings:
            settings = RenewalSettings.objects.first()

        if settings and settings.auto_refresh_enabled:
            refresh_all_cases()
        return super().list(request, *args, **kwargs)

    # FEATURE 2: EDIT CASE ON / OFF
    def update(self, request, *args, **kwargs):
        settings = RenewalSettings.objects.filter(enable_call_integration=True).first()
        if not settings:
            settings = RenewalSettings.objects.first()

        # If settings exist, check the flag. If no settings, assume allowed (or safe default)
        if settings and not settings.show_edit_case_button:
            raise ValidationError("Editing renewal cases is disabled by admin.")
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        settings = RenewalSettings.objects.filter(enable_call_integration=True).first()
        if not settings:
            settings = RenewalSettings.objects.first()

        if settings and not settings.show_edit_case_button:
            raise ValidationError("Editing renewal cases is disabled by admin.")
        return super().partial_update(request, *args, **kwargs)
