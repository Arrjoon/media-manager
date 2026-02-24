from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APITestCase
from rest_framework.test import APIClient
from rest_framework import status

from media_manager.models import Media, Folder, Tag

User = get_user_model()


class FolderModelTests(TestCase):
    """Tests for Folder model."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )
        self.root_folder = Folder.objects.create(
            name="Root",
            owner=self.user
        )
        self.child_folder = Folder.objects.create(
            name="Child",
            parent=self.root_folder,
            owner=self.user
        )

    def test_folder_creation(self):
        """Test folder can be created."""
        self.assertEqual(self.root_folder.name, "Root")
        self.assertIsNone(self.root_folder.parent)

    def test_folder_hierarchy(self):
        """Test folder hierarchy works correctly."""
        self.assertEqual(self.child_folder.parent, self.root_folder)

    def test_get_full_path(self):
        """Test full path generation."""
        path = self.child_folder.get_full_path()
        self.assertEqual(path, "Root/Child")

    def test_unique_together_constraint(self):
        """Test folder name must be unique under parent."""
        with self.assertRaises(Exception):
            Folder.objects.create(
                name="Root",
                parent=None,
                owner=self.user
            )


class TagModelTests(TestCase):
    """Tests for Tag model."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

    def test_tag_creation(self):
        """Test tag can be created."""
        tag = Tag.objects.create(name="landscape", owner=self.user)
        self.assertEqual(tag.name, "landscape")
        self.assertEqual(tag.owner, self.user)

    def test_tag_unique_name(self):
        """Test tag name is unique."""
        Tag.objects.create(name="sunset", owner=self.user)
        with self.assertRaises(Exception):
            Tag.objects.create(name="sunset", owner=self.user)


class MediaAPITests(APITestCase):
    """Tests for Media API endpoints."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )
        self.other_user = User.objects.create_user(
            username="otheruser",
            email="other@example.com",
            password="testpass123",
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        self.folder = Folder.objects.create(
            name="Test Folder",
            owner=self.user
        )
        self.tag = Tag.objects.create(name="test-tag", owner=self.user)

    def test_upload_media(self):
        """Test uploading media."""
        file = SimpleUploadedFile(
            "test.jpg",
            b"file content",
            content_type="image/jpeg"
        )
        
        data = {
            "file": file,
            "title": "Test Image",
            "folder": self.folder.id,
        }
        
        response = self.client.post("/api/media-manager/media/", data, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["title"], "Test Image")

    def test_list_media(self):
        """Test listing media."""
        Media.objects.create(
            file="test.jpg",
            title="Test Image",
            size=1024,
            uploaded_by=self.user,
            file_type="image"
        )
        
        response = self.client.get("/api/media-manager/media/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)

    def test_media_permission(self):
        """Test user can't access other user's media."""
        media = Media.objects.create(
            file="test.jpg",
            title="Test Image",
            size=1024,
            uploaded_by=self.other_user,
            file_type="image"
        )
        
        response = self.client.get(f"/api/media-manager/media/{media.id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_add_tags_to_media(self):
        """Test adding tags to media."""
        media = Media.objects.create(
            file="test.jpg",
            title="Test Image",
            size=1024,
            uploaded_by=self.user,
            file_type="image"
        )
        
        data = {"tag_ids": [self.tag.id]}
        response = self.client.post(
            f"/api/media-manager/media/{media.id}/add_tags/",
            data,
            format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(self.tag.id, [t["id"] for t in response.data["tags"]])

    def test_move_media_to_folder(self):
        """Test moving media to different folder."""
        media = Media.objects.create(
            file="test.jpg",
            title="Test Image",
            size=1024,
            uploaded_by=self.user,
            file_type="image"
        )
        
        new_folder = Folder.objects.create(
            name="New Folder",
            owner=self.user
        )
        
        data = {"folder_id": new_folder.id}
        response = self.client.post(
            f"/api/media-manager/media/{media.id}/move_to_folder/",
            data,
            format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["folder"], new_folder.id)

    def test_media_stats(self):
        """Test media statistics endpoint."""
        Media.objects.create(
            file="test1.jpg",
            title="Test Image 1",
            size=1024,
            uploaded_by=self.user,
            file_type="image"
        )
        Media.objects.create(
            file="test2.mp4",
            title="Test Video",
            size=5000000,
            uploaded_by=self.user,
            file_type="video"
        )
        
        response = self.client.get("/api/media-manager/media/stats/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_media"], 2)
        self.assertIn("by_type", response.data)


class FolderAPITests(APITestCase):
    """Tests for Folder API endpoints."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_create_folder(self):
        """Test creating a folder."""
        data = {"name": "Test Folder"}
        response = self.client.post("/api/media-manager/folders/", data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["name"], "Test Folder")

    def test_create_nested_folder(self):
        """Test creating nested folder."""
        parent = Folder.objects.create(name="Parent", owner=self.user)
        data = {"name": "Child", "parent": parent.id}
        response = self.client.post("/api/media-manager/folders/", data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["parent"], parent.id)

    def test_get_folder_tree(self):
        """Test getting folder tree structure."""
        Folder.objects.create(name="Root1", owner=self.user)
        Folder.objects.create(name="Root2", owner=self.user)
        
        response = self.client.get("/api/media-manager/folders/tree/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)


class TagAPITests(APITestCase):
    """Tests for Tag API endpoints."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_create_tag(self):
        """Test creating a tag."""
        data = {"name": "landscape"}
        response = self.client.post("/api/media-manager/tags/", data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["name"], "landscape")

    def test_list_tags(self):
        """Test listing tags."""
        Tag.objects.create(name="tag1", owner=self.user)
        Tag.objects.create(name="tag2", owner=self.user)
        
        response = self.client.get("/api/media-manager/tags/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 2)

    def test_tag_media_count(self):
        """Test getting media count for tag."""
        tag = Tag.objects.create(name="test", owner=self.user)
        media = Media.objects.create(
            file="test.jpg",
            size=1024,
            uploaded_by=self.user,
            file_type="image"
        )
        media.tags.add(tag)
        
        response = self.client.get(f"/api/media-manager/tags/{tag.id}/media_count/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["media_count"], 1)