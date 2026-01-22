from django.test import TestCase
from django.contrib.auth import get_user_model
from .models import HierarchyNode
from rest_framework.test import APIClient
from rest_framework import status

User = get_user_model()

class HierarchyNodeTests(TestCase):
    def setUp(self):
        # Create a user for manager linking
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpassword123',
            first_name='Test',
            last_name='Manager'
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_create_root_node(self):
        """Test creating a top-level node (Department)"""
        node = HierarchyNode.objects.create(
            unit_name="Head Office",
            unit_type="department",
            manager=self.user
        )
        self.assertEqual(node.unit_name, "Head Office")
        self.assertIsNone(node.parent)
        self.assertEqual(node.manager, self.user)

    def test_create_child_nodes(self):
        """Test creating a hierarchy: Region -> State -> Branch"""
        region = HierarchyNode.objects.create(
            unit_name="North Region",
            unit_type="region"
        )
        
        state = HierarchyNode.objects.create(
            unit_name="Delhi State",
            unit_type="state",
            parent=region
        )
        
        branch = HierarchyNode.objects.create(
            unit_name="Connaught Place Branch",
            unit_type="branch",
            parent=state
        )
        
        # Verify relationships
        self.assertEqual(state.parent, region)
        self.assertEqual(branch.parent, state)
        self.assertEqual(branch.parent.parent, region)
        
        # Verify reverse relationships
        self.assertIn(state, region.children.all())
        self.assertIn(branch, state.children.all())

    def test_prevent_self_parenting(self):
        """Test that a node cannot be its own parent"""
        node = HierarchyNode.objects.create(unit_name="Self Loop", unit_type="region")
        
        node.parent = node
        with self.assertRaises(Exception): # ValidationError from model.clean()
            node.save()
            
    def test_api_create_hierarchy(self):
        """Test creating hierarchy via API"""
        # 1. Create Parent
        response = self.client.post('/apps/hierarchy/api/units/', {
            'unit_name': 'API Region',
            'unit_type': 'region',
            'status': 'active'
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        parent_id = response.data['data']['id']
        
        # 2. Create Child
        response = self.client.post('/apps/hierarchy/api/units/', {
            'unit_name': 'API State',
            'unit_type': 'state',
            'parent': parent_id,
            'status': 'active'
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['data']['parent'], parent_id)
