"""
Class-Based Views for Media Manager
Converted from ViewSets to traditional Django CBVs
"""

from rest_framework import permissions, status, filters, generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from django.shortcuts import get_object_or_404
from django.db.models import Q, Count

from media_manager.models import Media, Folder, Tag
from media_manager.serializers import (
    MediaListSerializer,
    MediaDetailSerializer,
    MediaCreateSerializer,
    FolderSerializer,
    FolderCreateSerializer,
    FolderNestedSerializer,
    TagSerializer,
)


# ============================================================================
# PERMISSION CLASS
# ============================================================================

class IsOwner(permissions.BasePermission):
    """Custom permission to check if user owns the object."""
    
    def has_object_permission(self, request, view, obj):
        if hasattr(obj, "owner"):
            return obj.owner == request.user
        elif hasattr(obj, "uploaded_by"):
            return obj.uploaded_by == request.user
        return False


# ============================================================================
# MEDIA VIEWS
# ============================================================================

class MediaListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/media/media/              - List all media
    POST /api/media/media/              - Create/upload media
    """
    permission_classes = [permissions.IsAuthenticated, IsOwner]
    parser_classes = (MultiPartParser, FormParser)
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["title", "description", "alt_text", "file_type"]
    ordering_fields = ["created_at", "title", "size"]
    ordering = ["-created_at"]

    def get_queryset(self):
        """Filter media by current user."""
        return Media.objects.filter(
            uploaded_by=self.request.user
        ).select_related("folder", "uploaded_by").prefetch_related("tags")

    def get_serializer_class(self):
        """Use different serializers based on action."""
        if self.request.method == "POST":
            return MediaCreateSerializer
        return MediaListSerializer

    def perform_create(self, serializer):
        """Set uploaded_by to current user during creation."""
        serializer.save(uploaded_by=self.request.user)


class MediaDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET    /api/media/media/{id}/      - Get media details
    PATCH  /api/media/media/{id}/      - Update media metadata
    DELETE /api/media/media/{id}/      - Delete media
    """
    permission_classes = [permissions.IsAuthenticated, IsOwner]
    queryset = Media.objects.all()
    serializer_class = MediaDetailSerializer
    lookup_field = "pk"

    def get_queryset(self):
        """Filter by current user."""
        return Media.objects.filter(uploaded_by=self.request.user)


class MediaByFolderView(generics.ListAPIView):
    """
    GET /api/media/media/by_folder/?folder_id=1  - Get media by folder
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = MediaListSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    ordering = ["-created_at"]

    def get_queryset(self):
        """Filter media in a specific folder."""
        folder_id = self.request.query_params.get("folder_id")
        if not folder_id:
            return Media.objects.none()
        
        folder = get_object_or_404(
            Folder,
            id=folder_id,
            owner=self.request.user
        )
        
        return Media.objects.filter(
            uploaded_by=self.request.user,
            folder=folder
        ).select_related("folder", "uploaded_by").prefetch_related("tags")


class MediaByTagView(generics.ListAPIView):
    """
    GET /api/media/media/by_tag/?tag_id=1  - Get media by tag
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = MediaListSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    ordering = ["-created_at"]

    def get_queryset(self):
        """Filter media with a specific tag."""
        tag_id = self.request.query_params.get("tag_id")
        if not tag_id:
            return Media.objects.none()
        
        tag = get_object_or_404(Tag, id=tag_id, owner=self.request.user)
        
        return Media.objects.filter(
            uploaded_by=self.request.user,
            tags=tag
        ).select_related("folder", "uploaded_by").prefetch_related("tags")


class MediaByTypeView(generics.ListAPIView):
    """
    GET /api/media/media/by_type/?type=image  - Get media by type
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = MediaListSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    ordering = ["-created_at"]

    def get_queryset(self):
        """Filter media by file type."""
        file_type = self.request.query_params.get("type")
        if not file_type:
            return Media.objects.none()
        
        return Media.objects.filter(
            uploaded_by=self.request.user,
            file_type=file_type
        ).select_related("folder", "uploaded_by").prefetch_related("tags")


class MediaStatsView(APIView):
    """
    GET /api/media/media/stats/  - Get media statistics
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """Get media statistics for current user."""
        queryset = Media.objects.filter(uploaded_by=request.user)
        
        stats = {
            "total_media": queryset.count(),
            "total_size_mb": (
                sum([m.size for m in queryset]) / (1024 * 1024)
                if queryset.exists() else 0
            ),
            "by_type": dict(
                queryset.values("file_type")
                .annotate(count=Count("id"))
                .values_list("file_type", "count")
            ),
            "by_folder": dict(
                queryset.values("folder__name")
                .annotate(count=Count("id"))
                .values_list("folder__name", "count")
            ),
        }
        return Response(stats)


