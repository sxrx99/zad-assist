from storages.backends.s3boto3 import S3Boto3Storage
from django.conf import settings

class ImageS3Storage(S3Boto3Storage):
    default_acl = None

    def __init__(self, *args, **kwargs):
        kwargs['bucket_name'] = getattr(settings, 'ZAD_ASSIST_BUCKET', None)
        super().__init__(*args, **kwargs)