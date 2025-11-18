from rest_framework import serializers
from .models import Team
from django.contrib.auth import get_user_model

User = get_user_model()

class TeamMemberSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "first_name", "last_name", "email", "job_title"]

class TeamSerializer(serializers.ModelSerializer):
    members = TeamMemberSerializer(many=True, read_only=True)
    member_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Team
        fields = ["id", "name", "description", "is_active", "member_count", "members"]