class MediaAddTagsView(APIView):
    """
    POST /api/media/media/{id}/add_tags/  - Add tags to media
    """
    permission_classes = [permissions.IsAuthenticated, IsOwner]

    def post(self, request, pk):
        """Add tags to specific media."""
        media = get_object_or_404(Media, pk=pk, uploaded_by=request.user)
        tag_ids = request.data.get("tag_ids", [])
        
        tags = Tag.objects.filter(id__in=tag_ids, owner=request.user)
        media.tags.add(*tags)
        
        serializer = MediaDetailSerializer(media)
        return Response(serializer.data)


class MediaRemoveTagsView(APIView):
    """
    POST /api/media/media/{id}/remove_tags/  - Remove tags from media
    """
    permission_classes = [permissions.IsAuthenticated, IsOwner]

    def post(self, request, pk):
        """Remove tags from specific media."""
        media = get_object_or_404(Media, pk=pk, uploaded_by=request.user)
        tag_ids = request.data.get("tag_ids", [])
        
        media.tags.remove(*tag_ids)
        
        serializer = MediaDetailSerializer(media)
        return Response(serializer.data)


class MediaMoveToFolderView(APIView):
    """
    POST /api/media/media/{id}/move_to_folder/  - Move media to folder
    """
    permission_classes = [permissions.IsAuthenticated, IsOwner]

    def post(self, request, pk):
        """Move media to a different folder."""
        media = get_object_or_404(Media, pk=pk, uploaded_by=request.user)
        folder_id = request.data.get("folder_id")
        
        if folder_id:
            folder = get_object_or_404(Folder, id=folder_id, owner=request.user)
            media.folder = folder
        else:
            media.folder = None
        
        media.save()
        
        serializer = MediaDetailSerializer(media)
        return Response(serializer.data)


# ============================================================================
# FOLDER VIEWS
# ============================================================================

class FolderListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/media/folders/  - List all folders
    POST /api/media/folders/  - Create folder
    """
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name"]
    ordering = ["name"]

    def get_queryset(self):
        """Filter folders by current user."""
        return Folder.objects.filter(owner=self.request.user)

    def get_serializer_class(self):
        """Use FolderCreateSerializer for POST, FolderSerializer for GET."""
        if self.request.method == "POST":
            return FolderCreateSerializer
        return FolderSerializer

    def perform_create(self, serializer):
        """Set owner to current user during creation."""
        serializer.save(owner=self.request.user)


class FolderDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET    /api/media/folders/{id}/  - Get folder details
    PATCH  /api/media/folders/{id}/  - Update folder
    DELETE /api/media/folders/{id}/  - Delete folder
    """
    permission_classes = [permissions.IsAuthenticated, IsOwner]
    serializer_class = FolderSerializer

    def get_queryset(self):
        """Filter by current user."""
        return Folder.objects.filter(owner=self.request.user)


class FolderTreeView(APIView):
    """
    GET /api/media/folders/tree/  - Get folder hierarchy
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """Get folder tree structure (root folders with children)."""
        root_folders = Folder.objects.filter(
            owner=request.user,
            parent__isnull=True
        )
        serializer = FolderNestedSerializer(
            root_folders,
            many=True,
            context={"request": request}
        )
        return Response(serializer.data)


class FolderChildrenView(generics.ListAPIView):
    """
    GET /api/media/folders/{id}/children/  - Get child folders
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = FolderSerializer

    def get_queryset(self):
        """Get children of specific folder."""
        folder_id = self.kwargs.get("pk")
        folder = get_object_or_404(
            Folder,
            id=folder_id,
            owner=self.request.user
        )
        return folder.children.all()


