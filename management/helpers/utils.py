from django.core.exceptions import ValidationError
import uuid

def document_file_size(value):
    max_size = 20 * 1024 * 1024  # 20 MB
    if value.size > max_size:
        raise ValidationError("File too large. Size should not exceed 20 MB.")
    


def document_upload_path(instance, filename):
    return f"v1/dataset/{uuid.uuid4()}_{filename}"