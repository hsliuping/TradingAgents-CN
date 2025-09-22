import logging
import uuid
from typing import Any, Callable, Dict, List, Literal, Optional, TypeVar, Union, cast

import httpx
from typing_extensions import deprecated

from literalai.api.base import BaseLiteralAPI, prepare_variables
from literalai.api.helpers.attachment_helpers import (
    AttachmentUpload,
    create_attachment_helper,
    delete_attachment_helper,
    get_attachment_helper,
    update_attachment_helper,
)
from literalai.api.helpers.dataset_helpers import (
    add_generation_to_dataset_helper,
    add_step_to_dataset_helper,
    create_dataset_helper,
    create_dataset_item_helper,
    create_experiment_helper,
    create_experiment_item_helper,
    delete_dataset_helper,
    delete_dataset_item_helper,
    get_dataset_helper,
    get_dataset_item_helper,
    update_dataset_helper,
)
from literalai.api.helpers.generation_helpers import (
    create_generation_helper,
    get_generations_helper,
)
from literalai.api.helpers.prompt_helpers import (
    PromptRollout,
    create_prompt_helper,
    create_prompt_lineage_helper,
    create_prompt_variant_helper,
    get_prompt_ab_testing_helper,
    get_prompt_helper,
    get_prompt_lineage_helper,
    update_prompt_ab_testing_helper,
)
from literalai.api.helpers.score_helpers import (
    ScoreUpdate,
    check_scores_finite,
    create_score_helper,
    create_scores_query_builder,
    delete_score_helper,
    get_scores_helper,
    update_score_helper,
)
from literalai.api.helpers.step_helpers import (
    create_step_helper,
    delete_step_helper,
    get_step_helper,
    get_steps_helper,
    send_steps_helper,
    update_step_helper,
)
from literalai.api.helpers.thread_helpers import (
    create_thread_helper,
    delete_thread_helper,
    get_thread_helper,
    get_threads_helper,
    list_threads_helper,
    update_thread_helper,
    upsert_thread_helper,
)
from literalai.api.helpers.user_helpers import (
    create_user_helper,
    delete_user_helper,
    get_user_helper,
    get_users_helper,
    update_user_helper,
)
from literalai.context import active_steps_var, active_thread_var
from literalai.evaluation.dataset import Dataset, DatasetType
from literalai.evaluation.dataset_experiment import (
    DatasetExperiment,
    DatasetExperimentItem,
)
from literalai.evaluation.dataset_item import DatasetItem
from literalai.my_types import PaginatedResponse, User
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
    BaseGeneration,
    ChatGeneration,
    CompletionGeneration,
    GenerationMessage,
)
from literalai.observability.step import (
    Attachment,
    Score,
    ScoreDict,
    ScoreType,
    Step,
    StepDict,
    StepType,
)
from literalai.observability.thread import Thread
from literalai.prompt_engineering.prompt import Prompt, ProviderSettings

logger = logging.getLogger(__name__)


