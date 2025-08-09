import time
import json
import ast
import math
import logging
import threading
import queue
from django.conf import settings

from datetime import datetime

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import uuid

# import httpx

from django.http import StreamingHttpResponse
from django.views.decorators.csrf import csrf_protect
from django.core.files.storage import default_storage
from django.shortcuts import get_object_or_404
from django.core.exceptions import ObjectDoesNotExist


from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import action, renderer_classes
from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated
from rest_framework.filters import SearchFilter, OrderingFilter

from django_filters.rest_framework import DjangoFilterBackend

# from channels.db import database_sync_to_async

# from .permissions import ViewConversationHistoryPermission
from .serializers import (
    ConversationSerializer,
    TextMessageSerializer,
    
    ConversationImageMessageSerializer,
    MachineSerializer,
    MachineParameterSerializer,
    BugReportSerializer,
    MaterialSerializer,
    # ConversationHistorySerializer,
)
from .models import (
    Conversation,
    TextMessage,
    ImageMessage,
    Machine,
    MachineParameter,
    BugReport,
    Material,
)
from aws_xray_sdk.core import xray_recorder
from .helpers.sse_renderer import ServerSentEventRenderer
from .helpers.utils import (
    get_conversation_history,
    get_history_for_ai,
    split_s3_url,
    restructure_images,
)
from .filters import ConversationFilter, MachineParameterFilter, MachineFilter  
from .paginations import CustomLimitOffsetPagination

from core.decorators import use_db_pool

logger = logging.getLogger(__name__)

retry_strategy = Retry(
    total=5,
    backoff_factor=10,
    status_forcelist=[500, 502, 503, 504],
    method_whitelist=["GET", "POST"],
)

# Create an adapter with the retry strategy
adapter = HTTPAdapter(max_retries=retry_strategy)

# Set up a session and mount the adapter
session = requests.Session()
session.mount("http://", adapter)
session.mount("https://", adapter)

response_queue = queue.Queue()


# @csrf_protect

