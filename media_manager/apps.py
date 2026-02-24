from django.apps import AppConfig


class MediaManagerConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "media_manager"
    verbose_name = "Media Manager"

    def ready(self):
        """Import signals when app is ready."""
        import media_manager.signals