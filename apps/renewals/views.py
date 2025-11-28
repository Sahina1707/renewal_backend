from rest_framework import viewsets, permissions
from rest_framework.exceptions import ValidationError
from .models import Competitor
from .serializers import CompetitorSerializer

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
