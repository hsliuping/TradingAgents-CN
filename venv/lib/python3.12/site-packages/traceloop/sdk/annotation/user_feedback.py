from typing import Any, Dict

from traceloop.sdk.client.http import HTTPClient
from .base_annotation import BaseAnnotation


class UserFeedback(BaseAnnotation):
    def __init__(self, http: HTTPClient, app_name: str):
        super().__init__(http, app_name, "user_feedback")


def create(
    self,
    annotation_task: str,
    entity_instance_id: str,
    tags: Dict[str, Any],
) -> None:
    """Create an annotation for a specific task.

    Args:
        annotation_task (str): The ID/slug of the annotation task to report to.
            Can be found at app.traceloop.com/annotation_tasks/:annotation_task_id
        entity_instance_id (str): The ID of the specific entity instance being annotated, should be reported
            in the association properties
        tags (Dict[str, Any]): Dictionary containing the tags to be reported.
            Should match the tags defined in the annotation task

    Example:
        ```python
        client = Client(api_key="your-key")
        client.annotation.create(
            annotation_task="task_123",
            entity_instance_id="instance_456",
            tags={
                "sentiment": "positive",
                "relevance": 0.95,
                "tones": ["happy", "nice"]
            },
        )
        ```
    """

    return BaseAnnotation.create(self, annotation_task, entity_instance_id, tags)
