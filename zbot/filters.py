import django_filters
from .models import Conversation, Machine, MachineParameter


# Conversation's filterset
class ConversationFilter(django_filters.FilterSet):
    class Meta:
        model = Conversation
        fields = {
            "id": ["exact"],
            "type": ["exact"],
            "name": ["exact", "contains"],
            "user_id": ["exact"],
            "type": ["exact"],
            "title": ["exact", "contains"],
            "created_at": ["exact", "gt", "lt"],
            "is_deleted": ["exact"],
        }  # fields to filter by


# MachineParameter's filterset


class MachineParameterFilter(django_filters.FilterSet):
    class Meta:
        model = MachineParameter
        fields = {
            "id": ["exact"],
            "title": ["exact", "contains"],
            "conversation": ["exact"],
            "created_at": ["exact", "gt", "lt"],
        }
        

class MachineFilter(django_filters.FilterSet):
    class Meta:
        model = Machine
        fields = {
            "id": ["exact"],
            "name": ["exact", "icontains"],
            "number": ["exact", "icontains"],
            "type": ["exact", "icontains"],
            "manufacturer": ["exact", "icontains"],
            "production_year": ["exact"],          
        }
