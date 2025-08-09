from datetime import datetime, timedelta
from django.core.exceptions import ValidationError
from django.db import connection
import psycopg2
import logging
import time
import json
import uuid


MAX_RETRIES = 3
RETRY_DELAY = 1

# Set up the logger
logger = logging.getLogger(__name__)


def reconnect_database(connection, logger):
    """Reconnect to the database if the connection is closed."""
    retries = 0
    while retries < MAX_RETRIES:
        try:
            connection.connect()
            logger.info("Database connection re-established.")
            return
        except (ConnectionError, OperationalError) as e:
            logger.error(
                f"Failed to reconnect to database (attempt {retries+1}/{MAX_RETRIES}): {e}"
            )
            retries += 1
            if retries < MAX_RETRIES:
                logger.info(f"Retrying in {RETRY_DELAY} seconds...")
                time.sleep(RETRY_DELAY)
    logger.error(
        "Failed to reconnect to database after {} retries.".format(MAX_RETRIES)
    )
    return []


def restructure_images(original_json):
    if original_json is not None:
        # Extract the relevant parts from the original JSON
        images = original_json["images"]
        descriptions = original_json["descriptions"]
        utilities = original_json["utilities"]

        # Create the new structured list of images
        structured_images = []

        for i in range(len(images)):
            structured_images.append(
                {
                    "image_url": images[i],
                    "description": (
                        descriptions[i]
                        if (len(descriptions) > 0 and descriptions[i] is not None)
                        else None
                    ),
                    "utility": (
                        utilities[i]
                        if (len(utilities) > 0 and utilities[i] is not None)
                        else None
                    ),
                }
            )

        # Return the new JSON structure
        return structured_images
    return None


def split_s3_url(url):
    # Remove the "https://" part

    if (url is not None) and ("https" in url):
        url = url.replace("https://", "")

        # Split the URL into bucket and the rest
        bucket, key = url.split("/", 1)
        bucket = bucket.replace(".s3.amazonaws.com", "")
        return {"bucket": bucket, "key": key}
    return None


def file_size(value):
    # add this to some file where you can import it from
    limit = 20 * 1024 * 1024  # 20MB
    if value.size > limit:
        raise ValidationError("File too large. Size should not exceed 20 MB.")

def image_file_size(value):
    max_size = 20 * 1024 * 1024  # 20 MB
    if value.size > max_size:
        raise ValidationError("File too large. Size should not exceed 20 MB.")
    


def image_upload_path(instance, filename):
    return f"v1/static/media/{uuid.uuid4()}_{filename}"

