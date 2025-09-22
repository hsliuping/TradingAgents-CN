import os
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union

from typing_extensions import deprecated

from literalai.api.helpers.attachment_helpers import AttachmentUpload
from literalai.api.helpers.prompt_helpers import PromptRollout
from literalai.api.helpers.score_helpers import ScoreUpdate
from literalai.cache.shared_cache import SharedCache
from literalai.evaluation.dataset import DatasetType
from literalai.evaluation.dataset_experiment import DatasetExperimentItem
from literalai.my_types import Environment
from literalai.observability.filter import (
    generations_filters,
    generations_order_by,
    scores_filters,
    scores_order_by,
    steps_filters,
    steps_order_by,
    threads_filters,
    threads_order_by,
    users_filters,
)
from literalai.observability.generation import (
    ChatGeneration,
    CompletionGeneration,
    GenerationMessage,
)
from literalai.observability.step import ScoreDict, ScoreType, Step, StepDict, StepType
from literalai.prompt_engineering.prompt import ProviderSettings


def prepare_variables(variables: Dict[str, Any]) -> Dict[str, Any]:
    """
    Recursively checks and converts bytes objects in variables.
    """

    def handle_bytes(item):
        if isinstance(item, bytes):
            return "STRIPPED_BINARY_DATA"
        elif isinstance(item, dict):
            return {k: handle_bytes(v) for k, v in item.items()}
        elif isinstance(item, list):
            return [handle_bytes(i) for i in item]
        elif isinstance(item, tuple):
            return tuple(handle_bytes(i) for i in item)
        return item

    return handle_bytes(variables)


