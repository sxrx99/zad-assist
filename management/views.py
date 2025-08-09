import uuid
import logging
import requests
from django.conf import settings
from django.core.files.base import File
from rest_framework import viewsets, permissions,status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from .models import Customer, Company, Document, Operator
from .serializers import CustomerSerializer, CompanySerializer, DocumentSerializer, OperatorSerializer
from .paginations import CustomLimitOffsetPagination
from .filters import OperatorFilter, CompanyFilter, CustomerFilter, DocumentFilter
from .helpers.storage import DocumentS3Storage 
from .helpers.utils import document_upload_path

logger = logging.getLogger(__name__)

class CustomerViewSet(viewsets.ModelViewSet):
    queryset = Customer.objects.all().select_related("user")
    filterset_class = CustomerFilter
    pagination_class = CustomLimitOffsetPagination
    serializer_class = CustomerSerializer
    permission_classes = [IsAuthenticated]


class CompanyViewSet(viewsets.ModelViewSet):
    queryset = Company.objects.all().select_related("owner")
    filterset_class = CompanyFilter
    pagination_class = CustomLimitOffsetPagination
    serializer_class = CompanySerializer
    permission_classes = [IsAuthenticated]


class OperatorViewSet(viewsets.ModelViewSet):
    queryset = Operator.objects.all().select_related("employer", "user")
    filterset_class = OperatorFilter
    pagination_class = CustomLimitOffsetPagination
    serializer_class = OperatorSerializer
    permission_classes = [IsAuthenticated]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["employer_id"] = self.kwargs.get("employer_id")
        return context

    def perform_create(self, serializer):
        """Create a new operator."""
        serializer.save()