def get_conversation_history(conversation_id, limit, offset):
    """
    Retrieves the conversation history for a given conversation ID.

    Args:
    conversation_id (int): The ID of the conversation to retrieve history for.

    Returns:
    list: A list of dictionaries representing the conversation history.
    """

    try:
        count_query = """
            WITH
                text_messages AS (
                    SELECT
                        tm.id::TEXT AS id
                    FROM
                        zbot_conversation c
                    LEFT JOIN zbot_textmessage tm ON c.id = tm.conversation_id
                    WHERE
                        c.id = %s
                        AND tm.is_deleted = FALSE
                ),
                image_messages AS (
                    SELECT
                        im.id::TEXT AS id
                    FROM
                        zbot_conversation c
                    LEFT JOIN zbot_imagemessage im ON c.id = im.conversation_id
                    WHERE
                        im.is_deleted = FALSE
                        AND c.id = %s
                ),
                machine_parameters AS (
                    SELECT
                        mp.id::TEXT AS id
                    FROM
                        zbot_conversation c
                    LEFT JOIN zbot_machineparameter mp ON c.id = mp.conversation_id
                    WHERE
                        c.id = %s
                )
            SELECT COUNT(*)
            FROM (
                SELECT id FROM text_messages
                UNION ALL
                SELECT id FROM image_messages
                UNION ALL
                SELECT id FROM machine_parameters
            ) AS combined_messages;
        """

        with connection.cursor() as cursor:
            cursor.execute(
                count_query, [conversation_id, conversation_id, conversation_id]
            )
            total_count = cursor.fetchone()[0]

        cursor = connection.cursor()
        cursor.execute(
            """
            WITH
                text_messages AS (
                    SELECT
                        tm.id::TEXT AS id,
                        'text' AS type,
                        tm.text AS data,
                        NULL AS image_description,
                        tm.sender AS sender,
                        tm.created_at AS created_at
                    FROM
                        zbot_conversation c
                    LEFT JOIN zbot_textmessage tm ON c.id = tm.conversation_id
                    WHERE
                        c.id = %s
                        AND tm.is_deleted = FALSE
                ),
                image_messages AS (
                    SELECT
                        im.id::TEXT AS id,
                        'image' AS type,
                        im.image_url AS data,
                        im.metadata AS image_description,
                        im.sender AS sender,
                        im.created_at AS created_at
                    FROM
                        zbot_conversation c
                    LEFT JOIN zbot_imagemessage im ON c.id = im.conversation_id
                    WHERE
                        im.is_deleted = FALSE
                        AND c.id = %s
                ),
                machine_parameters AS (
                    SELECT
                        mp.id::TEXT AS id,
                        'parameter' AS type,
                        mp.title AS data,
                        CONCAT(
                            COALESCE(ARRAY_TO_STRING(mp.injection_temperature, ','), ''),
                            '|',
                            COALESCE(ARRAY_TO_STRING(mp.position, ','), ''),
                            '|',
                            COALESCE(ARRAY_TO_STRING(mp.injection_pressure, ','), ''),
                            '|',
                            COALESCE(ARRAY_TO_STRING(mp.velocity, ','), ''),
                            '|',
                            COALESCE(mp.mold_temperature, 0.0),
                            '|',
                            COALESCE(mp.cooling_time, 0.0),
                            '|',
                            COALESCE(mp.hot_runner_temperature, 0.0),
                            '|',
                            COALESCE(mp.decompression, 0.0),
                            '|',
                            COALESCE(ARRAY_TO_STRING(mp.hold_pressure, ','), ''),
                            '|',
                            COALESCE(ARRAY_TO_STRING(mp.hold_velocity, ','), ''),
                            '|',
                            COALESCE(ARRAY_TO_STRING(mp.hold_time, ','), ''),
                            '|',
                            COALESCE(ARRAY_TO_STRING(mp.back_pressure, ','), ''),
                            '|',
                            COALESCE(mp.clamping_force, 0.0),
                            '|',
                            COALESCE(mp.injection_weight, 0.0),
                            '|',
                            COALESCE(mp.num_cavities, 0.0),
                            '|',
                            COALESCE(mp.single_prod_wieght, 0.0),
                            '|',
                            COALESCE(mp.nozzle_weight, 0.0),
                            '|',
                            COALESCE(mp.clamping_pressure, 0.0),
                            '|',
                            COALESCE(m.id::TEXT,''),  
                            '|',
                            COALESCE(mat.id::TEXT,'')  
                        ) AS fineTunning,
                        'user' AS sender,
                        mp.created_at AS created_at
                    FROM
                        zbot_conversation c
                    LEFT JOIN zbot_machineparameter mp ON c.id = mp.conversation_id
                    LEFT JOIN zbot_machine m ON mp.machine_id = m.id  
                    LEFT JOIN zbot_material mat ON mp.material_id = mat.id  
                    WHERE
                        c.id = %s
                )
            SELECT
                *
            FROM 
                text_messages
            UNION 
            SELECT
                *
            FROM
                image_messages
            UNION 
            SELECT
                *
            FROM
                machine_parameters
            ORDER BY
                created_at DESC
            LIMIT %s OFFSET %s;
            """,
            [conversation_id, conversation_id, conversation_id, limit, offset],
        )
        rows = cursor.fetchall()
        json_rows = []
        for row in rows:
            if row[0] is None:
                continue
            row_dict = {}
            if row[1] == "text":
                row_dict = {
                    "id": row[0],
                    "type": row[1],
                    "data": row[2],
                    "sender": row[4],
                    "created_at": row[5],
                }
            if row[1] == "image":
                image_utility = ""
                if row[3] is not None:
                    if row[3].startswith("description"):
                        parts = row[3].split("|")
                        image_utility = parts[1].split(":")[1]
                row_dict = {
                    "id": row[0],
                    "type": row[1],
                    "data": row[2],
                    "image_utility": row[3],  # image_utility,
                    "sender": row[4],
                    "created_at": row[5],
                }
            # Check if the row is a machine parameter and convert data to JSON
            if row[1] == "parameter":
                data_parts = row[3].split("|")
                # logger.info(
                #     f" data parts : {data_parts} machine_id:  {data_parts[18]} ,material_id :  {data_parts[19]}"
                # )
                data_json = {
                    "injection_temperature": (
                        json.loads(f"[{data_parts[0]}]") if data_parts[0] else []
                    ),
                    "position": (
                        json.loads(f"[{data_parts[1]}]") if data_parts[1] else []
                    ),
                    "injection_pressure": (
                        json.loads(f"[{data_parts[2]}]") if data_parts[2] else []
                    ),
                    "velocity": (
                        json.loads(f"[{data_parts[3]}]") if data_parts[3] else []
                    ),
                    "mold_temperature": float(data_parts[4]) if data_parts[4] else 0.0,
                    "cooling_time": float(data_parts[5]) if data_parts[5] else 0.0,
                    "hot_runner_temperature": (
                        float(data_parts[6]) if data_parts[6] else 0.0
                    ),
                    "decompression": float(data_parts[7]) if data_parts[7] else 0.0,
                    "hold_pressure": (
                        json.loads(f"[{data_parts[8]}]") if data_parts[8] else []
                    ),
                    "hold_velocity": (
                        json.loads(f"[{data_parts[9]}]") if data_parts[9] else []
                    ),
                    "hold_time": (
                        json.loads(f"[{data_parts[10]}]") if data_parts[10] else []
                    ),
                    "back_pressure": (
                        json.loads(f"[{data_parts[11]}]") if data_parts[11] else []
                    ),
                    "clamping_force": float(data_parts[12]) if data_parts[12] else 0.0,
                    "injection_weight": (
                        float(data_parts[13]) if data_parts[13] else 0.0
                    ),
                    "num_of_cavities": (
                        float(data_parts[14]) if data_parts[14] else 0.0
                    ),
                    "prod_wieght": (float(data_parts[15]) if data_parts[15] else 0.0),
                    "nozzle_weight": (float(data_parts[16]) if data_parts[16] else 0.0),
                    "clamping_pressure": (
                        float(data_parts[17]) if data_parts[17] else 0.0
                    ),
                    "machine_id": (str(data_parts[18]) if data_parts[18] else ""),
                    "material_id": (str(data_parts[19]) if data_parts[19] else ""),
                }
                row_dict = {
                    "id": row[0],
                    "type": row[1],
                    "data": row[2],
                    "fineTunning": data_json,
                    "sender": row[4],
                    "created_at": row[5],
                }
            if row_dict:  # Only append if row_dict is not empty
                json_rows.append(row_dict)

        return [json_rows, total_count]

    except psycopg2.Error as e:
        logger.error(f"Database query failed: {e}")
        return []

    # # Check if rows contain only None values or are empty
    # if not rows or all(row is None for row in rows):
    #     return []  # Return an empty array if no messages or images
    # logger.info("rows : %s", rows)
    # # Process rows into the desired format
    # conversation_history = []
    # for row in rows:
    #     if row is not None or row[0] is not None:
    #         (id, type, data, image_description, sender, created_at) = row

    #         if type == "text":
    #             conversation_history.append(
    #                 {
    #                     "id": str(id),  # Ensure ID is a string
    #                     "type": type,
    #                     "data": data,  # Text message content
    #                     "sender": sender,
    #                     "created_at": created_at,
    #                 }
    #             )
    #         elif type == "image":
    #             image_description = ""
    #             image_utility = ""
    #             if image_description is not None:
    #                 if image_description.startswith("description"):
    #                     parts = image_description.split("|")
    #                     image_description = parts[0].split(":")[1]
    #                     image_utility = parts[1].split(":")[1]

    #             conversation_history.append(
    #                 {
    #                     "id": str(id),  # Ensure ID is a string
    #                     "type": type,
    #                     "data": data,  # Image URL
    #                     "image_description": image_description,
    #                     "image_utility": image_utility,
    #                     "sender": sender,
    #                     "created_at": created_at,
    #                 }
    #             )
    #         else:
    #             logger.info(f" data  content {data}")
    #             # splittted_params = data.split("-")
    #             fine_tuning = None
    #             # if len(splittted_params):
    #             #     fine_tuning = {
    #             #         "injection_temperature": splittted_params[1],
    #             #         "position": splittted_params[2],
    #             #         "injection_pressure": splittted_params[3],
    #             #         "velocity": splittted_params[4],
    #             #         "hold_pressure": splittted_params[5],
    #             #         "hold_velocity": splittted_params[6],
    #             #         "hold_time": splittted_params[7],
    #             #         "back_pressure": splittted_params[8],
    #             #         "mold_temperature": splittted_params[9],
    #             #         "cooling_time": splittted_params[10],
    #             #         "hot_runner_temperature": splittted_params[11],
    #             #         "decompression": splittted_params[12],
    #             #         "clamping_force": splittted_params[13],
    #             #     }
    #             formatted_params = {
    #                 "id": str(id),  # Ensure ID is a string
    #                 "type": type,
    #                 "data": fine_tuning,
    #                 "fineTuning": fine_tuning,
    #                 "sender": "user",
    #                 "created_at": created_at,
    #             }
    #             conversation_history.append(formatted_params)

    # return conversation_history


