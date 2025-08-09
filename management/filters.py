import django_filters
from .models import Operator, Company, Customer, Document

# Operator's filterset
class OperatorFilter(django_filters.FilterSet):
    class Meta:
        model = Operator
        fields = {
            "id": ["exact"],
            "user__first_name": ["exact", "icontains"],
            "user__last_name": ["exact", "icontains"],
            "employer__name": ["exact", "icontains"],
            "created_at": ["exact", "gt", "lt"],
            "is_deleted": ["exact"],
        }
# Company filterset
class CompanyFilter(django_filters.FilterSet):
    class Meta:
        model = Company
        fields = {
            "id": ["exact"],
            "name": ["exact", "icontains"],
            "email": ["exact", "icontains"],
            "phone_number": ["exact", "icontains"],
            "address": ["exact", "icontains"],
            "created_at": ["exact", "gt", "lt"],
            "is_deleted": ["exact"],
        }
# Customer filterset
class CustomerFilter(django_filters.FilterSet):
    class Meta:
        model = Customer
        fields = {
            "id": ["exact"],
            "user__first_name": ["exact", "icontains"],
            "user__last_name": ["exact", "icontains"],
            "created_at": ["exact", "gt", "lt"],
            "is_deleted": ["exact"],
        }
# Document filterset
class DocumentFilter(django_filters.FilterSet):
    class Meta:
        model = Document
        fields = {
            "id": ["exact"],
            "document_name": ["exact", "icontains"],
            "owner__first_name": ["exact", "icontains"],
            "owner__last_name": ["exact", "icontains"],
            "document_tag": ["exact", "icontains"],
            "image_status": ["exact", "icontains"],
            "text_status": ["exact", "icontains"],  
            "table_status": ["exact", "icontains"],
            "job_id": ["exact", "icontains"],
            "job_created_at": ["exact", "icontains"],
            "created_at": ["exact", "gt", "lt"],
            "is_deleted": ["exact"],
        }



