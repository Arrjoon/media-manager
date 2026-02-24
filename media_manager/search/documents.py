from django_elasticsearch_dsl import Document, fields, Index
from django_elasticsearch_dsl.registries import registry
from media_manager.models import Media, Tag, Folder

# Create custom index with settings
media_index = Index("media", using="default")
media_index.settings(
    number_of_shards=1,
    number_of_replicas=0,
    analysis={
        "analyzer": {
            "default": {
                "type": "standard",
                "stopwords": "_english_"
            },
            "autocomplete": {
                "type": "custom",
                "tokenizer": "standard",
                "filter": ["lowercase", "stop"]
            }
        }
    }
)


@registry.register_document
class MediaDocument(Document):
    """Elasticsearch document for Media model with full-text search."""
    
    # Basic fields
    title = fields.TextField(
        analyzer="autocomplete",
        fields={"keyword": fields.KeywordField()}
    )
    description = fields.TextField(analyzer="standard")
    alt_text = fields.TextField()
    file_type = fields.KeywordField()
    
    # File info - NOTE: 'size' is handled by Django class, use file_size for custom mapping
    file_name = fields.TextField(
        attr="file.name",
        analyzer="standard",
        fields={"keyword": fields.KeywordField()}
    )
    file_size = fields.IntegerField(attr="size")
    file_extension = fields.KeywordField(attr="get_file_extension")
    
    # Relationships
    folder_name = fields.KeywordField(attr="folder.name")
    folder_path = fields.TextField(attr="folder.get_full_path")
    tags = fields.NestedField(
        properties={
            "id": fields.IntegerField(),
            "name": fields.KeywordField()
        }
    )
    uploaded_by_username = fields.KeywordField(attr="uploaded_by.username")
    uploaded_by_id = fields.IntegerField(attr="uploaded_by.id")
    
    # Timestamps
    created_at = fields.DateField()
    updated_at = fields.DateField()

    class Index:
        name = "media"
        settings = {
            "number_of_shards": 1,
            "number_of_replicas": 0,
        }

    class Django:
        model = Media
        # IMPORTANT: Do NOT include 'size' here since we map it to 'file_size' above
        # IMPORTANT: Do NOT include fields that are explicitly defined above
        fields = [
            "id",
        ]

    def prepare_tags(self, instance):
        """Prepare tags for nested field."""
        return [{"id": tag.id, "name": tag.name} for tag in instance.tags.all()]

    def prepare_file_extension(self, instance):
        """Prepare file extension."""
        return instance.get_file_extension()

    def prepare_folder_path(self, instance):
        """Prepare full folder path."""
        return instance.folder.get_full_path() if instance.folder else "root"