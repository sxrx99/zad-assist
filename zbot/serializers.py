from rest_framework import serializers
from .models import (
    Conversation,
    TextMessage,
    ImageMessage,
    BugReport,
    MachineParameter,
    Machine,
    Material,
)
from management.serializers import (
    SimpleCompanySerializer,
    SimpleCustomerSerializer,
    SimpleOperatorSerializer,
)

# from rest_framework.pagination import LimitOffsetPagination


class ConversationImageMessageSerializer(serializers.ModelSerializer):
    conversation_id = serializers.CharField(read_only=True)

    class Meta:
        model = ImageMessage
        fields = [
            "id",
            "metadata",
            "image",
            "image_url",
            "machine_model",
            "sender",
            "machine_model",
            "top_k",
            "created_at",
            "updated_at",
            "conversation_id",
            "is_deleted",
        ]

        read_only_fields = ["id","conversation_id","image_url", "created_at",
            "updated_at",
            "conversation_id",
            "is_deleted"]
        extra_kwargs = {"image": {"required": "True"}}


class TextMessageSerializer(serializers.ModelSerializer):
    conversation_id = serializers.CharField(read_only=True)

    class Meta:
        model = TextMessage
        fields = [
            "id",
            "text",
            "sender",
            "is_deleted",
            "created_at",
            "updated_at",
            "conversation_id",
        ]


class ConversationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Conversation
        fields = [
            "id",
            "type",
            "name",
            "title",
            "is_deleted",
            "created_at",
            "updated_at",
        ]


class MachineSerializer(serializers.ModelSerializer):
    # company = SimpleCompanySerializer()

    class Meta:
        model = Machine
        fields = [
            "id",
            "name",
            "number",
            "type",
            "manufacturer",
            "production_year",
            "expiration_year",
            "def_clamping_force",
            "def_screw_diameter",
            "def_screw_stroke",
            "def_shot_volume",
            "def_max_sys_pressure",
            "def_space_tie_bars",
            "def_mold_thickness",
            "def_injection_pressure",
            "def_doc_index",
            "def_images_index",
            "company",
            #  "is_deleted"
        ]


class SimpleMachineSerializer(serializers.ModelSerializer):
    class Meta:
        model = Machine
        fields = ["id", "name", "number"]


class MachineParameterSerializer(serializers.ModelSerializer):
    conversation_id = serializers.CharField(read_only=True)

    class Meta:
        model = MachineParameter

        fields = [
            "id",
            "title",
            "injection_temperature",
            "position",
            "injection_pressure",
            "velocity",
            "mold_temperature",
            "cooling_time",
            "hot_runner_temperature",
            "decompression",
            "clamping_force",
            #            "rotation_speed_of_screw",
            "hold_pressure",
            "hold_velocity",
            "hold_time",
            "back_pressure",
            "num_cavities",
            "single_prod_wieght",
            "nozzle_weight",
            "clamping_pressure",
            "injection_weight",
            "material",
            "machine",
            "conversation_id",
            # "is_deleted"
        ]
        # read_only_fields = ["machine"]

    # def create(self, validated_data):
    #     # get machine id from context
    #     machine_id = self.context.get("machine_id")

    #     return MachineParameter.objects.create(machine_id=machine_id, **validated_data)


class BugReportSerializer(serializers.ModelSerializer):
    # machine = SimpleMachineSerializer()
    # customer = SimpleCustomerSerializer()
    # operator = SimpleOperatorSerializer()

    class Meta:
        model = BugReport
        fields = [
            "id",
            "customer",
            "machine",
            "operator",
            "urgency",
            "status",
            "description",
            "created_at",
            # "is_deleted"
        ]
        read_only_fields = ["customer", "machine", "operator"]


class MaterialSerializer(serializers.ModelSerializer):
    class Meta:
        model = Material
        fields = ["id", "type", "quantity", "melt_density"]


# # filter images and text nested conversation serializer
# class FilteredTextMessageSerializer(serializers.ListSerializer):
#     def to_representation(self, data):
#         request = self.context.get("request")
#         limit = request.query_params.get("limit")
#         offset = request.query_params.get("offset")
#         if limit and offset:
#             data = data[int(offset) : int(offset) + int(limit)]
#         return super().to_representation(data)


# class FilteredImageMessageSerializer(serializers.ListSerializer):
#     def to_representation(self, data):
#         request = self.context.get("request")
#         limit = request.query_params.get("limit")
#         offset = request.query_params.get("offset")
#         if limit and offset:
#             data = data[int(offset) : int(offset) + int(limit)]
#         return super().to_representation(data)
