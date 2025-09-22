import mimetypes
from typing import Dict, Optional, TypedDict, Union

from literalai.api.helpers import gql
from literalai.observability.step import Attachment


def create_attachment_helper(
    step_id: str,
    thread_id: Optional[str] = None,
    id: Optional[str] = None,
    metadata: Optional[Dict] = None,
    mime: Optional[str] = None,
    name: Optional[str] = None,
    object_key: Optional[str] = None,
    url: Optional[str] = None,
    content: Optional[Union[bytes, str]] = None,
    path: Optional[str] = None,
):
    if not content and not url and not path:
        raise Exception("Either content, path or attachment url must be provided")

    if content and path:
        raise Exception("Only one of content and path must be provided")

    if (content and url) or (path and url):
        raise Exception("Only one of content, path and attachment url must be provided")

    if path:
        # TODO: if attachment.mime is text, we could read as text?
        with open(path, "rb") as f:
            content = f.read()
        if not name:
            name = path.split("/")[-1]
        if not mime:
            mime, _ = mimetypes.guess_type(path)
            mime = mime or "application/octet-stream"

    if not name:
        raise Exception("Attachment name must be provided")

    variables = {
        "metadata": metadata,
        "mime": mime,
        "name": name,
        "objectKey": object_key,
        "stepId": step_id,
        "threadId": thread_id,
        "url": url,
        "id": id,
    }

    description = "create attachment"

    def process_response(response):
        return Attachment.from_dict(response["data"]["createAttachment"])

    return gql.CREATE_ATTACHMENT, description, variables, content, process_response


class AttachmentUpload(TypedDict, total=False):
    metadata: Optional[Dict]
    name: Optional[str]
    mime: Optional[str]
    objectKey: Optional[str]
    url: Optional[str]


def update_attachment_helper(id: str, update_params: AttachmentUpload):
    variables = {"id": id, **update_params}

    def process_response(response):
        return Attachment.from_dict(response["data"]["updateAttachment"])

    description = "update attachment"

    return gql.UPDATE_ATTACHMENT, description, variables, process_response


def get_attachment_helper(id: str):
    variables = {"id": id}

    def process_response(response):
        attachment = response["data"]["attachment"]
        return Attachment.from_dict(attachment) if attachment else None

    description = "get attachment"

    return gql.GET_ATTACHMENT, description, variables, process_response


def delete_attachment_helper(id: str):
    variables = {"id": id}

    def process_response(response):
        return response["data"]["deleteAttachment"]

    description = "delete attachment"

    return gql.DELETE_ATTACHMENT, description, variables, process_response
