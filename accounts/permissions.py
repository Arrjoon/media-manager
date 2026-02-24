# permissions.py
from rest_framework.permissions import BasePermission

class IsDashboardAdmin(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and request.user.groups.filter(name="DashboardAdmin").exists()
        )
