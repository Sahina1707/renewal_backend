from rest_framework import serializers
from django.db import transaction
from .models import (
    WhatsAppFlow, 
    FlowBlock, 
    WhatsAppMessageTemplate, 
    FlowTemplate,
    FlowAnalytics,
    AITemplate
)

# --- 1. Flow Block Serializer ---
class FlowBlockSerializer(serializers.ModelSerializer):
    class Meta:
        model = FlowBlock
        # Include 'id' for update/delete operations
        fields = ['id', 'block_id', 'block_type', 'configuration', 'connections']
class WhatsAppFlowSerializer(serializers.ModelSerializer):
    """
    Lightweight Serializer for the 'Flow Management' cards.
    Excludes 'canvas_layout' to improve performance.
    Adds computed fields for UI stats (Recipients, Delivery Rate, Tags).
    """
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    recipients = serializers.SerializerMethodField()
    delivery_rate = serializers.SerializerMethodField()
    last_run = serializers.SerializerMethodField()
    tags = serializers.SerializerMethodField()
    
    class Meta:
        model = WhatsAppFlow
        # REMOVED 'canvas_layout' from here (only needed in detail view)
        fields = [
            'id', 'name', 'status', 'status_display', 
            'entry_point', 'recipients', 'delivery_rate', 
            'last_run', 'tags', 'created_at'
        ]

    def get_recipients(self, obj):
        # Fetch 'total_runs' from Analytics. Use safe navigation (getattr)
        if hasattr(obj, 'analytics'):
            return obj.analytics.total_runs
        return 0

    def get_delivery_rate(self, obj):
        # Calculate success rate based on completed vs total runs
        if hasattr(obj, 'analytics') and obj.analytics.total_runs > 0:
            rate = (obj.analytics.completed_runs / obj.analytics.total_runs) * 100
            return f"{rate:.1f}%"
        return "0.0%"

    def get_last_run(self, obj):
        # Format date like "Jan 15, 2024, 04:00 PM"
        return obj.updated_at.strftime("%b %d, %Y, %I:%M %p")

    def get_tags(self, obj):
        # Dynamic tags based on Flow Trigger/Entry Point
        tags = []
        
        # Tag 1: Category
        if obj.entry_point == 'INBOUND':
            tags.append("Onboarding")
        elif obj.entry_point == 'SCHEDULED':
            tags.append("Renewal")
        elif obj.entry_point == 'POST_CAMPAIGN':
            tags.append("Marketing")
        else:
            tags.append("General")
            
        # Tag 2: Audience (Placeholder)
        tags.append("All Customers")
        return tags


# --- 3. WhatsApp Flow Detail Serializer (Flow Builder - Save/Retrieve) ---
class WhatsAppFlowDetailSerializer(WhatsAppFlowSerializer):
    """
    Detailed Serializer for the Flow Builder Canvas.
    Includes 'canvas_layout' and nested 'blocks'.
    """
    blocks = FlowBlockSerializer(many=True, required=False)
    
    class Meta:
        model = WhatsAppFlow
        # Add 'canvas_layout' back here since the Builder needs it
        fields = WhatsAppFlowSerializer.Meta.fields + ['blocks', 'canvas_layout']

    @transaction.atomic
    def create(self, validated_data):
        blocks_data = validated_data.pop('blocks', [])
        # Assuming created_by is passed via context
        user = self.context['request'].user if self.context.get('request') else None
        
        flow = WhatsAppFlow.objects.create(**validated_data, created_by=user)
        
        block_objects = [FlowBlock(flow=flow, **data) for data in blocks_data]
        FlowBlock.objects.bulk_create(block_objects)
        
        return flow

    @transaction.atomic
    def update(self, instance, validated_data):
        blocks_data = validated_data.pop('blocks', None)
        
        # Update Flow fields (Name, Status, Canvas Layout)
        instance = super().update(instance, validated_data)

        if blocks_data is not None:
            # Smart Update for Blocks
            existing_blocks = {block.block_id: block for block in instance.blocks.all()}
            incoming_block_ids = set()
            new_blocks = []

            for block_data in blocks_data:
                block_id = block_data.get('block_id')
                incoming_block_ids.add(block_id)

                if block_id in existing_blocks:
                    # Update existing block
                    block = existing_blocks[block_id]
                    for attr, value in block_data.items():
                        setattr(block, attr, value)
                    block.save()
                else:
                    # Prepare new block
                    new_blocks.append(FlowBlock(flow=instance, **block_data))

            # Bulk create new blocks
            if new_blocks:
                FlowBlock.objects.bulk_create(new_blocks)

            # Delete removed blocks
            ids_to_delete = existing_blocks.keys() - incoming_block_ids
            if ids_to_delete:
                FlowBlock.objects.filter(flow=instance, block_id__in=ids_to_delete).delete()

        return instance
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
class AITemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = AITemplate
        fields = ['id', 'name', 'description', 'category', 'prompt_used', 'generated_content', 'status', 'created_at']
        read_only_fields = ['id', 'created_at']
