from typing import Dict, Any

from ..client.http import HTTPClient


class BaseAnnotation:
    """
    Annotation class for creating annotations in Traceloop.

    This class provides functionality to create annotations for specific tasks.
    """

    _http: HTTPClient
    _app_name: str

    def __init__(self, http: HTTPClient, app_name: str, flow: str):
        self._http = http
        self._app_name = app_name
        self._flow = flow

    def create(
        self,
        annotation_task: str,
        entity_id: str,
        tags: Dict[str, Any],
    ) -> None:
        """Create an user feedback annotation for a specific task.

        Args:
            annotation_task (str): The ID/slug of the annotation task to report to.
                Can be found at app.traceloop.com/annotation_tasks/:annotation_task_id
            entity_id (str): The ID of the specific entity instance being annotated, should be reported
                in the association properties
            tags (Dict[str, Any]): Dictionary containing the tags to be reported.
                Should match the tags defined in the annotation task

        Example:
            ```python
            client = Client(api_key="your-key")
            client.annotation.create(
                annotation_task="task_123",
                entity_id="instance_456",
                tags={
                    "sentiment": "positive",
                    "relevance": 0.95,
                    "tones": ["happy", "nice"]
                },
            )
            ```
        """

        if not annotation_task:
            raise ValueError("annotation_task is required")
        if not entity_id:
            raise ValueError("entity_id is required")
        if not tags:
            raise ValueError("tags cannot be empty")

        self._http.post(
            f"annotation-tasks/{annotation_task}/annotations",
            {
                "entity_instance_id": entity_id,
                "tags": tags,
                "source": "sdk",
                "flow": self._flow,
                "actor": {
                    "type": "service",
                    "id": self._app_name,
                },
            },
        )
