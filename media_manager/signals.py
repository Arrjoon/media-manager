from django.db.models.signals import pre_save, post_delete
from django.dispatch import receiver
from django.core.files.base import ContentFile
from pathlib import Path
import mimetypes

from media_manager.models import Media


def detect_file_type(filename, size=0):
    """Detect file type from filename and size."""
    ext = Path(filename).suffix.lower()
    mime_type, _ = mimetypes.guess_type(filename)
    
    # Image extensions
    if ext in [".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".bmp", ".tiff"]:
        return "image"
    
    # Video extensions
    if ext in [".mp4", ".avi", ".mov", ".mkv", ".flv", ".wmv", ".webm", ".m4v"]:
        return "video"
    
    # Audio extensions
    if ext in [".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a", ".wma"]:
        return "audio"
    
    # Document extensions
    if ext in [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".rtf"]:
        return "document"
    
    # Fallback to mime type detection
    if mime_type:
        if mime_type.startswith("image/"):
            return "image"
        elif mime_type.startswith("video/"):
            return "video"
        elif mime_type.startswith("audio/"):
            return "audio"
        elif mime_type.startswith("text/") or "application/pdf" in mime_type:
            return "document"
    
    return "other"


@receiver(pre_save, sender=Media)
def set_media_file_size_and_type(sender, instance, **kwargs):
    """
    Auto-set file size and file type before saving.
    """
    if instance.file:
        # Set file size
        if hasattr(instance.file, "size"):
            instance.size = instance.file.size
        
        # Set file type if not already set
        if not instance.file_type or instance.file_type == "other":
            instance.file_type = detect_file_type(instance.file.name)


@receiver(post_delete, sender=Media)
def delete_media_file(sender, instance, **kwargs):
    """
    Delete the file from storage when Media instance is deleted.
    """
    if instance.file:
        # Delete the file from storage
        if instance.file.storage.exists(instance.file.name):
            instance.file.storage.delete(instance.file.name)