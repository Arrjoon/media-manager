from rest_framework import serializers
from media_manager.models import Media, Folder, Tag
from django.contrib.auth import get_user_model

User = get_user_model()


class TagSerializer(serializers.ModelSerializer):
    """Serializer for Tag model."""
    
    class Meta:
        model = Tag
        fields = ["id", "name"]
        read_only_fields = ["id"]


class UserBasicSerializer(serializers.ModelSerializer):
    """Minimal user serializer for nested display."""
    
    class Meta:
        model = User
        fields = ["id", "username", "email"]
        read_only_fields = fields


class FolderSerializer(serializers.ModelSerializer):
    """Serializer for Folder model with nested structure."""
    
    children_count = serializers.SerializerMethodField()
    media_count = serializers.SerializerMethodField()
    full_path = serializers.CharField(source="get_full_path", read_only=True)
    owner = UserBasicSerializer(read_only=True)

    class Meta:
        model = Folder
        fields = [
            "id",
            "name",
            "parent",
            "owner",
            "children_count",
            "media_count",
            "full_path",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "owner", "created_at", "updated_at"]

    def get_children_count(self, obj):
        """Get count of direct children folders."""
        return obj.children.count()

    def get_media_count(self, obj):
        """Get count of media in this folder."""
        return obj.media.count()


class FolderNestedSerializer(FolderSerializer):
    """Serializer with nested children for full tree structure."""
    
    children = serializers.SerializerMethodField()

    class Meta(FolderSerializer.Meta):
        fields = FolderSerializer.Meta.fields + ["children"]

    def get_children(self, obj):
        """Get nested children folders."""
        children = obj.children.all()
        return FolderNestedSerializer(children, many=True, context=self.context).data


class MediaListSerializer(serializers.ModelSerializer):
    """Compact serializer for listing media."""
    
    file_type_display = serializers.CharField(source="get_file_type_display", read_only=True)
    size_mb = serializers.SerializerMethodField()
    file_extension = serializers.CharField(source="get_file_extension", read_only=True)
    folder_name = serializers.CharField(source="folder.name", read_only=True)
    uploaded_by_username = serializers.CharField(source="uploaded_by.username", read_only=True)

    class Meta:
        model = Media
        fields = [
            "id",
            "title",
            "file",
            "file_type",
            "file_type_display",
            "file_extension",
            "size",
            "size_mb",
            "folder",
            "folder_name",
            "uploaded_by_username",
            "created_at",
        ]
        read_only_fields = fields

    def get_size_mb(self, obj):
        """Get file size in MB."""
        return obj.get_file_size_mb()


class MediaDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer with full relationships."""
    
    file_type_display = serializers.CharField(source="get_file_type_display", read_only=True)
    size_mb = serializers.SerializerMethodField()
    file_extension = serializers.CharField(source="get_file_extension", read_only=True)
    folder_details = FolderSerializer(source="folder", read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    uploaded_by = UserBasicSerializer(read_only=True)

    class Meta:
        model = Media
        fields = [
            "id",
            "title",
            "description",
            "file",
            "alt_text",
            "file_type",
            "file_type_display",
            "file_extension",
            "size",
            "size_mb",
            "folder",
            "folder_details",
            "tags",
            "uploaded_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "file",
            "size",
            "uploaded_by",
            "created_at",
            "updated_at",
        ]

    def get_size_mb(self, obj):
        """Get file size in MB."""
        return obj.get_file_size_mb()


class MediaUploadSerializer(serializers.Serializer):
    """Serializer for media upload with validation."""
    
    file = serializers.FileField(required=True)
    folder = serializers.PrimaryKeyRelatedField(
        queryset=Folder.objects.all(),
        required=False,
        allow_null=True
    )
    title = serializers.CharField(max_length=255, required=False, allow_blank=True)
    description = serializers.CharField(required=False, allow_blank=True)
    alt_text = serializers.CharField(max_length=255, required=False, allow_blank=True)
    file_type = serializers.ChoiceField(
        choices=Media._meta.get_field("file_type").choices,
        required=False
    )
    tag_names = serializers.ListField(
        child=serializers.CharField(max_length=50),
        required=False,
        allow_empty=True
    )

    def validate_file(self, value):
        """Validate file size (max 500MB)."""
        max_size = 500 * 1024 * 1024  # 500MB
        if value.size > max_size:
            raise serializers.ValidationError(
                f"File size ({value.size / (1024*1024):.2f}MB) exceeds maximum of 500MB."
            )
        return value

    def validate_folder(self, value):
        """Validate folder ownership."""
        request = self.context.get("request")
        if value and value.owner != request.user:
            raise serializers.ValidationError("You don't have permission to use this folder.")
        return value

    def validate_tag_names(self, value):
        """Validate tag names."""
        if len(value) > 10:
            raise serializers.ValidationError("Maximum 10 tags allowed per media.")
        return value


class MediaCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating media with validation."""
    
    tag_ids = serializers.PrimaryKeyRelatedField(
        queryset=Tag.objects.all(),
        many=True,
        required=False,
        source="tags"
    )

    class Meta:
        model = Media
        fields = [
            "file",
            "title",
            "description",
            "alt_text",
            "file_type",
            "folder",
            "tag_ids",
        ]

    def create(self, validated_data):
        """Create media instance with proper owner assignment."""
        validated_data["uploaded_by"] = self.context["request"].user
        
        # Extract tags for M2M relationship
        tags = validated_data.pop("tags", [])
        
        media = Media.objects.create(**validated_data)
        media.tags.set(tags)
        return media


class FolderCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating folders."""
    
    class Meta:
        model = Folder
        fields = ["name", "parent"]

    def create(self, validated_data):
        """Create folder with owner from request."""
        validated_data["owner"] = self.context["request"].user
        return super().create(validated_data)

    def validate_parent(self, value):
        """Validate parent folder ownership."""
        request = self.context.get("request")
        if value and value.owner != request.user:
            raise serializers.ValidationError("You don't have permission to use this folder.")
        return value