class DocumentViewSet(viewsets.ModelViewSet):
    serializer_class = DocumentSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_class = DocumentFilter
    pagination_class = CustomLimitOffsetPagination
    search_fields = ["document_name"]
    ordering_fields = ["created_at"]


    def get_queryset(self):
        user = self.request.user
        if user.is_staff or user.is_superuser:
            return Document.objects.all().select_related("owner").order_by("-created_at")
        return Document.objects.filter(owner=user, is_deleted=False).select_related("owner") .order_by("-created_at")
    
    @action(detail=False, methods=['post'], url_path='upload')
    def upload(self, request, *args, **kwargs):
        file_obj = request.FILES.get('document_file')
        if not file_obj:
            return Response({'error': 'No file provided.'}, status=status.HTTP_400_BAD_REQUEST)

        # Use dynamic storage directly
        storage = DocumentS3Storage()
        updated_name = f"v1/dataset/{uuid.uuid4()}_{file_obj.name}"
        file_obj.name = updated_name  # Set the upload path
        logger.info(f"Uploading file: {file_obj.name} to bucket: {storage.bucket_name}")
        file_name = storage.save(updated_name, file_obj)
        # Build public URL
        public_url = f"https://data-upsertions.s3.eu-west-1.amazonaws.com/{file_name}"
        logger.info(f"document url: {public_url}")
        # Create Document instance manually
        document = Document.objects.create(
            owner=request.user,
            document_url=public_url,
            document_name=request.data.get('document_name'),
            document_tag=request.data.get('document_tag', ''),
            document_description=request.data.get('document_description', ''),
            table_status="Processing",
            text_status="Processing",
            image_status="Processing",
        )
        # update the document name , current name + '-' + document id
        document.document_name = f"{document.document_name}-{document.id}"
        document.save(update_fields=["document_name"])
        #logger.info(f"document url: { document.document_url}")
        if not document:
            return Response(
                {"error": "Failed to create document instance."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        microservice_data = {
            "document_key": file_name,
            "document_name": document.document_name,
            "document_tag": document.document_tag,
            "document_description": document.document_description,
        }

        logger.info(f"microservice_data: {microservice_data}")
        # documents = []
       
        # documents.append(microservice_data)
        # data_to_upload = {
        #     "documents": documents
        # }
        microservice_url = f"{settings.DATA_UPSERTION_CONTAINER}/upload/"
        logger.info(f"Sending data to microservice: {microservice_url}")
        
        try:
            ms_response = requests.post(microservice_url, json= microservice_data, timeout=10)
            ms_response.raise_for_status()
            ms_response_data = ms_response.json()
            logger.info(f"Microservice response: {ms_response.status_code} {ms_response.text}")
        
            # Update job_id if present in microservice response
            job_id = ms_response_data.get("job_id")
            if job_id:
                document.job_id = job_id
                document.job_created_at = ms_response_data.get("job_created_at", None)
                document.save(update_fields=["job_id", "job_created_at"])

        except Exception as e:
            logger.error(f"Failed to POST to microservice: {e}")
            ms_response_data = {"error": str(e)}

        
        return Response(
            {
                "document": {
                    "id": document.id,
                    "document_url": document.document_url,
                    "document_name": document.document_name,
                    "document_tag": document.document_tag,
                    "document_description": document.document_description,
                    "progress": document.progress,
                    "image_status": document.image_status,
                    "text_status": document.text_status,
                    "table_status": document.table_status,
                    "job_id": document.job_id,                    
                },
                "response" : ms_response_data,  
            },
            status=status.HTTP_201_CREATED,
        )
    
    # @action(detail=True, methods=['get'], url_path='upload-progress')
    # def get_progress(self, request, pk=None):
    #     """
    #     Check the progress of the upsertion process for this document from the external microservice.
    #     """
    #     try:
    #         document = self.get_object()
    #         job_id = document.job_id
    #         logger.info(f"Checking progress for document {document.id} with job_id {job_id}")
    #         # Use the document ID or another identifier as needed by your microservice
    #         microservice_url = f"{settings.DATA_UPSERTION_CONTAINER}/upload/progress/{job_id}/"
    #         # convert get to post request
             
    #         # ms_response = requests.get(microservice_url, timeout=10)
    #         ms_body = {
    #             "document_name": document.document_name,
    #             "job_id": job_id,
    #         }
            
    #         ms_response = requests.post(microservice_url, json=ms_body, timeout=10)
    #         # ms_response.raise_for_status()
    #         # check if there is a key "error" in the response object
    #         if ms_response.json().get("error"):
    #             logger.error(f"Microservice returned an error:  {ms_response.json()}")
    #             return Response(
    #                 {"error": "job_id invalid."},
    #                 status=status.HTTP_404_NOT_FOUND
    #             )
    #         progress_data = ms_response.json()
    #         logger.info(f"Progress check for document {document.id}: {progress_data}")

    #         # Update the document's progress field with the value from the microservice
    #         document.progress = progress_data.get("progress", 0.0)
    #         document.image_status = progress_data.get("image_status", False)
    #         document.text_status = progress_data.get("text_status", False)
    #         document.table_status = progress_data.get("table_status", False)
    #         document.save(update_fields=["progress", "image_status", "text_status", "table_status"])
    #         logger.info(f"Document {document.id} progress updated: {document.progress}")
    #         # return current serialized data
    #         return Response(
    #             {
    #                 "document": {
    #                     "id": document.id,
    #                     "progress": document.progress,
    #                     "image_status": document.image_status,
    #                     "text_status": document.text_status,
    #                     "table_status": document.table_status,
    #                     "job_id": document.job_id,
    #                     "job_created_at": document.job_created_at,
    #                     "document_url": document.document_url,
    #                     "document_name": document.document_name,
    #                     "document_tag": document.document_tag,
    #                     "document_description": document.document_description,
    #                     "is_deleted": document.is_deleted,
    #                     "created_at": document.created_at,
    #                     "updated_at": document.updated_at,
    #                 }
    #                                 },
    #             status=status.HTTP_200_OK
    #         ) 

    #     except Exception as e:
    #         logger.error(f"Failed to check progress from microservice: {e}")
    #         progress_data = {"error": str(e)}
            
    #         return Response(
    #             {"error": "Failed to retrieve progress data."},
    #             status=status.HTTP_500_INTERNAL_SERVER_ERROR
    #         )

    # @action(detail=True, methods=['get'], url_path='get-status')
    # def get_status(self, request, pk=None):
    #     document = self.get_object() 
    #     document_name = document.document_name + '-docs'

    #     # Call the second microservice
    #     microservice_url = f"{settings.DATA_UPSERTION_CONTAINER}/upload/status/{document_name}"
    #     try:
    #         ms_response = requests.get(microservice_url, timeout=10)
    #         ms_response.raise_for_status()
    #         ms_data = ms_response.json()
    #     except requests.exceptions.Timeout:
    #         logger.error("Microservice call timed out.")
    #         return Response({"error": "Microservice call timed out."}, status=status.HTTP_504_GATEWAY_TIMEOUT)
    #     except requests.exceptions.RequestException as e:
    #         logger.error(f"Failed to get status from microservice: {e}")
    #         return Response({"error": "Failed to retrieve status from microservice."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    #     document.text_status = ms_data.get("text_status", document.text_status)
    #     document.image_status = ms_data.get("image_status", document.image_status)
    #     document.table_status = ms_data.get("table_status", document.table_status)
    #     # check for each status and update the document progress percentage
    #     # if one of them has "Upserted" status, update progress by 33.3
    #     progress = 0.0
    #     if document.text_status == "Upserted":
    #         progress += 33.3    
    #     if document.image_status == "Upserted":
    #         progress += 33.3
    #     if document.table_status == "Upserted":
    #         progress += 33.3
    #     if progress == 99.9: 
    #         progress = 100.0
    #     document.progress = progress
    #     document.save(update_fields=["text_status", "image_status", "table_status","progress"])

    #     # Return the updated document (serialized)
    #     serializer = DocumentSerializer(document)
    #     return Response({"document": serializer.data}, status=status.HTTP_200_OK)


    # unified endpoint 
    @action(detail=True, methods=['get'], url_path='update-status')
    def get_latest_status(self, request, pk=None):
        """Fetch and update document status/progress using job_id with fallback to document_name."""
        try:
            document = self.get_object()
            logger.info(f"Fetching status for document {document.id}")
            
            # Step 1: Try fetching using job_id
            job_id = document.job_id
            document_name = f"{document.document_name}-docs"
            step1_success, step1_data = self._fetch_via_job_id(job_id, document.document_name)
            
            # Step 2: Fallback to document_name if step1 fails
            if not step1_success:
                step2_success, step2_data = self._fetch_via_document_name(document_name)
                if not step2_success:
                    return Response(
                        {"error": "Failed to retrieve data from both job_id and document_name."},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    )
                self._update_document(document, **step2_data)
            else:
                self._update_document(document, **step1_data)
            
            # Save updates and return response
            document.save(update_fields=["progress", "image_status", "text_status", "table_status"])
            logger.info(
                f"Document {document.id} updated: progress={document.progress}, "
                f"image_status={document.image_status}, text_status={document.text_status}, "
                f"table_status={document.table_status}"
            )
            serializer = DocumentSerializer(document)
            return Response({"document": serializer.data}, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Unexpected error while fetching document status: {e}")
            return Response(
                {"error": "Failed to update document status."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    
    def _fetch_via_job_id(self, job_id, document_name):
        """Fetch status using job_id. Returns (success, data_dict)."""
        try:
            url = f"{settings.DATA_UPSERTION_CONTAINER}/upload/progress/{job_id}"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()

            if data.get("error") == "job_id invalid.":
                raise ValueError("job_id invalid")

            return True, {
                "progress": data.get("progress", 0.0),
                "image_status": data.get("image_status"),
                "text_status": data.get("text_status"),
                "table_status": data.get("table_status"),
            }
        except (requests.RequestException, ValueError) as e:
            logger.warning(f"JobID method failed ({e}), falling back to document_name")
            return False, None

    def _fetch_via_document_name(self, document_name):
        """Fetch status using document_name. Returns (success, data_dict)."""
        try:
            url = f"{settings.DATA_UPSERTION_CONTAINER}/upload/status/{document_name}"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # Calculate progress from statuses
            status_fields = ["image_status", "text_status", "table_status"]
            count_upserted = sum(1 for field in status_fields if data.get(field) == "Upserted")
            progress = 100.0 if count_upserted == 3 else round(count_upserted * 100 / 3, 1)
            
            return True, {
                "progress": progress,
                "image_status": data.get("image_status"),
                "text_status": data.get("text_status"),
                "table_status": data.get("table_status"),
            }
        except requests.RequestException as e:
            logger.error(f"DocumentName method failed: {e}")
            return False, None

    def _update_document(self, document, progress, image_status, text_status, table_status):
        """Update document fields with new values."""
        document.progress = progress
        document.image_status = image_status or document.image_status
        document.text_status = text_status or document.text_status
        document.table_status = table_status or document.table_status