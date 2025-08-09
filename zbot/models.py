from django.conf import settings

import uuid
from django.db import models
from django.core.validators import FileExtensionValidator
from django.contrib.postgres.fields import ArrayField

from core.models import TimestampedModel, SoftDeleteModel
from management.models import Company, Customer, Operator
from .helpers.utils import image_file_size , image_upload_path
from .helpers.storage import ImageS3Storage


class Conversation(TimestampedModel, SoftDeleteModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, unique=True)
    title = models.CharField(max_length=255)
    type = models.CharField(max_length=100)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    def __str__(self):
        return self.title


# text_message mode for a conversation with text
class TextMessage(TimestampedModel, SoftDeleteModel):
    USER = "user"
    AI_AGENT = "ai"
    MESSAGE_SENDERS = [
        (USER, "user"),
        (AI_AGENT, "ai"),
    ]
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE)
    text = models.TextField()
    machine_model = models.CharField(max_length=255)
    sender = models.CharField(max_length=9, choices=MESSAGE_SENDERS, default="user")


class CustomImageField(models.ImageField):
    def __init__(self, *args, **kwargs):
        # Set max_length to 255
        self.max_length = 255
        super().__init__(*args, **kwargs)


# image_message model for a conversation with image
class ImageMessage(TimestampedModel, SoftDeleteModel):
    USER = "user"
    AI_AGENT = "ai"
    MESSAGE_SENDERS = [
        (USER, "user"),
        (AI_AGENT, "ai"),
    ]
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE)
    metadata = models.TextField(null=True, blank=True)
    # set specific  extensions for the image
    image_url = models.CharField(max_length=255, null=True)
    image = CustomImageField(
        # define maximum size of the image validator
        null=True,
        blank=True,
        storage=ImageS3Storage(),
        validators=[
            FileExtensionValidator(allowed_extensions=["jpg", "jpeg", "png", "heic"]),
            image_file_size,
        ],
        upload_to=image_upload_path,
    )
    top_k = models.PositiveIntegerField(default=1, blank=True, null=True)
    machine_model = models.CharField(max_length=255, blank= True, null=True)
    sender = models.CharField(max_length=9, choices=MESSAGE_SENDERS, default="user")

    def save(self, *args, **kwargs):
        # Save the object first to ensure the file is uploaded and has a name
        is_new = self._state.adding
        super().save(*args, **kwargs)
        # Only update image_url after the initial save and if image_file exists
        if is_new and self.image and self.image.name:
            self.image_url = self.image.url
            # Save only the image_url field to avoid recursion
            super().save(update_fields=["image_url"])

# machine model
class Machine(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    number = models.CharField(max_length=255, unique=True)
    type = models.CharField(max_length=50, null=True, blank=True)
    manufacturer = models.CharField(max_length=50, null=True, blank=True)
    production_year = models.CharField(max_length=50, null=True, blank=True)
    expiration_year = models.CharField(max_length=50, null=True, blank=True)
    def_clamping_force = models.FloatField(default=0.0)
    def_screw_diameter = models.FloatField(default=0.0)
    def_screw_stroke = models.FloatField(default=0.0)
    def_shot_volume = models.FloatField(default=0.0)
    def_max_sys_pressure = models.FloatField(default=0.0)
    def_space_tie_bars = models.CharField(max_length=255)
    def_mold_thickness = models.CharField(max_length=255)
    def_injection_pressure = models.FloatField(default=0.0)
    def_doc_index = models.CharField(max_length=255, null=True, blank=True)
    def_images_index = models.CharField(max_length=255, null=True, blank=True)
    company = models.ForeignKey(
        Company, on_delete=models.PROTECT, related_name="machines"
    )


class Material(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    type = models.CharField(max_length=255, null=True, blank=True)
    melt_density = models.FloatField(default=0.0)
    quantity = models.FloatField(default=0.0)


# machine parameter model extract fields from current_parameters
class MachineParameter(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255, null=True, blank=True)
    injection_temperature = ArrayField(
        models.FloatField(default=0.0), default=list, size=8
    )
    position = ArrayField(models.FloatField(default=0.0), default=list, size=8)
    injection_pressure = ArrayField(
        models.FloatField(default=0.0), default=list, size=8
    )
    velocity = ArrayField(models.FloatField(default=0.0), default=list, size=8)
    mold_temperature = models.FloatField(default=0.0)
    cooling_time = models.FloatField(default=0.0)
    hot_runner_temperature = models.FloatField(default=0.0)
    decompression = models.FloatField(default=0.0)
    # rotation_speed_of_screw = models.FloatField(default=0.0)
    hold_pressure = ArrayField(models.FloatField(default=0.0), default=list, size=8)
    hold_velocity = ArrayField(models.FloatField(default=0.0), default=list, size=8)
    hold_time = ArrayField(models.FloatField(default=0.0), default=list, size=8)
    back_pressure = ArrayField(models.FloatField(default=0.0), default=list, size=8)
    clamping_force = models.FloatField(default=0.0)
    injection_weight = models.FloatField(default=0.0)
    num_cavities = models.FloatField(default=0.0)
    single_prod_wieght = models.FloatField(default=0.0)
    nozzle_weight = models.FloatField(default=0.0)
    clamping_pressure = models.FloatField(default=0.0)
    material = models.ForeignKey(
        Material,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    machine = models.ForeignKey(
        Machine,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        
    )
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )


# bug reports
class BugReport(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(
        Customer, on_delete=models.PROTECT, null=True, blank=True
    )
    machine = models.ForeignKey(Machine, on_delete=models.PROTECT)
    operator = models.ForeignKey(
        Operator, on_delete=models.PROTECT, null=True, blank=True
    )
    urgency = models.CharField(
        max_length=50,
        choices=[
            ("Not Urgent", "Not Urgent"),
            ("Urgent", "Urgent"),
            ("Very Urgent", "Very Urgent"),
        ],
    )

    status = models.CharField(
        max_length=50, choices=[("Not yet", "Not yet"), ("Resolved", "Resolved")]
    )

    description = models.TextField()
    resolved_at = models.DateTimeField(null=True, blank=True)
