from django.conf import settings
import uuid
from django.db import models
from django.core.validators import FileExtensionValidator
from core.models import TimestampedModel, SoftDeleteModel
from .helpers.storage import DocumentS3Storage  
from .helpers.custom_filefield import DynamicStorageFileField
from .helpers.utils import document_file_size, document_upload_path




# customer model
class Customer(TimestampedModel, SoftDeleteModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=False, blank=False
    )

    def __str__(self):
        return self.user.first_name + " " + self.user.last_name

    class meta:
        ordering = ["user__last_name"]


# company model
class Company(TimestampedModel, SoftDeleteModel):

    name = models.CharField(max_length=255)
    email = models.EmailField(max_length=255)
    phone_number = models.CharField(max_length=20, null=True, blank=True)
    address = models.CharField(max_length=255, null=True, blank=True)
#    owner = models.ForeignKey(Customer, on_delete=models.CASCADE, null=True, blank=True)


# Operator model
class Operator(TimestampedModel, SoftDeleteModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employer = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name="operators"
    )
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True
    )

    def __str__(self):
        return self.user.first_name + " " + self.user.last_name

    class meta:
        ordering = ["user__last_name"]


class Document(TimestampedModel, SoftDeleteModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="management_documents"
    )
    document_file = DynamicStorageFileField(
        upload_to=document_upload_path,
        validators=[
            FileExtensionValidator(allowed_extensions=["pdf"]),
            document_file_size
        ],
        blank=True,
        null=True
    )
    # document name must be unique
    document_name = models.CharField(max_length=255, unique=True)
    document_tag = models.CharField(max_length=100)
    document_url = models.CharField(max_length=255, blank=True, null=True)
    document_description = models.TextField(blank=True, null=True)
    progress = models.FloatField(default=0.0)  
    image_status = models.CharField(max_length=80)
    text_status = models.CharField(max_length=80)
    table_status = models.CharField(max_length=80)
    job_id = models.CharField(max_length=255, blank=True, null=True)
    job_created_at = models.CharField(max_length=255, blank=True, null=True)
   
    def __str__(self):
        return self.document_name

    # text_index_name = models.CharField(max_length=255, blank=True, null=True)
    # image_index_name = models.CharField(max_length=255, blank=True, null=True)
    class Meta:
        ordering = ["-created_at"]