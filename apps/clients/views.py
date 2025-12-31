from rest_framework.viewsets import ModelViewSet
from rest_framework.response import Response
from rest_framework import status
from .models import Client
from .serializers import ClientSerializer

class ClientViewSet(ModelViewSet):
    """
    Client CRUD APIs:
    - GET    /api/clients/
    - POST   /api/clients/
    - PATCH  /api/clients/{id}/
    - DELETE /api/clients/{id}/
    """

    serializer_class = ClientSerializer

    def get_queryset(self):
        # GET clients (exclude soft deleted)
        return Client.objects.filter(is_deleted=False)

    def create(self, request, *args, **kwargs):
        # POST client
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        # PATCH client
        instance = self.get_object()
        serializer = self.get_serializer(
            instance,
            data=request.data,
            partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        # DELETE client (SOFT DELETE)
        client = self.get_object()
        client.is_deleted = True
        client.is_active = False
        client.save()

        return Response(
            {"message": "Client deleted successfully"},
            status=status.HTTP_204_NO_CONTENT
        )