class LiteralAPI(BaseLiteralAPI):
    """
    ```python
    from literalai import LiteralClient
    # Initialize the client
    literalai_client = LiteralClient(api_key="your_api_key_here")
    # Access the API's methods
    print(literalai_client.api)
    ```
    """

    R = TypeVar("R")

    def make_gql_call(
        self,
        description: str,
        query: str,
        variables: dict[str, Any],
        timeout: Optional[int] = 10,
    ) -> dict:
        def raise_error(error):
            logger.error(f"Failed to {description}: {error}")
            raise Exception(error)

        variables = prepare_variables(variables)
        with httpx.Client(follow_redirects=True) as client:
            response = client.post(
                self.graphql_endpoint,
                json={"query": query, "variables": variables},
                headers=self.headers,
                timeout=timeout,
            )

            try:
                response.raise_for_status()
            except httpx.HTTPStatusError:
                raise_error(f"Failed to {description}: {response.text}")

            try:
                json = response.json()
            except ValueError as e:
                raise_error(
                    f"Failed to parse JSON response: {e}, content: {response.content!r}"
                )

            if json.get("errors"):
                raise_error(json["errors"])

            if json.get("data"):
                if isinstance(json["data"], dict):
                    for value in json["data"].values():
                        if value and value.get("ok") is False:
                            raise_error(
                                f"""Failed to {description}: {value.get("message")}"""
                            )

            return json

    def make_rest_call(self, subpath: str, body: Dict[str, Any]) -> Dict:
        with httpx.Client(follow_redirects=True) as client:
            response = client.post(
                self.rest_endpoint + subpath,
                json=body,
                headers=self.headers,
                timeout=20,
            )

            try:
                response.raise_for_status()
            except httpx.HTTPStatusError:
                message = f"Failed to call {subpath}: {response.text}"
                logger.error(message)
                raise Exception(message)

            try:
                return response.json()
            except ValueError as e:
                raise ValueError(
                    f"Failed to parse JSON response: {e}, content: {response.content!r}"
                )

    def gql_helper(
        self,
        query: str,
        description: str,
        variables: Dict,
        process_response: Callable[..., R],
        timeout: Optional[int] = None,
    ) -> R:
        response = self.make_gql_call(description, query, variables, timeout)
        return process_response(response)

    ##################################################################################
    #                                User APIs                                       #
    ##################################################################################

    def get_users(
        self,
        first: Optional[int] = None,
        after: Optional[str] = None,
        before: Optional[str] = None,
        filters: Optional[users_filters] = None,
    ) -> PaginatedResponse["User"]:
        return self.gql_helper(*get_users_helper(first, after, before, filters))

    def get_user(
        self, id: Optional[str] = None, identifier: Optional[str] = None
    ) -> "User":
        return self.gql_helper(*get_user_helper(id, identifier))

    def create_user(self, identifier: str, metadata: Optional[Dict] = None) -> "User":
        return self.gql_helper(*create_user_helper(identifier, metadata))

    def update_user(
        self, id: str, identifier: Optional[str] = None, metadata: Optional[Dict] = None
    ) -> "User":
        return self.gql_helper(*update_user_helper(id, identifier, metadata))

    def delete_user(self, id: str) -> Dict:
        return self.gql_helper(*delete_user_helper(id))

    def get_or_create_user(
        self, identifier: str, metadata: Optional[Dict] = None
    ) -> "User":
        user = self.get_user(identifier=identifier)
        if user:
            return user

        return self.create_user(identifier, metadata)

    ##################################################################################
    #                                 Thread APIs                                    #
    ##################################################################################

    def get_threads(
        self,
        first: Optional[int] = None,
        after: Optional[str] = None,
        before: Optional[str] = None,
        filters: Optional[threads_filters] = None,
        order_by: Optional[threads_order_by] = None,
        step_types_to_keep: Optional[List[StepType]] = None,
    ) -> PaginatedResponse["Thread"]:
        return self.gql_helper(
            *get_threads_helper(
                first, after, before, filters, order_by, step_types_to_keep
            )
        )

    def list_threads(
        self,
        first: Optional[int] = None,
        after: Optional[str] = None,
        before: Optional[str] = None,
        filters: Optional[threads_filters] = None,
        order_by: Optional[threads_order_by] = None,
    ) -> PaginatedResponse["Thread"]:
        return self.gql_helper(
            *list_threads_helper(first, after, before, filters, order_by)
        )

    def get_thread(self, id: str) -> "Thread":
        return self.gql_helper(*get_thread_helper(id))

    def create_thread(
        self,
        name: Optional[str] = None,
        metadata: Optional[Dict] = None,
        participant_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> "Thread":
        return self.gql_helper(
            *create_thread_helper(name, metadata, participant_id, tags)
        )

    def upsert_thread(
        self,
        id: str,
        name: Optional[str] = None,
        metadata: Optional[Dict] = None,
        participant_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> "Thread":
        return self.gql_helper(
            *upsert_thread_helper(id, name, metadata, participant_id, tags)
        )

    def update_thread(
        self,
        id: str,
        name: Optional[str] = None,
        metadata: Optional[Dict] = None,
        participant_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> "Thread":
        return self.gql_helper(
            *update_thread_helper(id, name, metadata, participant_id, tags)
        )

    def delete_thread(self, id: str) -> bool:
        return self.gql_helper(*delete_thread_helper(id))

    ##################################################################################
    #                                  Score APIs                                    #
    ##################################################################################

    def get_scores(
        self,
        first: Optional[int] = None,
        after: Optional[str] = None,
        before: Optional[str] = None,
        filters: Optional[scores_filters] = None,
        order_by: Optional[scores_order_by] = None,
    ) -> PaginatedResponse["Score"]:
        return self.gql_helper(
            *get_scores_helper(first, after, before, filters, order_by)
        )

    def create_scores(self, scores: List["ScoreDict"]):
        check_scores_finite(scores)

        query = create_scores_query_builder(scores)
        variables = {}
        for id, score in enumerate(scores):
            for k, v in score.items():
                variables[f"{k}_{id}"] = v

        def process_response(response):
            return [x for x in response["data"].values()]

        return self.gql_helper(query, "create scores", variables, process_response)

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
    ) -> "Score":
        if generation_id:
            logger.warning(
                "generation_id is deprecated and will be removed in a future version, please use step_id instead"
            )
        check_scores_finite([{"name": name, "value": value}])

        return self.gql_helper(
            *create_score_helper(
                name,
                value,
                type,
                step_id,
                dataset_experiment_item_id,
                comment,
                tags,
            )
        )

    def update_score(
        self,
        id: str,
        update_params: ScoreUpdate,
    ) -> "Score":
        return self.gql_helper(*update_score_helper(id, update_params))

    def delete_score(self, id: str) -> Dict:
        return self.gql_helper(*delete_score_helper(id))

    ##################################################################################
    #                                Attachment APIs                                 #
    ##################################################################################

    def upload_file(
        self,
        content: Union[bytes, str],
        thread_id: Optional[str] = None,
        mime: Optional[str] = "application/octet-stream",
    ) -> Dict:
        id = str(uuid.uuid4())
        body = {"fileName": id, "contentType": mime}
        if thread_id:
            body["threadId"] = thread_id

        path = "/api/upload/file"

        with httpx.Client(follow_redirects=True) as client:
            response = client.post(
                f"{self.url}{path}",
                json=body,
                headers=self.headers,
            )
            if response.status_code >= 400:
                reason = response.text
                logger.error(f"Failed to sign upload url: {reason}")
                return {"object_key": None, "url": None}
            json_res = response.json()
        method = "put" if "put" in json_res else "post"
        request_dict: Dict[str, Any] = json_res.get(method, {})
        url: Optional[str] = request_dict.get("url")

        if not url:
            raise Exception("Invalid server response")
        headers: Optional[Dict] = request_dict.get("headers")
        fields: Dict = request_dict.get("fields", {})
        object_key: Optional[str] = fields.get("key")
        upload_type: Literal["raw", "multipart"] = cast(
            Literal["raw", "multipart"], request_dict.get("uploadType", "multipart")
        )
        signed_url: Optional[str] = json_res.get("signedUrl")

        # Prepare form data
        form_data = (
            {}
        )  # type: Dict[str, Union[tuple[Union[str, None], Any], tuple[Union[str, None], Any, Any]]]
        for field_name, field_value in fields.items():
            form_data[field_name] = (None, field_value)

        # Add file to the form_data
        # Note: The content_type parameter is not needed here, as the correct MIME type should be set
        # in the 'Content-Type' field from upload_details
        form_data["file"] = (id, content, mime)

        with httpx.Client(follow_redirects=True) as client:
            if upload_type == "raw":
                upload_response = client.request(
                    url=url,
                    headers=headers,
                    method=method,
                    data=content,  # type: ignore
                )
            else:
                upload_response = client.request(
                    url=url,
                    headers=headers,
                    method=method,
                    files=form_data,
                )  # type: ignore
            try:
                upload_response.raise_for_status()
                return {"object_key": object_key, "url": signed_url}
            except Exception as e:
                logger.error(f"Failed to upload file: {str(e)}")
                return {"object_key": None, "url": None}

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
    ) -> "Attachment":
        if not thread_id:
            if active_thread := active_thread_var.get(None):
                thread_id = active_thread.id

        if not step_id:
            if active_steps := active_steps_var.get():
                step_id = active_steps[-1].id
            else:
                raise Exception("No step_id provided and no active step found.")

        (
            query,
            description,
            variables,
            content,
            process_response,
        ) = create_attachment_helper(
            thread_id=thread_id,
            step_id=step_id,
            id=id,
            metadata=metadata,
            mime=mime,
            name=name,
            object_key=object_key,
            url=url,
            content=content,
            path=path,
        )

        if content:
            uploaded = self.upload_file(content=content, thread_id=thread_id, mime=mime)

            if uploaded["object_key"] is None or uploaded["url"] is None:
                raise Exception("Failed to upload file")

            object_key = uploaded["object_key"]
            if object_key:
                variables["objectKey"] = object_key
            else:
                variables["url"] = uploaded["url"]

        response = self.make_gql_call(description, query, variables)
        return process_response(response)

    def update_attachment(
        self, id: str, update_params: AttachmentUpload
    ) -> "Attachment":
        return self.gql_helper(*update_attachment_helper(id, update_params))

    def get_attachment(self, id: str) -> Optional["Attachment"]:
        return self.gql_helper(*get_attachment_helper(id))

    def delete_attachment(self, id: str) -> Dict:
        return self.gql_helper(*delete_attachment_helper(id))

    ##################################################################################
    #                                     Step APIs                                  #
    ##################################################################################

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
    ) -> Step:
        return self.gql_helper(
            *create_step_helper(
                thread_id=thread_id,
                type=type,
                start_time=start_time,
                end_time=end_time,
                input=input,
                output=output,
                metadata=metadata,
                parent_id=parent_id,
                name=name,
                tags=tags,
                root_run_id=root_run_id,
            )
        )

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
    ) -> "Step":
        return self.gql_helper(
            *update_step_helper(
                id=id,
                type=type,
                input=input,
                output=output,
                metadata=metadata,
                name=name,
                tags=tags,
                start_time=start_time,
                end_time=end_time,
                parent_id=parent_id,
            )
        )

    def get_steps(
        self,
        first: Optional[int] = None,
        after: Optional[str] = None,
        before: Optional[str] = None,
        filters: Optional[steps_filters] = None,
        order_by: Optional[steps_order_by] = None,
    ) -> PaginatedResponse["Step"]:
        return self.gql_helper(
            *get_steps_helper(first, after, before, filters, order_by)
        )

    def get_step(
        self,
        id: str,
    ) -> Optional["Step"]:
        return self.gql_helper(*get_step_helper(id=id))

    def delete_step(
        self,
        id: str,
    ) -> bool:
        return self.gql_helper(*delete_step_helper(id=id))

    def send_steps(self, steps: List[Union["StepDict", "Step"]]):
        return self.gql_helper(*send_steps_helper(steps=steps))

    ##################################################################################
    #                                 Generation APIs                                #
    ##################################################################################

    def get_generations(
        self,
        first: Optional[int] = None,
        after: Optional[str] = None,
        before: Optional[str] = None,
        filters: Optional[generations_filters] = None,
        order_by: Optional[generations_order_by] = None,
    ) -> PaginatedResponse["BaseGeneration"]:
        return self.gql_helper(
            *get_generations_helper(first, after, before, filters, order_by)
        )

    def create_generation(
        self, generation: Union["ChatGeneration", "CompletionGeneration"]
    ) -> Union["ChatGeneration", "CompletionGeneration"]:
        return self.gql_helper(*create_generation_helper(generation))

    ##################################################################################
    #                                   Dataset APIs                                 #
    ##################################################################################

    def create_dataset(
        self,
        name: str,
        description: Optional[str] = None,
        metadata: Optional[Dict] = None,
        type: DatasetType = "key_value",
    ) -> "Dataset":
        return self.gql_helper(
            *create_dataset_helper(self, name, description, metadata, type)
        )

    def get_dataset(
        self, id: Optional[str] = None, name: Optional[str] = None
    ) -> Optional["Dataset"]:
        subpath, _, variables, process_response = get_dataset_helper(
            self, id=id, name=name
        )
        response = self.make_rest_call(subpath, variables)
        return process_response(response)

    def update_dataset(
        self,
        id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> "Dataset":
        return self.gql_helper(
            *update_dataset_helper(self, id, name, description, metadata)
        )

    def delete_dataset(self, id: str) -> "Dataset":
        return self.gql_helper(*delete_dataset_helper(self, id))

    ##################################################################################
    #                                  Experiment APIs                               #
    ##################################################################################

    def create_experiment(
        self,
        name: str,
        dataset_id: Optional[str] = None,
        prompt_variant_id: Optional[str] = None,
        params: Optional[Dict] = None,
    ) -> "DatasetExperiment":
        return self.gql_helper(
            *create_experiment_helper(
                api=self,
                name=name,
                dataset_id=dataset_id,
                prompt_variant_id=prompt_variant_id,
                params=params,
            )
        )

    def create_experiment_item(
        self, experiment_item: DatasetExperimentItem
    ) -> "DatasetExperimentItem":
        # Create the dataset experiment item
        result = self.gql_helper(
            *create_experiment_item_helper(
                dataset_experiment_id=experiment_item.dataset_experiment_id,
                dataset_item_id=experiment_item.dataset_item_id,
                experiment_run_id=experiment_item.experiment_run_id,
                input=experiment_item.input,
                output=experiment_item.output,
            )
        )

        for score in experiment_item.scores:
            score["datasetExperimentItemId"] = result.id

        # Create the scores and add to experiment item.
        result.scores = self.create_scores(experiment_item.scores)

        return result

    ##################################################################################
    #                                 Dataset Item APIs                              #
    ##################################################################################

    def create_dataset_item(
        self,
        dataset_id: str,
        input: Dict,
        expected_output: Optional[Dict] = None,
        metadata: Optional[Dict] = None,
    ) -> "DatasetItem":
        return self.gql_helper(
            *create_dataset_item_helper(dataset_id, input, expected_output, metadata)
        )

    def get_dataset_item(self, id: str) -> Optional["DatasetItem"]:
        return self.gql_helper(*get_dataset_item_helper(id))

    def delete_dataset_item(self, id: str) -> "DatasetItem":
        return self.gql_helper(*delete_dataset_item_helper(id))

    def add_step_to_dataset(
        self, dataset_id: str, step_id: str, metadata: Optional[Dict] = None
    ) -> "DatasetItem":
        return self.gql_helper(
            *add_step_to_dataset_helper(dataset_id, step_id, metadata)
        )

    def add_generation_to_dataset(
        self, dataset_id: str, generation_id: str, metadata: Optional[Dict] = None
    ) -> "DatasetItem":
        return self.gql_helper(
            *add_generation_to_dataset_helper(dataset_id, generation_id, metadata)
        )

    ##################################################################################
    #                                   Prompt APIs                                  #
    ##################################################################################

    def get_or_create_prompt_lineage(
        self, name: str, description: Optional[str] = None
    ) -> Dict:
        return self.gql_helper(*create_prompt_lineage_helper(name, description))

    @deprecated("Use get_or_create_prompt_lineage instead")
    def create_prompt_lineage(
        self, name: str, description: Optional[str] = None
    ) -> Dict:
        return self.get_or_create_prompt_lineage(name, description)

    def get_or_create_prompt(
        self,
        name: str,
        template_messages: List[GenerationMessage],
        settings: Optional[ProviderSettings] = None,
        tools: Optional[List[Dict]] = None,
    ) -> "Prompt":
        lineage = self.get_or_create_prompt_lineage(name)
        lineage_id = lineage["id"]
        return self.gql_helper(
            *create_prompt_helper(self, lineage_id, template_messages, settings, tools)
        )

    @deprecated("Please use `get_or_create_prompt` instead.")
    def create_prompt(
        self,
        name: str,
        template_messages: List[GenerationMessage],
        settings: Optional[ProviderSettings] = None,
    ) -> "Prompt":
        return self.get_or_create_prompt(name, template_messages, settings)

    def get_prompt(
        self,
        id: Optional[str] = None,
        name: Optional[str] = None,
        version: Optional[int] = None,
    ) -> "Prompt":
        if not (id or name):
            raise ValueError("At least the `id` or the `name` must be provided.")

        (
            get_prompt_query,
            description,
            variables,
            process_response,
            timeout,
            cached_prompt,
        ) = get_prompt_helper(
            api=self, id=id, name=name, version=version, cache=self.cache
        )

        try:
            if id:
                prompt = self.gql_helper(
                    get_prompt_query, description, variables, process_response, timeout
                )
            elif name:
                prompt = self.gql_helper(
                    get_prompt_query, description, variables, process_response, timeout
                )

            return prompt

        except Exception as e:
            if cached_prompt:
                logger.warning("Failed to get prompt from API, returning cached prompt")
                return cached_prompt

            raise e

    def create_prompt_variant(
        self,
        name: str,
        template_messages: List[GenerationMessage],
        settings: Optional[ProviderSettings] = None,
        tools: Optional[List[Dict]] = None,
    ) -> Optional[str]:
        lineage = self.gql_helper(*get_prompt_lineage_helper(name))
        lineage_id = lineage["id"] if lineage else None
        return self.gql_helper(
            *create_prompt_variant_helper(
                lineage_id, template_messages, settings, tools
            )
        )

    def get_prompt_ab_testing(self, name: str) -> List["PromptRollout"]:
        return self.gql_helper(*get_prompt_ab_testing_helper(name=name))

    def update_prompt_ab_testing(
        self, name: str, rollouts: List["PromptRollout"]
    ) -> Dict:
        return self.gql_helper(
            *update_prompt_ab_testing_helper(name=name, rollouts=rollouts)
        )

    ##################################################################################
    #                                  Misc APIs                                   #
    ##################################################################################

    def get_my_project_id(self) -> str:
        response = self.make_rest_call("/my-project", {})
        return response["projectId"]
