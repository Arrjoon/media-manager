from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import FileExtensionValidator
from django.utils import timezone
from pathlib import Path

User = get_user_model()


class Folder(models.Model):
    """Hierarchical folder structure for organizing media."""
    name = models.CharField(max_length=255)
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        related_name="children",
        on_delete=models.CASCADE,
    )
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="folders")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("name", "parent", "owner")
        ordering = ["name"]
        indexes = [
            models.Index(fields=["owner", "parent"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return self.get_full_path()

    def get_full_path(self):
        """Get the complete path from root to this folder."""
        parts = [self.name]
        parent = self.parent
        while parent:
            parts.append(parent.name)
            parent = parent.parent
        return "/".join(reversed(parts))

    def get_all_media(self):
        """Get all media in this folder and subfolders."""
        media_ids = [m.id for m in self.media.all()]
        for child in self.children.all():
            media_ids.extend([m.id for m in child.get_all_media()])
        return Media.objects.filter(id__in=media_ids)


class Tag(models.Model):
    """Tags for categorizing media."""
    name = models.CharField(max_length=50, unique=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="tags")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["owner"]),
        ]

    def __str__(self):
        return self.name


def upload_to(instance, filename):
    """Generate upload path for media files."""
    if instance.folder:
        path = instance.folder.get_full_path()
        return f"media/{path}/{filename}"
    return f"media/root/{filename}"


class Media(models.Model):
    """Media file model with metadata."""
    
    FILE_TYPE_CHOICES = [
        ("image", "Image"),
        ("video", "Video"),
        ("audio", "Audio"),
        ("document", "Document"),
        ("other", "Other"),
    ]

    file = models.FileField(upload_to=upload_to)
    title = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    alt_text = models.CharField(max_length=255, blank=True)

    file_type = models.CharField(
        max_length=20, 
        choices=FILE_TYPE_CHOICES,
        default="other"
    )
    size = models.BigIntegerField(default=0)
    
    folder = models.ForeignKey(
        Folder,
        null=True,
        blank=True,
        related_name="media",
        on_delete=models.SET_NULL,
    )

    tags = models.ManyToManyField(Tag, blank=True, related_name="media")

    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="uploaded_media",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["uploaded_by", "created_at"]),
            models.Index(fields=["folder"]),
            models.Index(fields=["file_type"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return self.title or self.file.name

    def get_file_extension(self):
        """Get file extension."""
        return Path(self.file.name).suffix.lower()

    def get_file_size_mb(self):
        """Get file size in MB."""
        return round(self.size / (1024 * 1024), 2)