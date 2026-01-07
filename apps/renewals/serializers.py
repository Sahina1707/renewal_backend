from rest_framework import serializers
from .models import Competitor

class CompetitorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Competitor
        fields = ['id', 'name', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


from .models import RenewalCase


class RenewalCaseSerializer(serializers.ModelSerializer):
    class Meta:
        model = RenewalCase
        fields = "__all__"