class FolderMediaView(generics.ListAPIView):
    """
    GET /api/media/folders/{id}/media/  - Get media in folder
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = MediaListSerializer

    def get_queryset(self):
        """Get media in specific folder."""
        folder_id = self.kwargs.get("pk")
        folder = get_object_or_404(
            Folder,
            id=folder_id,
            owner=self.request.user
        )
        return folder.media.all()


# ============================================================================
# TAG VIEWS
# ============================================================================

class TagListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/media/tags/  - List all tags
    POST /api/media/tags/  - Create tag
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = TagSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name"]
    ordering = ["name"]

    def get_queryset(self):
        """Filter tags by current user."""
        return Tag.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        """Set owner to current user during creation."""
        serializer.save(owner=self.request.user)


class TagDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET    /api/media/tags/{id}/  - Get tag details
    PATCH  /api/media/tags/{id}/  - Update tag
    DELETE /api/media/tags/{id}/  - Delete tag
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = TagSerializer

    def get_queryset(self):
        """Filter by current user."""
        return Tag.objects.filter(owner=self.request.user)


class TagMediaCountView(APIView):
    """
    GET /api/media/tags/{id}/media_count/  - Get media count for tag
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        """Get count of media using this tag."""
        tag = get_object_or_404(Tag, id=pk, owner=request.user)
        count = tag.media.count()
        
        return Response({
            "tag_id": tag.id,
            "tag_name": tag.name,
            "media_count": count
        })


# ============================================================================
# SEARCH VIEWS (Elasticsearch)
# ============================================================================

class MediaSearchView(APIView):
    """
    GET /api/media/search/?q=sunset  - Basic full-text search
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """Search media using full-text search."""
        try:
            from media_manager.search.documents import MediaDocument
        except ImportError:
            return Response(
                {"error": "Elasticsearch not configured"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        
        query = request.query_params.get("q", "").strip()
        if not query:
            return Response(
                {"error": "Query parameter 'q' is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Search in Elasticsearch
        search = MediaDocument.search().filter(
            "term",
            uploaded_by_id=request.user.id
        ).query("multi_match", query=query, fields=[
            "title", "description", "alt_text", "file_name"
        ])
        
        results = search[:100].execute()
        
        # Get full objects from database
        media_ids = [hit.id for hit in results.hits]
        media_list = Media.objects.filter(
            id__in=media_ids,
            uploaded_by=request.user
        )
        
        serializer = MediaDetailSerializer(media_list, many=True)
        return Response({
            "count": results.hits.total.value,
            "results": serializer.data
        })


class MediaAdvancedSearchView(APIView):
    """
    GET /api/media/search/advanced/?q=photo&file_type=image&date_from=2024-01-01
    Advanced search with multiple filters
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """Advanced search with filtering."""
        try:
            from media_manager.search.documents import MediaDocument
            from elasticsearch_dsl import Q as ES_Q
        except ImportError:
            return Response(
                {"error": "Elasticsearch not configured"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        
        # Start with user filter
        search = MediaDocument.search().filter(
            "term",
            uploaded_by_id=request.user.id
        )
        
        # Text search
        query = request.query_params.get("q", "").strip()
        if query:
            search = search.query("multi_match", query=query, fields=[
                "title", "description", "alt_text", "file_name"
            ])
        
        # File type filter
        file_type = request.query_params.get("file_type")
        if file_type:
            search = search.filter("term", file_type=file_type)
        
        # Date range filter
        date_from = request.query_params.get("date_from")
        date_to = request.query_params.get("date_to")
        if date_from or date_to:
            range_query = {}
            if date_from:
                range_query["gte"] = date_from
            if date_to:
                range_query["lte"] = date_to
            search = search.filter("range", created_at=range_query)
        
        # Size range filter
        size_from = request.query_params.get("size_from")
        size_to = request.query_params.get("size_to")
        if size_from or size_to:
            range_query = {}
            if size_from:
                range_query["gte"] = int(size_from)
            if size_to:
                range_query["lte"] = int(size_to)
            search = search.filter("range", file_size=range_query)
        
        # Tag filter
        tags = request.query_params.getlist("tags")
        if tags:
            for tag in tags:
                search = search.filter(
                    "nested",
                    path="tags",
                    query=ES_Q("term", **{"tags.name": tag})
                )
        
        # Execute search
        results = search[:100].execute()
        
        # Get full objects from database
        media_ids = [hit.id for hit in results.hits]
        media_list = Media.objects.filter(
            id__in=media_ids,
            uploaded_by=request.user
        )
        
        serializer = MediaDetailSerializer(media_list, many=True)
        return Response({
            "count": results.hits.total.value,
            "results": serializer.data
        })