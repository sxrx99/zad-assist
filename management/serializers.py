from rest_framework import serializers
from core.serializers import CustomUserSerializer
from .models import (
    Customer,
    Company,
    Operator,
    Document
)


class CustomerSerializer(serializers.ModelSerializer):

    user = CustomUserSerializer()

    class Meta:
        model = Customer
        fields = ["id", "user"]
        read_only_fields = ["user"]


class SimpleCustomerSerializer(serializers.ModelSerializer):
    user__first_name = serializers.CharField(source="user.first_name")
    user__last_name = serializers.CharField(source="user.last_name")

    class Meta:
        model = Customer
        fields = ["id", "user__first_name", "user__last_name"]


class CompanySerializer(serializers.ModelSerializer):
    # owner = SimpleCustomerSerializer()

    class Meta:
        model = Company
        fields = ["id", "name", "email", "phone_number", "address"]
                  # "owner"


class SimpleCompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = ["id", "name", "email"]


class OperatorSerializer(serializers.ModelSerializer):
 #   employer = SimpleCompanySerializer()
 #   user = CustomUserSerializer()

    class Meta:
        model = Operator
        fields = ["id", "employer", "user"]
        #read_only_fields = ["user", "employer"]

    def create(self, validated_data):
        employer = validated_data.pop("employer")
        user_id = validated_data.pop("user")
        operator = Operator.objects.create(
            user_id=user_id, employer=employer, **validated_data
        )
        return operator


class SimpleOperatorSerializer(serializers.ModelSerializer):
    user__first_name = serializers.CharField(source="user.first_name")
    user__last_name = serializers.CharField(source="user.last_name")

    class Meta:
        model = Operator
        fields = ["id", "user__first_name", "user__last_name"]


class DocumentSerializer(serializers.ModelSerializer):
    owner = serializers.PrimaryKeyRelatedField(read_only=True)
    
    class Meta:
        model = Document
        fields = [
            'id',
            'owner',
            'document_file',
            'document_url',
            'document_name',
            'document_tag',
            'document_description',
            'image_status',
            'text_status',
            'table_status',
            # 'text_index_name',
            # 'image_index_name',
            'progress',
            'job_id',
            'job_created_at',
            'created_at',
            'updated_at',
            "is_deleted",
        ]
        read_only_fields = ['id', 'owner', 'created_at', 'updated_at',   'document_url','progress','image_status','text_status','table_status',
            'job_id', 'job_created_at', "is_deleted"]