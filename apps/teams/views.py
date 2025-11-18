from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import Team
from .serializers import TeamSerializer, TeamMemberSerializer

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_teams(request):
    teams = Team.objects.filter(is_active=True)
    serializer = TeamSerializer(teams, many=True)
    return Response({"success": True, "teams": serializer.data})

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def team_members(request, team_id):
    try:
        team = Team.objects.get(id=team_id)
    except Team.DoesNotExist:
        return Response({"success": False, "error": "Team not found"}, status=404)

    serializer = TeamMemberSerializer(team.members.all(), many=True)
    return Response({"success": True, "members": serializer.data})
