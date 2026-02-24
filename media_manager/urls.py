from django.urls import path
from media_manager.views import (
    MediaListCreateView, MediaDetailView, MediaByFolderView, MediaByTagView, MediaByTypeView,
    MediaStatsView, MediaAddTagsView, MediaRemoveTagsView, MediaMoveToFolderView,
    FolderListCreateView, FolderDetailView, FolderTreeView, FolderChildrenView, FolderMediaView,
    TagListCreateView, TagDetailView, TagMediaCountView,
    MediaSearchView, MediaAdvancedSearchView
)

app_name = "media_manager"

urlpatterns = [
    # ========== MEDIA ENDPOINTS ==========
    path("media/", MediaListCreateView.as_view(), name="media-list-create"),
    path("media/<int:pk>/", MediaDetailView.as_view(), name="media-detail"),
    path("media/by_folder/", MediaByFolderView.as_view(), name="media-by-folder"),
    path("media/by_tag/", MediaByTagView.as_view(), name="media-by-tag"),
    path("media/by_type/", MediaByTypeView.as_view(), name="media-by-type"),
    path("media/stats/", MediaStatsView.as_view(), name="media-stats"),
    path("media/<int:pk>/add_tags/", MediaAddTagsView.as_view(), name="media-add-tags"),
    path("media/<int:pk>/remove_tags/", MediaRemoveTagsView.as_view(), name="media-remove-tags"),
    path("media/<int:pk>/move_to_folder/", MediaMoveToFolderView.as_view(), name="media-move-to-folder"),

    # ========== FOLDER ENDPOINTS ==========
    path("folders/", FolderListCreateView.as_view(), name="folder-list-create"),
    path("folders/<int:pk>/", FolderDetailView.as_view(), name="folder-detail"),
    path("folders/tree/", FolderTreeView.as_view(), name="folder-tree"),
    path("folders/<int:pk>/children/", FolderChildrenView.as_view(), name="folder-children"),
    path("folders/<int:pk>/media/", FolderMediaView.as_view(), name="folder-media"),

    # ========== TAG ENDPOINTS ==========
    path("tags/", TagListCreateView.as_view(), name="tag-list-create"),
    path("tags/<int:pk>/", TagDetailView.as_view(), name="tag-detail"),
    path("tags/<int:pk>/media_count/", TagMediaCountView.as_view(), name="tag-media-count"),

    # ========== SEARCH ENDPOINTS ==========
    path("search/", MediaSearchView.as_view(), name="media-search"),
    path("search/advanced/", MediaAdvancedSearchView.as_view(), name="media-advanced-search"),
]