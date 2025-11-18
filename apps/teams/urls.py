from django.urls import path
from .views import list_teams, team_members

urlpatterns = [
    path("", list_teams, name="team-list"),
    path("<int:team_id>/members/", team_members, name="team-members"),
]
