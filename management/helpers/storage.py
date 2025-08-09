from storages.backends.s3boto3 import S3Boto3Storage
from django.conf import settings
import logging
logger = logging.getLogger(__name__)
class DocumentS3Storage(S3Boto3Storage):
    default_acl = None

    def __init__(self, *args, **kwargs):
        kwargs['bucket_name'] = getattr(settings, 'DATA_UPSERTION_BUCKET', "data-upsertions")
        # logger.info(f"DocumentS3Storage initialized with bucket: {kwargs['bucket_name']}")
        super().__init__(*args, **kwargs)