def get_history_for_ai(text_query_id, conversation_id, type):
    """
    Retrieves the conversation history for a given conversation ID,
    including the latest 10 text messages and related image messages.

    Args:
    conversation_id (int): The ID of the conversation to retrieve history for.

    Returns:
    list: A list of dictionaries representing the conversation history.
    """

    if not connection.is_usable():
        reconnect_database(connection, logger)
        return []

    try:
        with connection.cursor() as cursor:
            # Get the latest 2 text messages
            query = """
                SELECT
                    tm.id AS id,
                    tm.text AS data,
                    tm.sender AS sender,
                    tm.created_at AS created_at
                FROM
                    zbot_conversation c
                LEFT JOIN
                    zbot_textmessage tm ON c.id = tm.conversation_id
                WHERE
                    tm.id <> %s
                    AND c.id = %s
                    AND tm.is_deleted = FALSE
                ORDER BY created_at DESC
                LIMIT 12;
            """
            cursor.execute(query, [text_query_id, conversation_id])
            text_messages = cursor.fetchall()

            # logger.info(f"list of text messages {text_messages}")
            if not text_messages:
                return []  # Return an empty array if no text messages

            conversation_history = []

            # For each text message, find related image messages
            for tm in reversed(text_messages):
                text_id, text_data, sender, created_at = tm
                minute_start = created_at.replace(
                    second=0, microsecond=0
                )  # Start of the minute
                minute_end = minute_start + timedelta(minutes=2)  # End of the minute

                # Fetch related image messages created within the same minute and with the same sender
                image_query = """
                    SELECT
                        im.id AS id,
                        im.image_url AS data,
                        im.metadata AS image_description
                    FROM
                        zbot_imagemessage im
                    WHERE
                        im.conversation_id = %s
                        AND im.is_deleted = FALSE
                        AND im.sender = %s
                        AND im.created_at >= %s
                        AND im.created_at < %s
                """
                cursor.execute(
                    image_query, [conversation_id, sender, minute_start, minute_end]
                )
                image_messages = cursor.fetchall()

                # Structure the result
                image_descriptions = []
                for img in image_messages:
                    image_desc = ""
                    if img[2] is not None:
                        if img[2].startswith("description"):
                            parts = img[2].split("|")
                            image_desc = parts[0].split(":")[1]
                    image_descriptions.append(image_desc)

                machine_params_list = []
                #
                machine_param_query = """
                    SELECT
                        mp.id AS id,
                        mp.title AS title,
                        mp.injection_temperature AS injection_temperature,
                        mp.position AS position,
                        mp.injection_pressure AS injection_pressure,
                        mp.velocity AS velocity,
                        mp.mold_temperature AS mold_temperature,
                        mp.cooling_time AS cooling_time,
                        mp.hot_runner_temperature AS hot_runner_temperature,
                        mp.decompression AS decompression,
                        mp.hold_pressure AS hold_pressure,
                        mp.hold_velocity AS hold_velocity,
                        mp.hold_time AS hold_time,
                        mp.back_pressure AS back_pressure,
                        mp.clamping_force AS clamping_force,
                        mp.injection_weight AS injection_weight
                    FROM
                        zbot_machineparameter mp
                    WHERE
                        mp.conversation_id = %s
                        AND mp.created_at >= %s
                        AND mp.created_at < %s
                """
                cursor.execute(
                    machine_param_query, [conversation_id, minute_start, minute_end]
                )
                machine_parameters = cursor.fetchall()

                # Structure the machine parameters

                for param in machine_parameters:
                    machine_params_list.append(
                        {
                            "injection_temperature": param[2],
                            "position": param[3],
                            "injection_pressure": param[4],
                            "velocity": param[5],
                            "mold_temperature": param[6],
                            "cooling_time": param[7],
                            "hot_runner_temperature": param[8],
                            "decompression": param[9],
                            "hold_pressure": param[10],
                            "hold_velocity": param[11],
                            "hold_time": param[12],
                            "back_pressure": param[13],
                            "clamping_force": param[14],
                            "injection_weight": param[15],
                        }
                    )
                if len(machine_parameters) == 0:
                    from zbot.models import MachineParameter

                    param = (
                        MachineParameter.objects.filter(
                            conversation_id=conversation_id, created_at__lt=minute_start
                        )
                        .order_by("-created_at")
                        .first()
                    )
                    if param is not None:
                        latest_current_param = {
                            "injection_temperature": param.injection_temperature,
                            "position": param.position,
                            "injection_pressure": param.injection_pressure,
                            "velocity": param.velocity,
                            "mold_temperature": param.mold_temperature,
                            "cooling_time": param.cooling_time,
                            "hot_runner_temperature": param.hot_runner_temperature,
                            "decompression": param.decompression,
                            "hold_pressure": param.hold_pressure,
                            "hold_velocity": param.hold_velocity,
                            "hold_time": param.hold_time,
                            "back_pressure": param.back_pressure,
                            "clamping_force": param.clamping_force,
                            "injection_weight": param.injection_weight,
                        }
                        machine_params_list.append(latest_current_param)

                history_data = {
                    "role": sender,
                    "message": text_data,
                }

                if type == "ops":
                    pass
                #                    history_data["updatedParameters"] = machine_params_list
                else:
                    history_data["imageDescription"] = image_descriptions

                # Append the structured object to the conversation history
                conversation_history.append(history_data)

    except psycopg2.Error as e:
        logger.error(f"Database query failed: {e}")
        return []

    return conversation_history


def conversation_image_path(instance, filename):
    conversation_id = instance.conversation_id
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Log the path being created
    # logger.info(
    #     f"Creating image path for conversation ID {conversation_id}: {filename}"
    # )

    return f"v1/static/media/{conversation_id}.{timestamp}.{filename}"
