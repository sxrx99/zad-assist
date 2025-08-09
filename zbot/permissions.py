from rest_framework.permissions import BasePermission


class ViewConversationHistoryPermission(BasePermission):
    """
    Custom permission to only allow users with the 'view_conversation_history' permission to view conversation history.
    """

    def has_permission(self, request, view):
        return bool(
            request.user and request.user.has_perm("app.view_conversation_history")
        )
