# media_manager/search.py
from .documents import MediaDocument


class MediaSearchService:

    @staticmethod
    def search(query=None, file_type=None, folder=None, tags=None):
        qs = MediaDocument.search()

        if query:
            qs = qs.query(
                "multi_match",
                query=query,
                fields=[
                    "title^3",
                    "description^2",
                    "alt_text",
                    "file_name",
                    "tags.name",
                    "folder_path",
                ],
                fuzziness="AUTO"
            )

        if file_type:
            qs = qs.filter("term", file_type=file_type)

        if folder:
            qs = qs.filter("term", folder_name=folder)

        if tags:
            qs = qs.filter("terms", tags__name=tags)

        qs = qs.sort("-created_at")

        return qs