class BaseLiteralAPI(ABC):
    def __init__(
        self,
        api_key: Optional[str] = None,
        url: Optional[str] = None,
        environment: Optional[Environment] = None,
    ):
        if url and url[-1] == "/":
            url = url[:-1]

        if api_key is None:
            raise Exception("LITERAL_API_KEY not set")
        if url is None:
            raise Exception("LITERAL_API_URL not set")

        self.api_key = api_key
        self.url = url

        if environment:
            os.environ["LITERAL_ENV"] = environment

        self.graphql_endpoint = self.url + "/api/graphql"
        self.rest_endpoint = self.url + "/api"

        self.cache = SharedCache()

    @property
    def headers(self):
        from literalai.version import __version__

        h = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "x-client-name": "py-literal-client",
            "x-client-version": __version__,
        }

        if env := os.getenv("LITERAL_ENV"):
            h["x-env"] = env

        return h

    @abstractmethod
    def get_users(
        self,
        first: Optional[int] = None,
        after: Optional[str] = None,
        before: Optional[str] = None,
        filters: Optional[users_filters] = None,
    ):
        """
        Retrieves a list of users based on pagination and optional filters.

        Args:
            first (Optional[int]): The number of users to retrieve.
            after (Optional[str]): A cursor for use in pagination, fetching records after this cursor.
            before (Optional[str]): A cursor for use in pagination, fetching records before this cursor.
            filters (Optional[users_filters]): Filters to apply to the user query.

        Returns:
            `PaginatedResponse[User]`: A paginated response containing the queried user data.
        """
        pass

    @abstractmethod
    def get_user(self, id: Optional[str] = None, identifier: Optional[str] = None):
        """
        Retrieves a user based on the provided ID or identifier.

        Args:
            id (Optional[str]): The unique ID of the user.
            identifier (Optional[str]): A unique identifier for the user, such as a username or email.

        Returns:
            `User`: The user with requested id or identifier.
        """
        pass

    @abstractmethod
    def create_user(self, identifier: str, metadata: Optional[Dict] = None):
        """
        Creates a new user with the specified identifier and optional metadata.

        Args:
            identifier (str): A unique identifier for the user, such as a username or email.
            metadata (Optional[Dict]): Additional data associated with the user.

        Returns:
            `User`: The created user object.
        """
        pass

    @abstractmethod
    def update_user(
        self, id: str, identifier: Optional[str] = None, metadata: Optional[Dict] = None
    ):
        """
        Updates an existing user identified by the given ID, with optional new identifier and metadata.

        Args:
            id (str): The unique ID of the user to update.
            identifier (Optional[str]): A new identifier for the user, such as a username or email.
            metadata (Optional[Dict]): New or updated metadata for the user.

        Returns:
            `User`: The updated user object.
        """
        pass

    @abstractmethod
    def delete_user(self, id: str):
        """
        Deletes a user identified by the given ID.

        Args:
            id (str): The unique ID of the user to delete.

        Returns:
            Dict: The deleted user as a dict.
        """
        pass

    @abstractmethod
    def get_or_create_user(self, identifier: str, metadata: Optional[Dict] = None):
        """
        Retrieves a user by their identifier, or creates a new user if it does not exist.

        Args:
            identifier (str): The identifier of the user to retrieve or create.
            metadata (Optional[Dict]): Metadata to associate with the user if they are created.

        Returns:
            `User`: The existing or newly created user.
        """
        pass

    @abstractmethod
    def get_threads(
        self,
        first: Optional[int] = None,
        after: Optional[str] = None,
        before: Optional[str] = None,
        filters: Optional[threads_filters] = None,
        order_by: Optional[threads_order_by] = None,
        step_types_to_keep: Optional[List[StepType]] = None,
    ):
        """
        Fetches a list of threads based on pagination and optional filters.

        Args:
            first (Optional[int]): Number of threads to fetch.
            after (Optional[str]): Cursor for pagination, fetch threads after this cursor.
            before (Optional[str]): Cursor for pagination, fetch threads before this cursor.
            filters (Optional[threads_filters]): Filters to apply on the threads query.
            order_by (Optional[threads_order_by]): Order by clause for threads.
            step_types_to_keep (Optional[List[StepType]]) : If set, only steps of the corresponding types
                                                            will be returned

        Returns:
            `PaginatedResponse[Thread]`: A paginated response containing the queried thread data.
        """
        pass

    @abstractmethod
    def list_threads(
        self,
        first: Optional[int] = None,
        after: Optional[str] = None,
        before: Optional[str] = None,
        filters: Optional[threads_filters] = None,
        order_by: Optional[threads_order_by] = None,
    ):
        """
        Lists threads based on pagination and optional filters, similar to get_threads but may include additional processing.

        Args:
            first (Optional[int]): Number of threads to list.
            after (Optional[str]): Cursor for pagination, list threads after this cursor.
            before (Optional[str]): Cursor for pagination, list threads before this cursor.
            filters (Optional[threads_filters]): Filters to apply on the threads listing.
            order_by (Optional[threads_order_by]): Order by clause for threads.

        Returns:
            `PaginatedResponse[Thread]`: A paginated response containing the queried thread data.
        """
        pass

    @abstractmethod
    def get_thread(self, id: str):
        """
        Retrieves a single thread by its ID.

        Args:
            id (str): The unique identifier of the thread.

        Returns:
            `Thread`: The thread corresponding to the provided ID.
        """
        pass

    @abstractmethod
    def create_thread(
        self,
        name: Optional[str] = None,
        metadata: Optional[Dict] = None,
        participant_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ):
        """
        Creates a `Thread` with the specified details.

        Args:
            name (Optional[str]): Name of the thread.
            metadata (Optional[Dict]): Metadata associated with the thread.
            participant_id (Optional[str]): Identifier for the participant.
            tags (Optional[List[str]]): List of tags associated with the thread.

        Returns:
            `Thread`: The created thread.
        """
        pass

    @abstractmethod
    def upsert_thread(
        self,
        id: str,
        name: Optional[str] = None,
        metadata: Optional[Dict] = None,
        participant_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ):
        """
        Updates an existing thread or creates a new one if it does not exist.

        Args:
            id (str): The unique identifier of the thread.
            name (Optional[str]): Name of the thread.
            metadata (Optional[Dict]): Metadata associated with the thread.
            participant_id (Optional[str]): Identifier for the participant.
            tags (Optional[List[str]]): List of tags associated with the thread.

        Returns:
            `Thread`: The updated or newly created thread.
        """
        pass

    @abstractmethod
    def update_thread(
        self,
        id: str,
        name: Optional[str] = None,
        metadata: Optional[Dict] = None,
        participant_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ):
        """
        Updates the specified details of an existing thread.

        Args:
            id (str): The unique identifier of the thread to update.
            name (Optional[str]): New name of the thread.
            metadata (Optional[Dict]): New metadata for the thread.
            participant_id (Optional[str]): New identifier for the participant.
            tags (Optional[List[str]]): New list of tags for the thread.

        Returns:
            `Thread`: The updated thread.
        """
        pass

    @abstractmethod
    def delete_thread(self, id: str):
        """
        Deletes a thread identified by its ID.

        Args:
            id (str): The unique identifier of the thread to delete.

        Returns:
            `bool`: True if the thread was deleted, False otherwise.
        """
        pass

    @abstractmethod
    def get_scores(
        self,
        first: Optional[int] = None,
        after: Optional[str] = None,
        before: Optional[str] = None,
        filters: Optional[scores_filters] = None,
        order_by: Optional[scores_order_by] = None,
    ):
        """
        Fetches scores based on pagination and optional filters.

        Args:
            first (Optional[int]): The number of scores to retrieve.
            after (Optional[str]): A cursor for use in pagination, fetching records after this cursor.
            before (Optional[str]): A cursor for use in pagination, fetching records before this cursor.
            filters (Optional[scores_filters]): Filters to apply to the scores query.
            order_by (Optional[scores_order_by]): Ordering options for the scores.

        Returns:
            `PaginatedResponse[Score]`: A paginated response containing the queried scores.
        """
        pass

    @abstractmethod
    def create_scores(self, scores: List[ScoreDict]):
        """
        Creates multiple scores.

        Args:
            scores (List[ScoreDict]): A list of dictionaries representing the scores to be created.

        Returns:
            List[ScoreDict]: The created scores as a list of dictionaries.
        """
        pass

    @abstractmethod
    def create_score(
        self,
        name: str,
        value: float,
        type: ScoreType,
        step_id: Optional[str] = None,
        generation_id: Optional[str] = None,
        dataset_experiment_item_id: Optional[str] = None,
        comment: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ):
        """
        Creates a single score in the database.

        Args:
            name (str): The name of the score.
            value (float): The numerical value of the score.
            type (ScoreType): The type of the score.
            step_id (Optional[str]): The ID of the step associated with the score.
            generation_id (Optional[str]): The ID of the generation associated with the score.
            dataset_experiment_item_id (Optional[str]): The ID of the dataset experiment item associated with the score.
            comment (Optional[str]): An optional comment about the score.
            tags (Optional[List[str]]): Optional tags associated with the score.

        Returns:
            `Score`: The created score.
        """
        pass

    @abstractmethod
    def update_score(
        self,
        id: str,
        update_params: ScoreUpdate,
    ):
        """
        Updates a score identified by its ID with new parameters.

        Args:
            id (str): The unique identifier of the score to update.
            update_params (ScoreUpdate): A dictionary of parameters to update in the score.

        Returns:
            `Score`: The updated score.
        """
        pass

    @abstractmethod
    def delete_score(self, id: str):
        """
        Deletes a score by ID.

        Args:
            id (str): ID of score to delete.

        Returns:
            Dict: The deleted `Score` as a dict.
        """
        pass

    @abstractmethod
    def upload_file(
        self,
        content: Union[bytes, str],
        thread_id: Optional[str] = None,
        mime: Optional[str] = "application/octet-stream",
    ):
        """
        Uploads a file to the server.

        Args:
            content (Union[bytes, str]): The content of the file to upload.
            thread_id (Optional[str]): The ID of the thread associated with the file.
            mime (Optional[str]): The MIME type of the file. Defaults to 'application/octet-stream'.

        Returns:
            Dict: A dictionary containing the object key and URL of the uploaded file, or None values if the upload fails.
        """
        pass

    @abstractmethod
    def create_attachment(
        self,
        thread_id: Optional[str] = None,
        step_id: Optional[str] = None,
        id: Optional[str] = None,
        metadata: Optional[Dict] = None,
        mime: Optional[str] = None,
        name: Optional[str] = None,
        object_key: Optional[str] = None,
        url: Optional[str] = None,
        content: Optional[Union[bytes, str]] = None,
        path: Optional[str] = None,
    ):
        """
        Creates an attachment associated with a thread and step, potentially uploading file content.

        Args:
            thread_id (str): The ID of the thread to which the attachment is linked.
            step_id (str): The ID of the step to which the attachment is linked.
            id (Optional[str]): The ID of the attachment, if updating an existing one.
            metadata (Optional[Dict]): Metadata associated with the attachment.
            mime (Optional[str]): MIME type of the file, if content is provided.
            name (Optional[str]): Name of the attachment.
            object_key (Optional[str]): Object key of the uploaded file, if already known.
            url (Optional[str]): URL of the uploaded file, if already known.
            content (Optional[Union[bytes, str]]): File content to upload.
            path (Optional[str]): Path where the file should be stored.

        Returns:
            `Attachment`: The created attachment.
        """
        pass

    @abstractmethod
    def update_attachment(self, id: str, update_params: AttachmentUpload):
        """
        Updates an existing attachment with new parameters.

        Args:
            id (str): The unique identifier of the attachment to update.
            update_params (AttachmentUpload): The parameters to update in the attachment.

        Returns:
            `Attachment`: The updated attachment.
        """
        pass

    @abstractmethod
    def get_attachment(self, id: str):
        """
        Retrieves an attachment by ID.

        Args:
            id (str): ID of the attachment to retrieve.

        Returns:
            `Attachment`: The attachment object with requested ID.
        """
        pass

    @abstractmethod
    def delete_attachment(self, id: str):
        """
        Deletes an attachment identified by ID.

        Args:
            id (str): The unique identifier of the attachment to delete.

        Returns:
            `Attachment`: The deleted attachment.
        """
        pass

    @abstractmethod
    def create_step(
        self,
        thread_id: Optional[str] = None,
        type: Optional[StepType] = "undefined",
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        input: Optional[Dict] = None,
        output: Optional[Dict] = None,
        metadata: Optional[Dict] = None,
        parent_id: Optional[str] = None,
        name: Optional[str] = None,
        tags: Optional[List[str]] = None,
        root_run_id: Optional[str] = None,
    ):
        """
        Creates a new step with the specified parameters.

        Args:
            thread_id (Optional[str]): The ID of the thread this step is associated with.
            type (Optional[StepType]): The type of the step, defaults to "undefined".
            start_time (Optional[str]): The start time of the step.
            end_time (Optional[str]): The end time of the step.
            input (Optional[Dict]): Input data for the step.
            output (Optional[Dict]): Output data from the step.
            metadata (Optional[Dict]): Metadata associated with the step.
            parent_id (Optional[str]): The ID of the parent step, if any.
            name (Optional[str]): The name of the step.
            tags (Optional[List[str]]): Tags associated with the step.
            root_run_id (Optional[str]): The ID of the root run, if any.

        Returns:
            `Step`: The created step.
        """
        pass

    @abstractmethod
    def update_step(
        self,
        id: str,
        type: Optional[StepType] = None,
        input: Optional[str] = None,
        output: Optional[str] = None,
        metadata: Optional[Dict] = None,
        name: Optional[str] = None,
        tags: Optional[List[str]] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        parent_id: Optional[str] = None,
    ):
        """
        Updates an existing step identified by its ID with new parameters.

        Args:
            id (str): The unique identifier of the step to update.
            type (Optional[StepType]): The type of the step.
            input (Optional[str]): Input data for the step.
            output (Optional[str]): Output data from the step.
            metadata (Optional[Dict]): Metadata associated with the step.
            name (Optional[str]): The name of the step.
            tags (Optional[List[str]]): Tags associated with the step.
            start_time (Optional[str]): The start time of the step.
            end_time (Optional[str]): The end time of the step.
            parent_id (Optional[str]): The ID of the parent step, if any.

        Returns:
            `Step`: The updated step.
        """
        pass

    @abstractmethod
    def get_steps(
        self,
        first: Optional[int] = None,
        after: Optional[str] = None,
        before: Optional[str] = None,
        filters: Optional[steps_filters] = None,
        order_by: Optional[steps_order_by] = None,
    ):
        """
        Fetches a list of steps based on pagination and optional filters.

        Args:
            first (Optional[int]): Number of steps to fetch.
            after (Optional[str]): Cursor for pagination, fetch steps after this cursor.
            before (Optional[str]): Cursor for pagination, fetch steps before this cursor.
            filters (Optional[steps_filters]): Filters to apply on the steps query.
            order_by (Optional[steps_order_by]): Order by clause for steps.

        Returns:
            `PaginatedResponse[Step]`: The list of steps matching the criteria.
        """
        pass

    @abstractmethod
    def get_step(
        self,
        id: str,
    ):
        """
        Retrieves a step by its ID.

        Args:
            id (str): The unique identifier of the step to retrieve.

        Returns:
            `Step`: The step with requested ID.
        """
        pass

    @abstractmethod
    def delete_step(
        self,
        id: str,
    ):
        """
        Deletes a step identified by its ID.

        Args:
            id (str): The unique identifier of the step to delete.

        Returns:
            `bool`: True if the step was deleted successfully, False otherwise.
        """
        pass

    @abstractmethod
    def send_steps(self, steps: List[Union[StepDict, "Step"]]):
        """
        Sends a list of steps to process.
        Step ingestion happens asynchronously if you configured a cache. See [Cache Configuration](https://docs.literalai.com/self-hosting/deployment#4-cache-configuration-optional).

        Args:
            steps (List[Union[StepDict, Step]]): A list of steps or step dictionaries to send.

        Returns:
            `Dict`: Dictionary with keys "ok" (boolean) and "message" (string).
        """
        pass

    @abstractmethod
    def get_generations(
        self,
        first: Optional[int] = None,
        after: Optional[str] = None,
        before: Optional[str] = None,
        filters: Optional[generations_filters] = None,
        order_by: Optional[generations_order_by] = None,
    ):
        """
        Fetches a list of generations based on pagination and optional filters.

        Args:
            first (Optional[int]): The number of generations to retrieve.
            after (Optional[str]): A cursor for use in pagination, fetching records after this cursor.
            before (Optional[str]): A cursor for use in pagination, fetching records before this cursor.
            filters (Optional[generations_filters]): Filters to apply to the generations query.
            order_by (Optional[generations_order_by]): Order by clause for generations.

        Returns:
            A list of generations that match the criteria.
        """
        pass

    @abstractmethod
    def create_generation(
        self, generation: Union[ChatGeneration, CompletionGeneration]
    ):
        """
        Creates a new generation, either a chat or completion type.

        ```py
        from literalai.observability.generation import ChatGeneration
        from literalai import LiteralClient

        literalai_client = LiteralClient(api_key="lsk-***")

        example_generation = ChatGeneration(
            messages=[
                {
                    "role": "user",
                    "content": "Hello, how can I help you today?"
                },
            ],
            message_completion={
                "role": "assistant",
                "content": "Sure, I can help with that. What do you need to know?"
            },
            model="gpt-4o-mini",
            provider="OpenAI"
        )

        literalai_client.api.create_generation(example_generation)
        ```

        Args:
            generation (Union[ChatGeneration, CompletionGeneration]): The generation data to create.

        Returns:
            `Union[ChatGeneration, CompletionGeneration]`: The created generation, either a chat or completion type.
        """
        pass

    @abstractmethod
    def create_dataset(
        self,
        name: str,
        description: Optional[str] = None,
        metadata: Optional[Dict] = None,
        type: DatasetType = "key_value",
    ):
        """
        Creates a new dataset with the specified properties.

        Args:
            name (str): The name of the dataset.
            description (Optional[str]): A description of the dataset.
            metadata (Optional[Dict]): Additional metadata for the dataset.
            type (DatasetType): The type of the dataset, defaults to "key_value".

        Returns:
            `Dataset`: The created dataset, empty initially.
        """
        pass

    @abstractmethod
    def get_dataset(self, id: Optional[str] = None, name: Optional[str] = None):
        """
        Retrieves a dataset by its ID or name.

        Args:
            id (Optional[str]): The unique identifier of the dataset.
            name (Optional[str]): The name of the dataset.

        Returns:
            The dataset data as returned by the REST helper function.
        """
        pass

    @abstractmethod
    def update_dataset(
        self,
        id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ):
        """
        Updates an existing dataset identified by its ID with new properties.

        Args:
            id (str): The unique identifier of the dataset to update.
            name (Optional[str]): A new name for the dataset.
            description (Optional[str]): A new description for the dataset.
            metadata (Optional[Dict]): New or updated metadata for the dataset.

        Returns:
            `Dataset`: The dataset with updated properties.
        """
        pass

    @abstractmethod
    def delete_dataset(self, id: str):
        """
        Deletes a dataset identified by its ID.

        Args:
            id (str): The unique identifier of the dataset to delete.

        Returns:
            `Dataset`: The deleted dataset.
        """
        pass

    @abstractmethod
    def create_experiment(
        self,
        name: str,
        dataset_id: Optional[str] = None,
        prompt_variant_id: Optional[str] = None,
        params: Optional[Dict] = None,
    ):
        """
        Creates a new experiment associated with a specific dataset.

        Args:
            name (str): The name of the experiment.
            dataset_id (Optional[str]): The unique identifier of the dataset.
            prompt_variant_id (Optional[str]): The identifier of the prompt variant to associate to the experiment.
            params (Optional[Dict]): Additional parameters for the experiment.

        Returns:
            DatasetExperiment: The newly created experiment object.
        """
        pass

    @abstractmethod
    def create_experiment_item(self, experiment_item: DatasetExperimentItem):
        """
        Creates an experiment item within an existing experiment.

        Args:
            experiment_item (DatasetExperimentItem): The experiment item to be created, containing all necessary data.

        Returns:
            DatasetExperimentItem: The newly created experiment item with scores attached.
        """
        pass

    @abstractmethod
    def create_dataset_item(
        self,
        dataset_id: str,
        input: Dict,
        expected_output: Optional[Dict] = None,
        metadata: Optional[Dict] = None,
    ):
        """
        Creates an item in a dataset with the specified properties.

        Args:
            dataset_id (str): The unique identifier of the dataset.
            input (Dict): The input data for the dataset item.
            expected_output (Optional[Dict]): The expected output data for the dataset item.
            metadata (Optional[Dict]): Additional metadata for the dataset item.

        Returns:
            DatasetItem: The created dataset item.
        """
        pass

    @abstractmethod
    def get_dataset_item(self, id: str):
        """
        Retrieves a dataset item by ID.

        Args:
            id (str): ID of the `DatasetItem` to retrieve.

        Returns:
            `DatasetItem`: The dataset item.
        """
        pass

    @abstractmethod
    def delete_dataset_item(self, id: str):
        """
        Deletes a dataset item by ID.

        Args:
            id (str): ID of the dataset item to delete.

        Returns:
            `DatasetItem`: The deleted item.
        """
        pass

    @abstractmethod
    def add_step_to_dataset(
        self, dataset_id: str, step_id: str, metadata: Optional[Dict] = None
    ):
        """
        Adds a step to a dataset.

        Args:
            dataset_id (str): The unique identifier of the dataset.
            step_id (str): The unique identifier of the step to add.
            metadata (Optional[Dict]): Additional metadata related to the step to add.

        Returns:
            Dict: The created `DatasetItem`.
        """
        pass

    @abstractmethod
    def add_generation_to_dataset(
        self, dataset_id: str, generation_id: str, metadata: Optional[Dict] = None
    ):
        """
        Adds a generation to a dataset.

        Args:
            dataset_id (str): The unique identifier of the dataset.
            generation_id (str): The unique identifier of the generation to add.
            metadata (Optional[Dict]): Additional metadata related to the generation to add.

        Returns:
            Dict: The created `DatasetItem`.
        """
        pass

    @abstractmethod
    @deprecated("Use get_or_create_prompt_lineage instead")
    def create_prompt_lineage(self, name: str, description: Optional[str] = None):
        """
        Deprecated. Please use **get_or_create_prompt_lineage** instead.
        """
        pass

    @abstractmethod
    def get_or_create_prompt_lineage(
        self, name: str, description: Optional[str] = None
    ):
        """
        Creates a prompt lineage with the specified name and optional description.
        If the prompt lineage with that name already exists, it is returned.

        Args:
            name (str): The name of the prompt lineage.
            description (Optional[str]): An optional description of the prompt lineage.

        Returns:
            `Dict`: The prompt lineage data as a dictionary.
        """
        pass

    @abstractmethod
    @deprecated("Please use `get_or_create_prompt` instead.")
    def create_prompt(
        self,
        name: str,
        template_messages: List[GenerationMessage],
        settings: Optional[ProviderSettings] = None,
    ):
        """
        Deprecated. Please use `get_or_create_prompt` instead.
        """
        pass

    @abstractmethod
    def get_or_create_prompt(
        self,
        name: str,
        template_messages: List[GenerationMessage],
        settings: Optional[ProviderSettings] = None,
        tools: Optional[List[Dict]] = None,
    ):
        """
        A `Prompt` is fully defined by its `name`, `template_messages`, `settings` and tools.
        If a prompt already exists for the given arguments, it is returned.
        Otherwise, a new prompt is created.

        Args:
            name (str): The name of the prompt to retrieve or create.
            template_messages (List[GenerationMessage]): A list of template messages for the prompt.
            settings (Optional[Dict]): Optional settings for the prompt.
            tools (Optional[List[Dict]]): Optional tool options for the model

        Returns:
            Prompt: The prompt that was retrieved or created.
        """
        pass

    @abstractmethod
    def get_prompt(
        self,
        id: Optional[str] = None,
        name: Optional[str] = None,
        version: Optional[int] = None,
    ):
        """
        Gets a prompt either by:
        - `id`
        - `name` and (optional) `version`

        At least the `id` or the `name` must be passed to the function.
        If both are provided, the `id` is used.

        Args:
            id (str): The unique identifier of the prompt to retrieve.
            name (str): The name of the prompt to retrieve.
            version (Optional[int]): The version number of the prompt to retrieve.

        Returns:
            Prompt: The prompt with the given identifier or name.
        """
        pass

    @abstractmethod
    def create_prompt_variant(
        self,
        name: str,
        template_messages: List[GenerationMessage],
        settings: Optional[ProviderSettings] = None,
        tools: Optional[List[Dict]] = None,
    ):
        """
        Creates a prompt variant to use as part of an experiment.
        This variant is not an official Prompt version until manually saved.

        Args:
            name (str): Name of the variant to create.
            template_messages (List[GenerationMessage]): A list of template messages for the prompt.
            settings (Optional[Dict]): Optional settings for the prompt.
            tools (Optional[List[Dict]]): Optional tools for the model.

        Returns:
            prompt_variant_id: The ID of the created prompt variant id, which you can link to an experiment.
        """
        pass

    @abstractmethod
    def get_prompt_ab_testing(self, name: str):
        """
        Get the A/B testing configuration for a prompt lineage.

        Args:
            name (str): The name of the prompt lineage.
        Returns:
            List[PromptRollout]
        """
        pass

    @abstractmethod
    def update_prompt_ab_testing(self, name: str, rollouts: List[PromptRollout]):
        """
        Update the A/B testing configuration for a prompt lineage.

        Args:
            name (str): The name of the prompt lineage.
            rollouts (List[PromptRollout]): The percentage rollout for each prompt version.

        Returns:
            Dict
        """
        pass

    @abstractmethod
    def get_my_project_id(self):
        """
        Retrieves the project ID associated with the API key.

        Returns:
            `str`: The project ID for current API key.
        """
        pass
