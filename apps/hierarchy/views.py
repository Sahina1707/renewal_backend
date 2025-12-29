from rest_framework import viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from .models import Region, State, Branch, Department, Team
from .serializers import (
    RegionSerializer, StateSerializer, BranchSerializer, 
    DepartmentSerializer, TeamSerializer
)

class RegionViewSet(viewsets.ModelViewSet):
    queryset = Region.objects.all()
    serializer_class = RegionSerializer

class StateViewSet(viewsets.ModelViewSet):
    queryset = State.objects.all()
    serializer_class = StateSerializer

class BranchViewSet(viewsets.ModelViewSet):
    queryset = Branch.objects.all()
    serializer_class = BranchSerializer

class DepartmentViewSet(viewsets.ModelViewSet):
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer

class TeamViewSet(viewsets.ModelViewSet):
    queryset = Team.objects.all()
    serializer_class = TeamSerializer

# --- SUMMARY TABLE API (For the Hierarchy Performance Table) ---
class HierarchySummaryView(APIView):
    def get(self, request):
        data = []
        # Gather all data from 5 tables
        data.extend(RegionSerializer(Region.objects.all(), many=True).data)
        data.extend(StateSerializer(State.objects.all(), many=True).data)
        data.extend(BranchSerializer(Branch.objects.all(), many=True).data)
        data.extend(DepartmentSerializer(Department.objects.all(), many=True).data)
        data.extend(TeamSerializer(Team.objects.all(), many=True).data)
        return Response(data)