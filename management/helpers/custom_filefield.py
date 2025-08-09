# app/management/helpers/custom_filefield.py
from django.db.models import FileField
from .storage import DocumentS3Storage

class DynamicStorageFileField(FileField):
    def get_storage(self, instance=None):
        storage = DocumentS3Storage()
        # Optionally log here to confirm it's called
        import logging
        logging.getLogger(__name__).info(f"DynamicStorageFileField using storage: {storage}")
        return storage