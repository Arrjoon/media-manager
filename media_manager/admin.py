from django.contrib import admin
from django.utils.html import format_html
from media_manager.models import Media, Folder, Tag


@admin.register(Folder)
class FolderAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "parent", "media_count", "children_count", "created_at")
    list_filter = ("owner", "created_at")
    search_fields = ("name", "owner__username")
    readonly_fields = ("created_at", "updated_at", "full_path")
    fieldsets = (
        ("Basic Information", {
            "fields": ("name", "owner", "parent"),
        }),
        ("Hierarchy", {
            "fields": ("full_path",),
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )

    def full_path(self, obj):
        return obj.get_full_path()
    full_path.short_description = "Full Path"

    def media_count(self, obj):
        count = obj.media.count()
        return format_html('<span style="background-color: #e3f2fd; padding: 5px 10px; border-radius: 3px;">{}</span>', count)
    media_count.short_description = "Media Count"

    def children_count(self, obj):
        count = obj.children.count()
        return count
    children_count.short_description = "Children"


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "media_count", "created_at")
    list_filter = ("owner", "created_at")
    search_fields = ("name", "owner__username")
    readonly_fields = ("created_at",)
    fieldsets = (
        ("Basic Information", {
            "fields": ("name", "owner"),
        }),
        ("Timestamps", {
            "fields": ("created_at",),
            "classes": ("collapse",),
        }),
    )

    def media_count(self, obj):
        count = obj.media.count()
        return format_html('<span style="background-color: #f3e5f5; padding: 5px 10px; border-radius: 3px;">{}</span>', count)
    media_count.short_description = "Media Count"


@admin.register(Media)
class MediaAdmin(admin.ModelAdmin):
    list_display = (
        "title_or_filename",
        "file_type",
        "size_mb_display",
        "folder",
        "uploaded_by",
        "tags_display",
        "created_at",
    )
    list_filter = ("file_type", "created_at", "uploaded_by", "folder")
    search_fields = ("title", "file", "alt_text", "uploaded_by__username")
    readonly_fields = (
        "file",
        "size",
        "uploaded_by",
        "created_at",
        "updated_at",
        "file_preview",
    )
    filter_horizontal = ("tags",)
    
    fieldsets = (
        ("File Information", {
            "fields": ("file", "file_type", "size", "file_preview"),
        }),
        ("Metadata", {
            "fields": ("title", "description", "alt_text"),
        }),
        ("Organization", {
            "fields": ("folder", "tags"),
        }),
        ("Ownership & Dates", {
            "fields": ("uploaded_by", "created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )

    def title_or_filename(self, obj):
        return obj.title or obj.file.name
    title_or_filename.short_description = "Title"

    def size_mb_display(self, obj):
        size_mb = obj.get_file_size_mb()
        if size_mb > 100:
            color = "#c62828"
        elif size_mb > 50:
            color = "#f57c00"
        else:
            color = "#2e7d32"
        return format_html(
            '<span style="background-color: {}; color: white; padding: 5px 10px; border-radius: 3px;">{} MB</span>',
            color,
            size_mb
        )
    size_mb_display.short_description = "Size"

    def tags_display(self, obj):
        tags = obj.tags.all()
        if not tags:
            return "—"
        return format_html(
            "{}",
            ", ".join([
                format_html(
                    '<span style="background-color: #e0f2f1; color: #00695c; padding: 3px 8px; border-radius: 3px; margin-right: 5px;">{}</span>',
                    tag.name
                )
                for tag in tags
            ])
        )
    tags_display.short_description = "Tags"

    def file_preview(self, obj):
        if obj.file:
            url = obj.file.url
            ext = obj.get_file_extension().lower()
            
            if ext in [".jpg", ".jpeg", ".png", ".gif", ".webp"]:
                return format_html(
                    '<img src="{}" style="max-width: 300px; max-height: 300px;" />',
                    url
                )
            elif ext in [".mp4", ".webm", ".mov"]:
                return format_html(
                    '<video controls style="max-width: 300px; max-height: 300px;"><source src="{}" /></video>',
                    url
                )
            else:
                return format_html(
                    '<a href="{}" target="_blank">View File</a>',
                    url
                )
        return "—"
    file_preview.short_description = "Preview"

    def get_readonly_fields(self, request, obj=None):
        """Make file field readonly for existing objects."""
        if obj:
            return self.readonly_fields
        return tuple(set(self.readonly_fields) - {"file"})


class MediaInline(admin.StackedInline):
    """Inline admin for displaying media within folder admin."""
    model = Media
    extra = 0
    fields = ("title", "file_type", "size", "created_at")
    readonly_fields = ("size", "created_at")
    can_delete = False


# Optional: Add media inline to Folder admin
FolderAdmin.inlines = [MediaInline]