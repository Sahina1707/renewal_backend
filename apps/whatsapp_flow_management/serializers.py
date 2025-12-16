# whatsapp_flow_management/serializers.py

from rest_framework import serializers
from django.db import transaction
from .models import (
    WhatsAppFlow, 
    FlowBlock, 
    WhatsAppMessageTemplate, 
    FlowTemplate,
    FlowAnalytics
)

# --- 1. Flow Block Serializer ---
class FlowBlockSerializer(serializers.ModelSerializer):
    class Meta:
        model = FlowBlock
        # Include 'id' for update/delete operations
        fields = ['id', 'block_id', 'block_type', 'configuration', 'connections']

# --- 2. WhatsApp Flow Serializer (List View) ---
class WhatsAppFlowSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    trigger_display = serializers.CharField(source='get_entry_point_display', read_only=True)
    
    # Note: Analytics field would be added here later for the list view tiles

    class Meta:
        model = WhatsAppFlow
        fields = [
            'id', 'name', 'status', 'status_display', 
            'entry_point', 'trigger_display', 'canvas_layout', 'created_at'
        ]

# --- 3. WhatsApp Flow Detail Serializer (Flow Builder Save/Retrieve) ---
class WhatsAppFlowDetailSerializer(WhatsAppFlowSerializer):
    # Writable nested serializer for blocks
    blocks = FlowBlockSerializer(many=True, required=False) 
    
    class Meta:
        model = WhatsAppFlow
        fields = WhatsAppFlowSerializer.Meta.fields + ['blocks']

    @transaction.atomic
    def create(self, validated_data):
        blocks_data = validated_data.pop('blocks', [])
        # Assuming created_by is passed via context, as done previously
        flow = WhatsAppFlow.objects.create(**validated_data, created_by=self.context['request'].user)
        for block_data in blocks_data:
            FlowBlock.objects.create(flow=flow, **block_data)
        return flow

    @transaction.atomic
    def update(self, instance, validated_data):
        blocks_data = validated_data.pop('blocks', None)
        instance = super().update(instance, validated_data)

        if blocks_data is not None:
            # Logic to handle CUD operations on FlowBlock using block_id
            existing_blocks = {block.block_id: block for block in instance.blocks.all()}
            incoming_block_ids = set()

            for block_data in blocks_data:
                block_id = block_data.get('block_id')
                incoming_block_ids.add(block_id)

                if block_id in existing_blocks:
                    block = existing_blocks[block_id]
                    block_serializer = FlowBlockSerializer(instance=block, data=block_data, partial=True)
                    block_serializer.is_valid(raise_exception=True)
                    block_serializer.save()
                else:
                    FlowBlock.objects.create(flow=instance, **block_data)

            ids_to_delete = existing_blocks.keys() - incoming_block_ids
            FlowBlock.objects.filter(flow=instance, block_id__in=ids_to_delete).delete()

        return instance


# --- 4. WhatsApp Message Template Serializer (NEW CRUD API) ---
class WhatsAppMessageTemplateSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = WhatsAppMessageTemplate
        fields = ['id', 'name', 'status', 'status_display', 'content_json', 'created_at']
        read_only_fields = ['id', 'status_display', 'created_at']

# --- 5. Flow Template Serializer (NEW CRUD API) ---
class FlowTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = FlowTemplate
        fields = ['id', 'name', 'description', 'template_flow_json', 'category']
        read_only_fields = ['id']