@xray_recorder.capture("ConversationViewSet")
class ConversationViewSet(ModelViewSet):
    serializer_class = ConversationSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = ConversationFilter
    pagination_class = CustomLimitOffsetPagination
    search_fields = ["name", "title"]
    ordering_fields = ["created_at", "name"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):  # drf-yasg comp
            return Conversation.objects.none()
        """Retrieve conversations for authenticated user"""
        # filter out deleted
        return Conversation.objects.filter(user=self.request.user).order_by(
            "-created_at"
        )
    
    def perform_create(self, serializer):
        """Create a new conversation."""
        serializer.save(user=self.request.user)

    # define history action with pagination
    @action(detail=True, methods=["GET"], url_path="history")
    def history(self, request, pk=None):
        """Retrieve conversation history."""
        try:
            limit = int(request.query_params.get("limit", 10))
            start = int(request.query_params.get("start", 0))
            history = get_conversation_history(pk, limit, start)
            conversation_history = history[0]
            total_count = history[1]
            # logger.info(f"Retrieved conversation history: {conversation_history}")

            # Use your custom pagination class
            paginator = CustomLimitOffsetPagination()
            paginator.count = total_count
            paginator.offset = start
            paginator.limit = limit
            paginator.request = request
            # paginated_history = paginator.get_paginated_response(conversation_history)

            # Return paginated response
            return paginator.get_paginated_response(conversation_history)
        except Exception as e:
            logger.critical(
                f"Failed to retrieve conversation history for Conversation {pk}: {str(e)}"
            )
            return Response(
                {"detail": "Failed to retrieve conversation history."}, status=500
            )

    @action(detail=False, methods=["post"])
    def calculate_parameters(self, request, *args, **kwargs):
        frontend_data = request.data

        single_product_weight = frontend_data.get("product_weight")
        number_of_cavities = frontend_data.get("num_of_cavities")
        nozzle_weight = frontend_data.get("nozzle_weight")
        clamping_pressure = frontend_data.get("clamping_pressure")
        machine = Machine.objects.filter(id=frontend_data.get("machine_id")).first()
        material = Material.objects.filter(id=frontend_data.get("material_id")).first()

        required_params = [
            #    conversation_id,
            machine,
            material,
            single_product_weight,
            number_of_cavities,
            nozzle_weight,
            clamping_pressure,
        ]
        if any(param is None for param in required_params):
            return Response(
                {"error": "Missing required parameters"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # claculate parameters
        pi = math.pi
        r = machine.def_screw_diameter / 2
        p_r_sqrt = pi * (r**2)

        material_density = material.melt_density
        volume = (p_r_sqrt * machine.def_screw_stroke) / 1000
        shot_weight = volume * material_density

        wieght_injected = (single_product_weight * number_of_cavities) + nozzle_weight
        injected_volume = (wieght_injected * machine.def_shot_volume) / shot_weight

        injected_weight = (injected_volume / p_r_sqrt) * 1000
        clamping_force_bar = (
            clamping_pressure * machine.def_max_sys_pressure * 10
        ) / machine.def_clamping_force
        response = {
            "injected_weight": injected_weight,
            "clamping_force_bar": clamping_force_bar,
        }
        return Response(response, status=status.HTTP_200_OK)
    def get_ai_endpoint(self, request):
        app_version = request.query_params.get("appVersion")
        if app_version == "tcg":
            return settings.ZAD_TCG_CONTAINER
        if app_version == "yizumi":
            return settings.ZAD_ASSIST_CONTAINER
        return settings.ZAD_ASSIST_CONTAINER
    @action(detail=True, methods=["POST"], url_path="redirect")
    def redirect(self, request, pk=None):
        """Redirect frontend requests to the AI agent service."""
        # Example frontend data for testing
        frontend_data = request.data  # Get data from the frontend POST request
        # frontend_data = {
        # "textQuery": {  
        #                 "id" : 5 ,
        #                 "text" : "What's the machanical structure of a clamping unit for my machine"
        #               },
        # "machineType": "Yizumi PAC 460 k3",
        # "imageQuery": {
        #        "id" : "116",
        #       "image_url": "https://example.com/image.jpg"
        # },
        # "chatHistory": [
        #     {
        #     "role": "user",
        #     "message": "what is injection molding?"
        #     },
        #     {
        #     "role": "ai",
        #     "message": "it's when we use molten plastic and inject it into molds to make plastic products."
        #     }
        #     ]
        # }
        #       logger.info(f"Received message from frontend: {frontend_data}")

        if (
            not frontend_data
            or not frontend_data.get("textQuery")
            or not frontend_data.get("machineType")
        ):
            return Response(
                {
                    "detail": "Message must be changed.",
                    "data": frontend_data,
                },  # Combine messages and data in a dict
                status=status.HTTP_400_BAD_REQUEST,
            )
        # Retrieve the conversation instance
        try:
            conversation = self.get_object()
        except Conversation.DoesNotExist:
            return Response("Conversation not found.", status=status.HTTP_404_NOT_FOUND)

        # Save the frontend message to the database

        received_text = frontend_data.get("textQuery", None)
        textQuery = None
        if received_text and type(received_text) is not dict:
            textQuery = received_text["text"]
            text_query_id = received_text["id"]
        else:
            return Response("The question not found.", status=status.HTTP_404_NOT_FOUND)

        machine_model = frontend_data.get("machineType", "Yizumi PAC 460 k3")
        recieved_image_query = frontend_data.get("imageQuery", None)
        imageQuery = None
        if recieved_image_query:
            imageQuery = split_s3_url(recieved_image_query["image_url"])
        #        logger.info(f"Image query object: {imageQuery}")
        chatHistory = get_history_for_ai(text_query_id, conversation.id, "chat")

        try:

            # logger.info(
            #     "Sent message from frontend: "
            #     "textQuery: %s, machine_type: %s, imageQuery: %s, chatHistory: %s",
            #     textQuery,
            #     machine_model,
            #     imageQuery,
            #     chatHistory,
            # )
            request_body = {
                "textQuery": textQuery,
                "imageQuery": imageQuery,
                "machineType": machine_model,
                "chatHistory": chatHistory,
                # get_conversation_history(pk)
            }
            start_time = time.time()
            ai_endpoint = self.get_ai_endpoint(request)
            react_agent_response = session.post(
                f"{ai_endpoint}/chat",
                json=request_body,
                #                    "image_query":image_query,
                timeout=50,  # 50 seconds timeout
            )
            elapsed_time = time.time()

            # {
            # "response": "Could you please provide more details about the problem you're experiencing? If it's related to a YIZUMI injection molding machine, any specific error codes, symptoms, or issues you're encountering would be helpful. This information will allow me to assist you more effectively.",
            # "images": {
            #     "images": [],
            #     "descriptions": [],
            #     "utilities": []
            # }

            # logger.info(
            #     f"Response from AI agent: {react_agent_response.json()}, user id : {self.request.user} elapsed time: {elapsed_time - start_time} seconds"
            # )

            # Handle the response based on content type
            if react_agent_response.status_code == 200:
                content_type = react_agent_response.headers.get("Content-Type")
                if "application/json" == content_type:
                    # Save the text response to the database
                    response_text = react_agent_response.json().get("response", None)
                    response_images = react_agent_response.json().get("images", None)
                    # logger.info(
                    #     f"Response list of images: {response_images}, Type: {type(response_images)}"
                    # )
                    image_input_desc = None
                    if recieved_image_query:
                        image_input_desc = react_agent_response.json().get(
                            "imageInputDescription", None
                        )

                    # update the imageMessage in the database with it description
                    if image_input_desc:
                        imageMessage = ImageMessage.objects.get(
                            id=recieved_image_query["id"]
                        )
                        # logger.info(f"Received image description: {image_input_desc}")
                        imageMessage.metadata = image_input_desc
                        imageMessage.save()

                    images = restructure_images(response_images)
                    # logger.info(f"Structured images: {images}, Type: {type(images)}")
                    serialized_text = None
                    serialized_image = None

                    if response_text:
                        response_text = TextMessage.objects.create(
                            conversation=conversation,
                            text=response_text,
                            machine_model=machine_model,
                            sender="ai",
                        )

                        # Serialize the created object
                        serialized_text = TextMessageSerializer(response_text)
                        # logger.info(
                        #     f"Saved text response from AI agent: {serialized_text.data}"
                        # )

                    serialized_images = []
                    if images is not None:
                        for image in images:
                            #                            metadata = str({"description": image["description"] })
                            # logger.info(
                            #     f"structured image in the list  : {image} , Type: {type(image)}"
                            # )
                            image_url_ai = image.get("image_url")
                            image_desc_ai = image.get("description")
                            image_util_ai = image.get("utility")
                            response_image = ImageMessage.objects.create(
                                conversation=conversation,
                                image_url=image_url_ai,
                                metadata=f"description:{image_desc_ai}|utility:{image_util_ai}",
                                machine_model=machine_model,
                                sender="ai",
                            )
                            # Serialize the created object
                            serialized_image = ConversationImageMessageSerializer(
                                response_image
                            )
                            # logger.info(
                            #     f"Saved image response from AI agent: {serialized_image.data}"
                            # )
                            serialized_images.append(serialized_image.data)
                    # Return the serialized response
                    final_response_time = time.time()
                    # logger.info(
                    #     f"Final response time : {final_response_time -elapsed_time} seconds"
                    # )
                    zbot_time = elapsed_time - start_time
                    django_time = final_response_time - elapsed_time

                    logger.info(f"user id : {self.request.user.id}, zbot time : {zbot_time} , django time : {django_time}")
                    response_data = {
                        "response": {
                            "text": serialized_text.data if serialized_text else None,
                            "image": serialized_images,
                        },
                        "timer": {"zbot_time": zbot_time, "django_time": django_time},
                    }

                    return Response(response_data, status=status.HTTP_200_OK)

                else:
                    return Response(
                        "Unsupported content type in AI agent response.",
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            else:
                return Response(
                    f"Error: {react_agent_response.status_code}",
                    status=status.HTTP_400_BAD_REQUEST,
                )

        except requests.exceptions.Timeout:
            logger.error("Request to AI agent timed out.")
            return Response(
                "Request timed out. Please try again later.",
                status=status.HTTP_400_BAD_REQUEST,
            )
        except requests.RequestException as e:
            logger.error(f"Error communicating with AI agent: {str(e)}")
            return Response(f"Error: {str(e)}", status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["POST"], url_path="ops-streamsse")
    @renderer_classes([ServerSentEventRenderer])
    def ops_streamsse(self, request, pk=None):
        """Redirect frontend requests to the AI agent service."""
        # Example frontend data for testing
        frontend_data = request.data  # Get data from the frontend POST request
        # frontend_data = {
        # "textQuery": {  
        #                 "id" : 5 ,
        #                 "text" : "What's the machanical structure of a clamping unit for my machine"
        #               },
        # "machineType": "Yizumi PAC 460 k3",
        # {
        #     "initParameters": {
        #         "machine_id": "machine_id",
        #         "machine_name": "machine_name",
        #         "material_id": "material_id",
        #         "material_name": "material_name",
        #         "clamping_pressure": 0,
        #         "number_of_cavities": 0,
        #         "product_weight": 0,
        #         "nozzle_weight": 0,
        #     },
        #     "finetunableParameters": {
        #         "injection_temperature": [0, ...],
        #         "position": [0 ,...],
        #         "injection_pressure":  [0, ...],
        #         "velocity":  [0, ...],
        #         "mold_temperature": 0,
        #         "cooling_time": 0,
        #         "hot_runner_temperature": 0,
        #         "decompression": 0,
        #         "injected_weight": 0,
        #         "clamping_force": 0,
        #         "hold_pressure": [0],
        #         "hold_velocity": [0],
        #         "hold_time": [0],
        #         "back_pressure": [0],
        #         },
        #     "textQuery " : "textQuery"
        #     }
        # Retrieve the conversation instance
        try:
            conversation = self.get_object()
        except Conversation.DoesNotExist:
            return Response("Conversation not found.", status=status.HTTP_404_NOT_FOUND)

        # Save the frontend message to the database

        received_text = frontend_data.get("textQuery", None)
        textQuery = None
        if received_text and "id" in received_text and "text" in received_text:
            textQuery = received_text["text"]
            text_query_id = received_text["id"]
        else:
            return Response(
                "The question not found.",
                status=status.HTTP_404_NOT_FOUND,
            )

        received_image_query = frontend_data.get("imageQuery", None)
        parameters_id = frontend_data.get("parameterId", None)
        if frontend_data is None or textQuery is None or parameters_id is None:
            return Response(
                {
                    "detail": " text message , fine tunable parameters must be provided.",
                    "data": frontend_data,
                },  # Combine messages and data in a dict
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            current_parameters = (
                MachineParameter.objects.filter(id=parameters_id)
                .select_related("machine", "material")
                .get()
            )
            print(f"MachineParameter ID: {current_parameters.id}")
            print(f"Machine Name: {current_parameters.machine.name}")
            print(f"Material Name: {current_parameters.material.type}")
        except ObjectDoesNotExist:
            return Response(
                {
                    "detail": "Machine parameters not found.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # logger.info(f"current_parameters: {current_parameters}")

        init_parameters_list = [
            current_parameters.clamping_pressure,
            current_parameters.num_cavities,
            current_parameters.single_prod_wieght,
            current_parameters.nozzle_weight,
        ]
        verified_init_params = all(
            (isinstance(value, float) or isinstance(value, int))
            for value in init_parameters_list
        )

        fine_tunable_parameters_lists = [
            current_parameters.injection_temperature,
            current_parameters.position,
            current_parameters.injection_pressure,
            current_parameters.velocity,
            current_parameters.hold_pressure,
            current_parameters.hold_velocity,
            current_parameters.hold_time,
            current_parameters.back_pressure,
        ]
        fine_tunable_parameters_lists_v = True
        for i in range(len(fine_tunable_parameters_lists)):
            param = fine_tunable_parameters_lists[i]
            if (
                not isinstance(param, list) or len(param) == 0
            ):  # Check if it's not a list or if it's empty
                fine_tunable_parameters_lists_v = False

        fine_tunable_parameters_floats = [
            current_parameters.mold_temperature,
            current_parameters.cooling_time,
            current_parameters.hot_runner_temperature,
            current_parameters.decompression,
            current_parameters.clamping_force,
        ]

        fine_tunable_parameters_floats_v = all(
            (isinstance(value, float) or isinstance(value, int))
            for value in fine_tunable_parameters_floats
        )
        if (
            not verified_init_params
            or not fine_tunable_parameters_lists_v
            or not fine_tunable_parameters_floats_v
        ):
            part = ""
            if not verified_init_params:
                part += "initial "
            if not fine_tunable_parameters_lists_v:
                part += "fine lists "
            if not fine_tunable_parameters_floats_v:
                part += "fine floats "
            return Response(
                {
                    "detail": f" Parameters must be updated correctly. {part}",
                    "data": frontend_data,
                },  # Combine messages and data in a dict
                status=status.HTTP_400_BAD_REQUEST,
            )

        machine_model = current_parameters.machine.name
        material_name = current_parameters.material.type

        # imageQuery = None
        # if received_image_query:
        #     imageQuery = split_s3_url(received_image_query["image_url"])
        #        logger.info(f"Image query object: {imageQuery}")

        chatHistory = get_history_for_ai(text_query_id, conversation.id, "ops")

        # logger.info(
        #     "Sent message from frontend: "
        #     "textQuery: %s, machine_type: %s, imageQuery: %s, chatHistory: %s",
        #     textQuery,
        #     machine_model,
        #     imageQuery,
        #     chatHistory,
        # )

        request_body = {
            "initParameters": {
                "material_name": material_name,
                "machine_name": machine_model,
                "f_mouliste": current_parameters.clamping_pressure,
                "number_of_cavities": current_parameters.num_cavities,
                "product_weight": current_parameters.single_prod_wieght,
                "nozzle_weight": current_parameters.nozzle_weight,
            },
            "finetunableParameters": {
                "injection_temperature": current_parameters.injection_temperature,
                "position": current_parameters.position,
                "injection_pressure": current_parameters.injection_pressure,
                "velocity": current_parameters.velocity,
                "mold_temperature": current_parameters.mold_temperature,
                "cooling_time": current_parameters.cooling_time,
                "hot_runner_temperature": current_parameters.hot_runner_temperature,
                "decompression": current_parameters.decompression,
                "injected_weight": current_parameters.injection_weight,
                "clamping_force": current_parameters.clamping_force,
                "hold_pressure": current_parameters.hold_pressure,
                "hold_velocity": current_parameters.hold_velocity,
                "hold_time": current_parameters.hold_time,
                "back_pressure": current_parameters.back_pressure,
            },
            "engFeedback": textQuery,
            "chatHistory": chatHistory,
        }

        # json_request_body = json.dumps(request_body, indent=4)
        # Log the formatted JSON
        # logger.info("Request body:\n%s", json_request_body)

        # logger.info( "request body %s ",type(json_request))
        ai_endpoint = self.get_ai_endpoint(request)
        response = StreamingHttpResponse(
            self.stream_response(
                "ops",
                "text",
                request_body,
                conversation,
                machine_model,
                received_image_query,
                user_id=self.request.user.id,
                ai_endpoint=ai_endpoint,
            )
        )
        response["X-Accel-Buffering"] = "no"  # Disable buffering in nginx
        response["Cache-Control"] = "no-cache"  # Ensure clients don't cache the data
        response["Content-Type"] = "text/event-stream"
        return response
    
    @action(detail=True, methods=['post'], url_path='similarity_search')
    def similarity_search(self, request, *args, **kwargs):
        """Perform similarity search on an image message."""
        # Retrieve the conversation instance
        conversation = Conversation.objects.filter(
            id=self.kwargs.get("pk"),
            is_deleted=False
        ).first()
        if not conversation:
            return Response(
                {"detail": "Conversation not found."},
                status=status.HTTP_400_BAD_REQUEST
            )
        # Validate the request data

       
        image = ImageMessage.objects.filter(
            id=request.data.get("image_id"),
            is_deleted=False
        ).first()
        if not image:
            return Response(
                {"detail": "Image message  not found."},
                status=status.HTTP_400_BAD_REQUEST
                )
        
        image_to_send = {
            "bucket": "zbot-image-input-v1",
            "key": image.image_url.split(".amazonaws.com/")[-1],
        }
        # Build the microservice_data dictionary 
        microservice_data = {
            "image":  image_to_send,
            "top_k":  request.data.get("top_k", 1),
        }

        microservice_url = f"{settings.CUSTOMIZATION_GROUP_CONTAINER}/search/"
        logger.info(f"Sending data to microservice: {microservice_url}")
        
        try:
            ms_response = requests.post(microservice_url, json= microservice_data, timeout=10)
            ms_response.raise_for_status()
            ms_response_data = ms_response.json()
            retrieved_images = ms_response_data.get("retrieved_images", [])
            for retrieved_image in retrieved_images:
                metadata = retrieved_image.get("metadata", {})
                # Convert metadata dict to markdown string
                markdown_lines = []
                for k, v in metadata.items():
                    markdown_lines.append(f"### {k}\n{v}\n")
                # Join all lines into a single string
                retrieved_image["metadata"] = "\n".join(markdown_lines)
            logger.info(f"Microservice response: {ms_response.status_code} {ms_response.text}")
            
            # create CustomImage instances for each retrieved image
            for retrieved_image in retrieved_images:
                ImageMessage.objects.create(
                    conversation=conversation,
                    top_k=1, 
                    image_url=retrieved_image.get("url"),
                    metadata=retrieved_image.get("metadata"),
                    sender="ai",
                )
        except Exception as e:
            logger.error(f"Failed to POST to microservice: {e}")
            ms_response_data = {"error": str(e)}

        return Response( 
            ms_response_data,  
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["POST"], url_path="streamsse")
    @renderer_classes([ServerSentEventRenderer])
    def streamsse(self, request, pk=None):
        """Redirect frontend requests to the AI agent service."""
        # Example frontend data for testing
        frontend_data = request.data  # Get data from the frontend POST request
        # frontend_data = {
        # "textQuery": {  
        #                 "id" : 5 ,
        #                 "text" : "What's the machanical structure of a clamping unit for my machine"
        #                 },
        # "machineType": "Yizumi PAC 460 k3",
        # "imageQuery": {
        #        "id" : "116",
        #       "image_url": "https://example.com/image.jpg"
        # },
        # "chatHistory": [
        #     {
        #     "role": "user",
        #     "message": "what is injection molding?"
        #     },
        #     {
        #     "role": "ai",
        #     "message": "it's when we use molten plastic and inject it into molds to make plastic products."
        #     }
        #     ]
        # }
        #       logger.info(f"Received message from frontend: {frontend_data}")

        if (
            not frontend_data
            or not frontend_data.get("textQuery")
            or not frontend_data.get("machineType")
        ):
            return Response(
                {
                    "detail": "Message must be changed.",
                    "data": frontend_data,
                },  # Combine messages and data in a dict
                status=status.HTTP_400_BAD_REQUEST,
            )
        # Retrieve the conversation instance
        try:
            conversation = self.get_object()
        except Conversation.DoesNotExist:
            return Response("Conversation not found.", status=status.HTTP_404_NOT_FOUND)

        # Save the frontend message to the database

        received_text = frontend_data.get("textQuery", None)
        textQuery = None
        if received_text:
            textQuery = received_text["text"]
            text_query_id = received_text["id"]

        machine_model = frontend_data.get("machineType", "Yizumi PAC 460 k3")
        received_image_query = frontend_data.get("imageQuery", None)
        imageQuery = None
        if received_image_query:
            imageQuery = split_s3_url(received_image_query["image_url"])
        #        logger.info(f"Image query object: {imageQuery}")
        chatHistory = get_history_for_ai(
            text_query_id, conversation.id, "chat"
        )
        # formatted_chat_history = json.dumps(chatHistory, indent=4, ensure_ascii=False)
        # logger.info(f"chat history: {formatted_chat_history} ")
        # logger.info(
        #     "Sent message from frontend: "
        #     "textQuery: %s, machine_type: %s, imageQuery: %s, chatHistory: %s",
        #     textQuery,
        #     machine_model,
        #     imageQuery,
        #     chatHistory,
        # )
        request_body = {
            "textQuery": textQuery,
            "imageQuery": imageQuery,
            "machineType": machine_model,
            "chatHistory": chatHistory,
        }
        #formatted_request = json.dumps(chatHistory, indent=4, ensure_ascii=False)
        logger.info(f"formatted_request: {request_body} ")
        ai_endpoint = self.get_ai_endpoint(request)
        response = StreamingHttpResponse(
            self.stream_response(
                "simple",
                "text",
                request_body,
                conversation,
                machine_model,
                received_image_query,
                user_id=self.request.user.id,
                ai_endpoint=ai_endpoint,
            )
        )
        response["X-Accel-Buffering"] = "no"  # Disable buffering in nginx
        response["Cache-Control"] = "no-cache"  # Ensure clients don't cache the data
        response["Content-Type"] = "text/event-stream"
        return response

    def stream_response(
        self,
        type,
        content,
        request_body,
        conversation,
        machine_model,
        received_image_query=None,
        user_id=None,
        ai_endpoint=None,
    ):
        try:

            start_time = time.time()
            if type == "ops":
                react_agent_response = session.post(
                    f"{ai_endpoint}/ops/stream",
                    json=request_body,
                    stream=True,
                    timeout=70,  
                )
            else:
                react_agent_response = session.post(
                    f"{ai_endpoint}/chat/stream",
                    json=request_body,
                    stream=True,
                    timeout=70,  
                )

            if react_agent_response.status_code != 200:
                logger.error(
                    "AI agent responded with status code: %d",
                    react_agent_response.status_code,
                )
                yield f"Error: {react_agent_response.status_code}"
                return

            chunk_time = 0
            first_chunk = 0

            complete_buffer = ""
            buffer = ""
            first = True
            for chunk in react_agent_response.iter_content(chunk_size=512):
                if chunk:
                    buffer = chunk.decode("utf-8")
                    if first:

                        chunk_time = time.time() 
                        first_chunk = chunk_time - start_time
                        
                        # logger.info(
                        #     f"start cunking time: {chunk_time } seconds"
                        # )
                        first = False

                    complete_buffer += buffer  # Accumulate the buffer

                    # Try to split the accumulated buffer into JSON objects
                    while True:
                        start_index = complete_buffer.find("{")
                        end_index = complete_buffer.find("}", start_index)

                        if start_index != -1 and end_index != -1:
                            json_str = complete_buffer[start_index : end_index + 1]

                            try:
                                parsed_word = json.loads(json_str)
                                inner_word = parsed_word["data"]

                                if content == "text":
                                    # string_format = json.dumps(parsed_word)
                                    # logger.info(f"stream : {string_format}")
                                    yield f"data : {inner_word}\n\n"
                                else:
                                    #logger.info(f"content : {inner_word}")
                                    yield parsed_word
                                # yield inner_word

                                # Update the buffer to remove the processed JSON
                                complete_buffer = complete_buffer[
                                    end_index + 1 :
                                ].strip()
                            except json.JSONDecodeError:
                                # If parsing fails, break the loop to wait for more data
                                break
                        else:
                            # If no more complete JSON objects are found, break the loop
                            break
            elapsed_time = time.time()
            # Once streaming is complete, process the complete response'
            full_response = complete_buffer
            stream_time = elapsed_time - chunk_time
            logger.info(f"user id: {user_id}, first chunk : {first_chunk}, stream_time: {stream_time } seconds")

            threading.Thread(
                target=self.save_response_to_db,
                args=(
                    full_response,
                    conversation,
                    machine_model,
                    received_image_query,
                ),
            ).start()
            # Check if there's any response from the database saving thread
            db_response = response_queue.get()
            # logger.info(f"post save response : {db_response}")
            if db_response:
                yield json.dumps(db_response)

        except json.JSONDecodeError as e:
            logger.error("Failed to decode JSON: %s", str(e))
            yield json.dumps({"error": "Failed to decode JSON"})

        except requests.exceptions.Timeout:
            logger.error("Request to AI agent timed out.")
            yield json.dumps({"error": "Request timed out. Please try again later."})

        except requests.RequestException as e:
            logger.error(f"Error communicating with AI agent: {str(e)}")
            yield json.dumps({"error": f"Error: {str(e)}"})

    # @database_sync_to_async
    def save_response_to_db(
        self,
        full_response,
        conversation,
        machine_model,
        received_image_query,
    ):
        try:
            start_time = time.time()

            escaped_string = json.loads(full_response)
            # logger.info(f"full response cescaped : {type(escaped_string)}")
            # Convert the dictionary to JSON using json.dumps()
            response_data = json.loads(escaped_string)
            # logger.info(
            #     f"full response converted {response_data}   type : {type(response_data)}"
            # )
            response_text = response_data["response"]
            #logger.info(f"text  type   {response_text}  ")
            response_images = response_data["images"]
            #logger.info(f"images type {response_images}  ")

            if received_image_query:
                image_input_desc = response_data["imageInputDescription"]
                if image_input_desc:
                    imageMessage = ImageMessage.objects.get(
                        id=received_image_query["id"]
                    )
                    imageMessage.metadata = image_input_desc
                    imageMessage.save()

            # Save text response
            saved_text = None
            if response_text:
                text_message = TextMessage.objects.create(
                    conversation=conversation,
                    text=response_text,
                    machine_model=machine_model,
                    sender="ai",
                )
                saved_text = {
                    "id": text_message.id,
                    "text": response_text,
                }
                logger.info("Saved text response to the database.")

            # Save image responses
            saved_images = []
            if response_images:
                restructured_images = restructure_images(response_images)
                for image in restructured_images:
                    image_url = image["image_url"]
                    image_desc = image["description"]
                    image_util = image["utility"]
                    metadata = f"description:{image_desc}|utility:{image_util}"
                    image_message = ImageMessage.objects.create(
                        conversation=conversation,
                        image_url=image_url,
                        metadata=metadata,
                        machine_model=machine_model,
                        sender="ai",
                    )
                    saved_images.append(
                        {
                            "id": image_message.id,
                            "image_url": image_url,
                            "metadata": metadata,
                        }
                    )

                logger.info("Saved images to the database.")
            # Construct the response data

            response = {
                "text": saved_text,
                "images": saved_images,
            }

            saved_time = time.time()
            logger.info(
                f"Time to save to the database: {saved_time - start_time} seconds"
            )
            response_queue.put(response)
            # return response

        except json.JSONDecodeError:
            logger.error("Failed to decode JSON response: %s", full_response)
        except Exception as e:
            logger.error("Error saving response to database: %s", str(e))

   
   
    

class TextMessageViewSet(ModelViewSet):
    """Manage text messages"""

    serializer_class = TextMessageSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # filter text messages by conversation_id
        return TextMessage.objects.filter(
            conversation_id=self.kwargs.get("conversation_pk"),
            is_deleted=False,
        ).order_by("-created_at")

    def get_serializer_context(self):
        # pass conversation_id to serializer
        return {"conversation_id": self.kwargs.get("conversation_pk")}

    def perform_create(self, serializer):
        conversation_id = self.kwargs.get("conversation_pk")

        # Attempt to retrieve the conversation object
        conversation = Conversation.objects.get(id=conversation_id)
        if not conversation:
            # logger.error(f"Conversation with id {conversation_id} does not exist.")
            return Response(
                {"error": "Conversation does not exist."},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer.save(conversation=conversation)


class ImageMessageViewSet(ModelViewSet):
    """Manage image messages"""

    serializer_class = ConversationImageMessageSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # filter image messages by conversation_id
        return ImageMessage.objects.filter(
            conversation_id=self.kwargs.get("conversation_pk"),
            is_deleted=False,
        ).order_by("-created_at")

    def get_serializer_context(self):
        # pass conversation_id to serializer
        return {"conversation_id": self.kwargs.get("conversation_pk")}
    
    def perform_create(self, serializer):
        conversation_id = self.kwargs.get("conversation_pk")

        # Attempt to retrieve the conversation object
        conversation = Conversation.objects.get(id=conversation_id)
        if not conversation:
            # logger.error(f"Conversation with id {conversation_id} does not exist.")
            return Response(
                {"error": "Conversation does not exist."},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer.save(conversation=conversation)
       

    @action(detail=False, methods=["post"])
    def upload_image(self, request, *args, **kwargs):
        # Use the custom serializer for validation
        conversation_id = self.kwargs.get("conversation_pk")
        conversation = Conversation.objects.filter(
            id=conversation_id, is_deleted=False
        ).first()
        if not conversation:
            return Response(
                {"error": "Conversation does not exist."},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = self.get_serializer_class()(data=request.data)

        if serializer.is_valid():
            start_time = time.time()
            image_file = request.FILES.get("image")
            # conversation_id = serializer.validated_data['conversation_id']

            # Extract additional fields from the validated data
            additional_data = {
                key: value
                for key, value in serializer.validated_data.items()
                if key != "image" and key != "image_url"
            }

            if image_file:
                # Generate the desired file name
                filename = f"v1/static/media/{conversation_id}.{datetime.now().strftime('%Y%m%d_%H%M%S')}.{image_file.name}"

                try:
                    # Save the file using default_storage
                    file_path = default_storage.save(filename, image_file)

                    # Log the successful upload
                    # logger.info(f"Image uploaded successfully: {file_path}")
                    image_name = image_file.name.split("/")[-1]
                    image_url = (
                        f"https://zbot-image-input-v1.s3.amazonaws.com/{uuid.uuid4()}_{image_file.name}"
                    )

                    # Create an ImageMessage object
                    image_message = ImageMessage(
                        image_url=image_url,
                        image=image_name,
                        conversation=conversation,
                        **additional_data,
                    )
                    image_message.save()

                    # Serialize the saved object for the response
                    response_serializer = ConversationImageMessageSerializer(
                        image_message
                    )
                    upload_time = time.time()
                    logger.info(f"Upload image time: {upload_time - start_time}")
                    # logger.debug(f"Serialized data: {response_serializer.data}")
                    return Response(
                        response_serializer.data, status=status.HTTP_201_CREATED
                    )
                except Exception as e:
                    logger.error(f"Error creating image message: {str(e)}")
                    return Response(
                        {"error": str(e)}, status=status.HTTP_400_BAD_REQUEST
                    )

        return Response(
            {"error": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
        )
    
    

    # def update(self, request, *args, **kwargs):
    #     partial = kwargs.pop("partial", False)
    #     instance = self.get_object()  # Get the instance to update
    #     serializer = self.get_serializer(instance, data=request.data, partial=partial)

    #     try:
    #         serializer.is_valid(raise_exception=True)
    #         validated_data = serializer.validated_data

    #         # Save the updated instance
    #         for attr, value in validated_data.items():
    #             setattr(instance, attr, value)
    #         instance.save()

    #         logger.info(f"Image message updated: {instance.id}")
    #         return Response(serializer.data)

    #     except Exception as e:
    #         logger.error(f"Error updating image message: {str(e)}")
    #         return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class MachineViewSet(ModelViewSet):
    serializer_class = MachineSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = MachineFilter
    permission_classes = [IsAuthenticated]
    
    # filter out deleted machines
    def get_queryset(self):
        return Machine.objects.order_by("-created_at")


class MaterialViewSet(ModelViewSet):
    queryset = Material.objects.all()
    serializer_class = MaterialSerializer
    permission_classes = [IsAuthenticated]


class MachineParameterViewSet(ModelViewSet):
    serializer_class = MachineParameterSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = MachineParameterFilter
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # filter machine parameters by machine_id
        return MachineParameter.objects.filter(
            conversation_id=self.kwargs.get("conversation_pk")
        ).order_by("-created_at")

    def get_serializer_context(self):
        # pass conversation_id to serializer
        return {"conversation_id": self.kwargs.get("conversation_pk")}

    def create(self, request, *args, **kwargs):
        # Access request.data once
        request_data = request.data

        # Log the request data
        # logger.info("Request data: %s", request_data)
        conversation_id = self.kwargs.get("conversation_pk")
        # request.data["conversation_id"] = conversation_id

        machine = Machine.objects.filter(id=request_data.get("machine")).first()
        material = Material.objects.filter(id=request_data.get("material")).first()

        if machine is None or material is None:
            return Response(
                {
                    "detail": " machine or material not exists",
                },  # Combine messages and data in a dict
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = self.get_serializer(data=request_data)
        # logger.info("valid serializer %s ", serializer.is_valid())

        if serializer.is_valid():  # Validate the data
            serializer.save(conversation_id=conversation_id)  # Save the validated data
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        else:
            # Log the errors if validation fails
            logger.error("Error creating machine parameters: %s", serializer.errors)
            return Response(
                {
                    "error": "Failed to create machine parameters",
                    "details": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )


class BugReportViewSet(ModelViewSet):
    queryset = BugReport.objects.all().select_related("customer, company, operator")
    serializer_class = BugReportSerializer
    permission_classes = [IsAuthenticated]
