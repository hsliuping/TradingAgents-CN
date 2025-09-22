"""The Async LangSmith Client."""

from __future__ import annotations

import asyncio
import contextlib
import datetime
import json
import uuid
from collections.abc import AsyncGenerator, AsyncIterator, Mapping, Sequence
from typing import (
    Any,
    Literal,
    Optional,
    Union,
    cast,
)

import httpx

from langsmith import client as ls_client
from langsmith import schemas as ls_schemas
from langsmith import utils as ls_utils
from langsmith._internal import _beta_decorator as ls_beta

ID_TYPE = Union[uuid.UUID, str]


class AsyncClient:
    """Async Client for interacting with the LangSmith API."""

    __slots__ = ("_retry_config", "_client", "_web_url", "_settings")

    def __init__(
        self,
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout_ms: Optional[
            Union[
                int, tuple[Optional[int], Optional[int], Optional[int], Optional[int]]
            ]
        ] = None,
        retry_config: Optional[Mapping[str, Any]] = None,
        web_url: Optional[str] = None,
    ):
        """Initialize the async client."""
        self._retry_config = retry_config or {"max_retries": 3}
        _headers = {
            "Content-Type": "application/json",
        }
        api_key = ls_utils.get_api_key(api_key)
        api_url = ls_utils.get_api_url(api_url)
        if api_key:
            _headers[ls_client.X_API_KEY] = api_key
        ls_client._validate_api_key_if_hosted(api_url, api_key)

        if isinstance(timeout_ms, int):
            timeout_: Union[tuple, float] = (timeout_ms / 1000, None, None, None)
        elif isinstance(timeout_ms, tuple):
            timeout_ = tuple([t / 1000 if t is not None else None for t in timeout_ms])
        else:
            timeout_ = 10
        self._client = httpx.AsyncClient(
            base_url=api_url, headers=_headers, timeout=timeout_
        )
        self._web_url = web_url
        self._settings: Optional[ls_schemas.LangSmithSettings] = None

    async def __aenter__(self) -> AsyncClient:
        """Enter the async client."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit the async client."""
        await self.aclose()

    async def aclose(self):
        """Close the async client."""
        await self._client.aclose()

    @property
    def _api_url(self):
        return str(self._client.base_url)

    @property
    def _host_url(self) -> str:
        """The web host url."""
        return ls_utils.get_host_url(self._web_url, self._api_url)

    async def _arequest_with_retries(
        self,
        method: str,
        endpoint: str,
        **kwargs: Any,
    ) -> httpx.Response:
        """Make an async HTTP request with retries."""
        max_retries = cast(int, self._retry_config.get("max_retries", 3))

        # Python requests library used by the normal Client filters out params with None values
        # The httpx library does not. Filter them out here to keep behavior consistent
        if "params" in kwargs:
            params = kwargs["params"]
            filtered_params = {k: v for k, v in params.items() if v is not None}
            kwargs["params"] = filtered_params

        for attempt in range(max_retries):
            try:
                response = await self._client.request(method, endpoint, **kwargs)
                ls_utils.raise_for_status_with_text(response)
                return response
            except httpx.HTTPStatusError as e:
                if response.status_code == 500:
                    raise ls_utils.LangSmithAPIError(
                        f"Server error caused failure to {method}"
                        f" {endpoint} in"
                        f" LangSmith API. {repr(e)}"
                    )
                elif response.status_code == 408:
                    raise ls_utils.LangSmithRequestTimeout(
                        f"Client took too long to send request to {method}{endpoint}"
                    )
                elif response.status_code == 429:
                    raise ls_utils.LangSmithRateLimitError(
                        f"Rate limit exceeded for {endpoint}. {repr(e)}"
                    )
                elif response.status_code == 401:
                    raise ls_utils.LangSmithAuthError(
                        f"Authentication failed for {endpoint}. {repr(e)}"
                    )
                elif response.status_code == 404:
                    raise ls_utils.LangSmithNotFoundError(
                        f"Resource not found for {endpoint}. {repr(e)}"
                    )
                elif response.status_code == 409:
                    raise ls_utils.LangSmithConflictError(
                        f"Conflict for {endpoint}. {repr(e)}"
                    )
                else:
                    raise ls_utils.LangSmithError(
                        f"Failed to {method} {endpoint} in LangSmith API. {repr(e)}"
                    )
            except httpx.RequestError as e:
                if attempt == max_retries - 1:
                    raise ls_utils.LangSmithConnectionError(f"Request error: {repr(e)}")
                await asyncio.sleep(2**attempt)
        raise ls_utils.LangSmithAPIError(
            "Unexpected error connecting to the LangSmith API"
        )

    async def _aget_paginated_list(
        self,
        path: str,
        params: Optional[dict[str, Any]] = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Get a paginated list of items."""
        params = params or {}
        offset = params.get("offset", 0)
        params["limit"] = params.get("limit", 100)
        while True:
            params["offset"] = offset
            response = await self._arequest_with_retries("GET", path, params=params)
            items = response.json()
            if not items:
                break
            for item in items:
                yield item
            if len(items) < params["limit"]:
                break
            offset += len(items)

    async def _aget_cursor_paginated_list(
        self,
        path: str,
        *,
        body: Optional[dict] = None,
        request_method: str = "POST",
        data_key: str = "runs",
    ) -> AsyncIterator[dict]:
        """Get a cursor paginated list of items."""
        params_ = body.copy() if body else {}
        while True:
            response = await self._arequest_with_retries(
                request_method,
                path,
                content=ls_client._dumps_json(params_),
            )
            response_body = response.json()
            if not response_body:
                break
            if not response_body.get(data_key):
                break
            for run in response_body[data_key]:
                yield run
            cursors = response_body.get("cursors")
            if not cursors:
                break
            if not cursors.get("next"):
                break
            params_["cursor"] = cursors["next"]

    async def create_run(
        self,
        name: str,
        inputs: dict[str, Any],
        run_type: str,
        *,
        project_name: Optional[str] = None,
        revision_id: Optional[ls_client.ID_TYPE] = None,
        **kwargs: Any,
    ) -> None:
        """Create a run."""
        run_create = {
            "name": name,
            "id": kwargs.get("id") or uuid.uuid4(),
            "inputs": inputs,
            "run_type": run_type,
            "session_name": project_name or ls_utils.get_tracer_project(),
            "revision_id": revision_id,
            **kwargs,
        }
        await self._arequest_with_retries(
            "POST", "/runs", content=ls_client._dumps_json(run_create)
        )

    async def update_run(
        self,
        run_id: ls_client.ID_TYPE,
        **kwargs: Any,
    ) -> None:
        """Update a run."""
        data = {**kwargs, "id": ls_client._as_uuid(run_id)}
        await self._arequest_with_retries(
            "PATCH",
            f"/runs/{ls_client._as_uuid(run_id)}",
            content=ls_client._dumps_json(data),
        )

    async def read_run(self, run_id: ls_client.ID_TYPE) -> ls_schemas.Run:
        """Read a run."""
        response = await self._arequest_with_retries(
            "GET",
            f"/runs/{ls_client._as_uuid(run_id)}",
        )
        return ls_schemas.Run(**response.json())

    async def list_runs(
        self,
        *,
        project_id: Optional[
            Union[ls_client.ID_TYPE, Sequence[ls_client.ID_TYPE]]
        ] = None,
        project_name: Optional[Union[str, Sequence[str]]] = None,
        run_type: Optional[str] = None,
        trace_id: Optional[ls_client.ID_TYPE] = None,
        reference_example_id: Optional[ls_client.ID_TYPE] = None,
        query: Optional[str] = None,
        filter: Optional[str] = None,
        trace_filter: Optional[str] = None,
        tree_filter: Optional[str] = None,
        is_root: Optional[bool] = None,
        parent_run_id: Optional[ls_client.ID_TYPE] = None,
        start_time: Optional[datetime.datetime] = None,
        error: Optional[bool] = None,
        run_ids: Optional[Sequence[ls_client.ID_TYPE]] = None,
        select: Optional[Sequence[str]] = None,
        limit: Optional[int] = None,
        **kwargs: Any,
    ) -> AsyncIterator[ls_schemas.Run]:
        """List runs from the LangSmith API.

        Parameters
        ----------
        project_id : UUID or None, default=None
            The ID(s) of the project to filter by.
        project_name : str or None, default=None
            The name(s) of the project to filter by.
        run_type : str or None, default=None
            The type of the runs to filter by.
        trace_id : UUID or None, default=None
            The ID of the trace to filter by.
        reference_example_id : UUID or None, default=None
            The ID of the reference example to filter by.
        query : str or None, default=None
            The query string to filter by.
        filter : str or None, default=None
            The filter string to filter by.
        trace_filter : str or None, default=None
            Filter to apply to the ROOT run in the trace tree. This is meant to
            be used in conjunction with the regular `filter` parameter to let you
            filter runs by attributes of the root run within a trace.
        tree_filter : str or None, default=None
            Filter to apply to OTHER runs in the trace tree, including
            sibling and child runs. This is meant to be used in conjunction with
            the regular `filter` parameter to let you filter runs by attributes
            of any run within a trace.
        is_root : bool or None, default=None
            Whether to filter by root runs.
        parent_run_id : UUID or None, default=None
            The ID of the parent run to filter by.
        start_time : datetime or None, default=None
            The start time to filter by.
        error : bool or None, default=None
            Whether to filter by error status.
        run_ids : List[str or UUID] or None, default=None
            The IDs of the runs to filter by.
        limit : int or None, default=None
            The maximum number of runs to return.
        **kwargs : Any
            Additional keyword arguments.

        Yields:
        ------
        Run
            The runs.

        Examples:
        --------
        List all runs in a project:

        .. code-block:: python

            project_runs = client.list_runs(project_name="<your_project>")

        List LLM and Chat runs in the last 24 hours:

        .. code-block:: python

            todays_llm_runs = client.list_runs(
                project_name="<your_project>",
                start_time=datetime.now() - timedelta(days=1),
                run_type="llm",
            )

        List root traces in a project:

        .. code-block:: python

            root_runs = client.list_runs(project_name="<your_project>", is_root=1)

        List runs without errors:

        .. code-block:: python

            correct_runs = client.list_runs(project_name="<your_project>", error=False)

        List runs and only return their inputs/outputs (to speed up the query):

        .. code-block:: python

            input_output_runs = client.list_runs(
                project_name="<your_project>", select=["inputs", "outputs"]
            )

        List runs by run ID:

        .. code-block:: python

            run_ids = [
                "a36092d2-4ad5-4fb4-9c0d-0dba9a2ed836",
                "9398e6be-964f-4aa4-8ae9-ad78cd4b7074",
            ]
            selected_runs = client.list_runs(id=run_ids)

        List all "chain" type runs that took more than 10 seconds and had
        `total_tokens` greater than 5000:

        .. code-block:: python

            chain_runs = client.list_runs(
                project_name="<your_project>",
                filter='and(eq(run_type, "chain"), gt(latency, 10), gt(total_tokens, 5000))',
            )

        List all runs called "extractor" whose root of the trace was assigned feedback "user_score" score of 1:

        .. code-block:: python

            good_extractor_runs = client.list_runs(
                project_name="<your_project>",
                filter='eq(name, "extractor")',
                trace_filter='and(eq(feedback_key, "user_score"), eq(feedback_score, 1))',
            )

        List all runs that started after a specific timestamp and either have "error" not equal to null or a "Correctness" feedback score equal to 0:

        .. code-block:: python

            complex_runs = client.list_runs(
                project_name="<your_project>",
                filter='and(gt(start_time, "2023-07-15T12:34:56Z"), or(neq(error, null), and(eq(feedback_key, "Correctness"), eq(feedback_score, 0.0))))',
            )

        List all runs where `tags` include "experimental" or "beta" and `latency` is greater than 2 seconds:

        .. code-block:: python

            tagged_runs = client.list_runs(
                project_name="<your_project>",
                filter='and(or(has(tags, "experimental"), has(tags, "beta")), gt(latency, 2))',
            )
        """
        project_ids = []
        if isinstance(project_id, (uuid.UUID, str)):
            project_ids.append(project_id)
        elif isinstance(project_id, list):
            project_ids.extend(project_id)
        if project_name is not None:
            if isinstance(project_name, str):
                project_name = [project_name]
            projects = await asyncio.gather(
                *[self.read_project(project_name=name) for name in project_name]
            )
            project_ids.extend([project.id for project in projects])

        body_query: dict[str, Any] = {
            "session": project_ids if project_ids else None,
            "run_type": run_type,
            "reference_example": (
                [reference_example_id] if reference_example_id else None
            ),
            "query": query,
            "filter": filter,
            "trace_filter": trace_filter,
            "tree_filter": tree_filter,
            "is_root": is_root,
            "parent_run": parent_run_id,
            "start_time": start_time.isoformat() if start_time else None,
            "error": error,
            "id": run_ids,
            "trace": trace_id,
            "select": select,
            **kwargs,
        }
        if project_ids:
            body_query["session"] = [
                str(ls_client._as_uuid(id_)) for id_ in project_ids
            ]
        body = {k: v for k, v in body_query.items() if v is not None}
        ix = 0
        async for run in self._aget_cursor_paginated_list("/runs/query", body=body):
            yield ls_schemas.Run(**run)
            ix += 1
            if limit is not None and ix >= limit:
                break

    async def share_run(
        self, run_id: ls_client.ID_TYPE, *, share_id: Optional[ls_client.ID_TYPE] = None
    ) -> str:
        """Get a share link for a run asynchronously.

        Args:
            run_id (ID_TYPE): The ID of the run to share.
            share_id (Optional[ID_TYPE], optional): Custom share ID.
                If not provided, a random UUID will be generated.

        Returns:
            str: The URL of the shared run.

        Raises:
            httpx.HTTPStatusError: If the API request fails.
        """
        run_id_ = ls_client._as_uuid(run_id, "run_id")
        data = {
            "run_id": str(run_id_),
            "share_token": str(share_id or uuid.uuid4()),
        }
        response = await self._arequest_with_retries(
            "PUT",
            f"/runs/{run_id_}/share",
            content=ls_client._dumps_json(data),
        )
        ls_utils.raise_for_status_with_text(response)
        share_token = response.json()["share_token"]
        return f"{self._host_url}/public/{share_token}/r"

    async def run_is_shared(self, run_id: ls_client.ID_TYPE) -> bool:
        """Get share state for a run asynchronously."""
        link = await self.read_run_shared_link(ls_client._as_uuid(run_id, "run_id"))
        return link is not None

    async def read_run_shared_link(self, run_id: ls_client.ID_TYPE) -> Optional[str]:
        """Retrieve the shared link for a specific run asynchronously.

        Args:
            run_id (ID_TYPE): The ID of the run.

        Returns:
            Optional[str]: The shared link for the run, or None if the link is not
            available.

        Raises:
            httpx.HTTPStatusError: If the API request fails.
        """
        response = await self._arequest_with_retries(
            "GET",
            f"/runs/{ls_client._as_uuid(run_id, 'run_id')}/share",
        )
        ls_utils.raise_for_status_with_text(response)
        result = response.json()
        if result is None or "share_token" not in result:
            return None
        return f"{self._host_url}/public/{result['share_token']}/r"

    async def create_project(
        self,
        project_name: str,
        **kwargs: Any,
    ) -> ls_schemas.TracerSession:
        """Create a project."""
        data = {"name": project_name, **kwargs}
        response = await self._arequest_with_retries(
            "POST", "/sessions", content=ls_client._dumps_json(data)
        )
        return ls_schemas.TracerSession(**response.json())

    async def read_project(
        self,
        project_name: Optional[str] = None,
        project_id: Optional[ls_client.ID_TYPE] = None,
    ) -> ls_schemas.TracerSession:
        """Read a project."""
        if project_id:
            response = await self._arequest_with_retries(
                "GET", f"/sessions/{ls_client._as_uuid(project_id)}"
            )
        elif project_name:
            response = await self._arequest_with_retries(
                "GET", "/sessions", params={"name": project_name}
            )
        else:
            raise ValueError("Either project_name or project_id must be provided")

        data = response.json()
        if isinstance(data, list):
            if not data:
                raise ls_utils.LangSmithNotFoundError(
                    f"Project {project_name} not found"
                )
            return ls_schemas.TracerSession(**data[0])
        return ls_schemas.TracerSession(**data)

    async def delete_project(
        self, *, project_name: Optional[str] = None, project_id: Optional[str] = None
    ) -> None:
        """Delete a project from LangSmith.

        Parameters
        ----------
        project_name : str or None, default=None
            The name of the project to delete.
        project_id : str or None, default=None
            The ID of the project to delete.
        """
        if project_id is None and project_name is None:
            raise ValueError("Either project_name or project_id must be provided")
        if project_id is None:
            project = await self.read_project(project_name=project_name)
            project_id = str(project.id)
        if not project_id:
            raise ValueError("Project not found")
        await self._arequest_with_retries(
            "DELETE",
            f"/sessions/{ls_client._as_uuid(project_id)}",
        )

    async def create_dataset(
        self,
        dataset_name: str,
        **kwargs: Any,
    ) -> ls_schemas.Dataset:
        """Create a dataset."""
        data = {"name": dataset_name, **kwargs}
        response = await self._arequest_with_retries(
            "POST", "/datasets", content=ls_client._dumps_json(data)
        )
        return ls_schemas.Dataset(**response.json())

    async def read_dataset(
        self,
        dataset_name: Optional[str] = None,
        dataset_id: Optional[ls_client.ID_TYPE] = None,
    ) -> ls_schemas.Dataset:
        """Read a dataset."""
        if dataset_id:
            response = await self._arequest_with_retries(
                "GET", f"/datasets/{ls_client._as_uuid(dataset_id)}"
            )
        elif dataset_name:
            response = await self._arequest_with_retries(
                "GET", "/datasets", params={"name": dataset_name}
            )
        else:
            raise ValueError("Either dataset_name or dataset_id must be provided")

        data = response.json()
        if isinstance(data, list):
            if not data:
                raise ls_utils.LangSmithNotFoundError(
                    f"Dataset {dataset_name} not found"
                )
            return ls_schemas.Dataset(**data[0])
        return ls_schemas.Dataset(**data)

    async def delete_dataset(self, dataset_id: ls_client.ID_TYPE) -> None:
        """Delete a dataset."""
        await self._arequest_with_retries(
            "DELETE",
            f"/datasets/{ls_client._as_uuid(dataset_id)}",
        )

    async def list_datasets(
        self,
        **kwargs: Any,
    ) -> AsyncIterator[ls_schemas.Dataset]:
        """List datasets."""
        async for dataset in self._aget_paginated_list("/datasets", params=kwargs):
            yield ls_schemas.Dataset(**dataset)

    async def create_example(
        self,
        inputs: dict[str, Any],
        outputs: Optional[dict[str, Any]] = None,
        dataset_id: Optional[ls_client.ID_TYPE] = None,
        dataset_name: Optional[str] = None,
        **kwargs: Any,
    ) -> ls_schemas.Example:
        """Create an example."""
        if dataset_id is None and dataset_name is None:
            raise ValueError("Either dataset_id or dataset_name must be provided")
        if dataset_id is None:
            dataset = await self.read_dataset(dataset_name=dataset_name)
            dataset_id = dataset.id

        data = {
            "inputs": inputs,
            "outputs": outputs,
            "dataset_id": str(dataset_id),
            **kwargs,
        }
        response = await self._arequest_with_retries(
            "POST", "/examples", content=ls_client._dumps_json(data)
        )
        return ls_schemas.Example(**response.json())

    async def read_example(self, example_id: ls_client.ID_TYPE) -> ls_schemas.Example:
        """Read an example."""
        response = await self._arequest_with_retries(
            "GET", f"/examples/{ls_client._as_uuid(example_id)}"
        )
        return ls_schemas.Example(**response.json())

    async def list_examples(
        self,
        *,
        dataset_id: Optional[ls_client.ID_TYPE] = None,
        dataset_name: Optional[str] = None,
        **kwargs: Any,
    ) -> AsyncIterator[ls_schemas.Example]:
        """List examples."""
        params = kwargs.copy()
        if dataset_id:
            params["dataset"] = ls_client._as_uuid(dataset_id)
        elif dataset_name:
            dataset = await self.read_dataset(dataset_name=dataset_name)
            params["dataset"] = dataset.id

        async for example in self._aget_paginated_list("/examples", params=params):
            yield ls_schemas.Example(**example)

    async def create_feedback(
        self,
        run_id: Optional[ls_client.ID_TYPE],
        key: str,
        score: Optional[float] = None,
        value: Optional[Any] = None,
        comment: Optional[str] = None,
        **kwargs: Any,
    ) -> ls_schemas.Feedback:
        """Create feedback for a run.

        Args:
            run_id (Optional[ls_client.ID_TYPE]): The ID of the run to provide feedback for.
                Can be None for project-level feedback.
            key (str): The name of the metric or aspect this feedback is about.
            score (Optional[float]): The score to rate this run on the metric or aspect.
            value (Optional[Any]): The display value or non-numeric value for this feedback.
            comment (Optional[str]): A comment about this feedback.
            **kwargs: Additional keyword arguments to include in the feedback data.

        Returns:
            ls_schemas.Feedback: The created feedback object.

        Raises:
            httpx.HTTPStatusError: If the API request fails.
        """  # noqa: E501
        data = {
            "run_id": ls_client._ensure_uuid(run_id, accept_null=True),
            "key": key,
            "score": score,
            "value": value,
            "comment": comment,
            **kwargs,
        }
        response = await self._arequest_with_retries(
            "POST", "/feedback", content=ls_client._dumps_json(data)
        )
        return ls_schemas.Feedback(**response.json())

    async def create_feedback_from_token(
        self,
        token_or_url: Union[str, uuid.UUID],
        score: Union[float, int, bool, None] = None,
        *,
        value: Union[float, int, bool, str, dict, None] = None,
        correction: Union[dict, None] = None,
        comment: Union[str, None] = None,
        metadata: Optional[dict] = None,
    ) -> None:
        """Create feedback from a presigned token or URL.

        Args:
            token_or_url (Union[str, uuid.UUID]): The token or URL from which to create
                 feedback.
            score (Union[float, int, bool, None], optional): The score of the feedback.
                Defaults to None.
            value (Union[float, int, bool, str, dict, None], optional): The value of the
                feedback. Defaults to None.
            correction (Union[dict, None], optional): The correction of the feedback.
                Defaults to None.
            comment (Union[str, None], optional): The comment of the feedback. Defaults
                to None.
            metadata (Optional[dict], optional): Additional metadata for the feedback.
                Defaults to None.

        Raises:
            ValueError: If the source API URL is invalid.

        Returns:
            None: This method does not return anything.
        """
        source_api_url, token_uuid = ls_client._parse_token_or_url(
            token_or_url, self._api_url, num_parts=1
        )
        if source_api_url != self._api_url:
            raise ValueError(f"Invalid source API URL. {source_api_url}")
        response = await self._arequest_with_retries(
            "POST",
            f"/feedback/tokens/{ls_client._as_uuid(token_uuid)}",
            content=ls_client._dumps_json(
                {
                    "score": score,
                    "value": value,
                    "correction": correction,
                    "comment": comment,
                    "metadata": metadata,
                    # TODO: Add ID once the API supports it.
                }
            ),
        )
        ls_utils.raise_for_status_with_text(response)

    async def create_presigned_feedback_token(
        self,
        run_id: ls_client.ID_TYPE,
        feedback_key: str,
        *,
        expiration: Optional[datetime.datetime | datetime.timedelta] = None,
        feedback_config: Optional[ls_schemas.FeedbackConfig] = None,
        feedback_id: Optional[ls_client.ID_TYPE] = None,
    ) -> ls_schemas.FeedbackIngestToken:
        """Create a pre-signed URL to send feedback data to.

        This is useful for giving browser-based clients a way to upload
        feedback data directly to LangSmith without accessing the
        API key.

        Args:
            run_id:
            feedback_key:
            expiration: The expiration time of the pre-signed URL.
                Either a datetime or a timedelta offset from now.
                Default to 3 hours.
            feedback_config: FeedbackConfig or None.
                If creating a feedback_key for the first time,
                this defines how the metric should be interpreted,
                such as a continuous score (w/ optional bounds),
                or distribution over categorical values.
            feedback_id: The ID of the feedback to create. If not provided, a new
                feedback will be created.

        Returns:
            The pre-signed URL for uploading feedback data.
        """
        body: dict[str, Any] = {
            "run_id": run_id,
            "feedback_key": feedback_key,
            "feedback_config": feedback_config,
            "id": feedback_id or str(uuid.uuid4()),
        }
        if expiration is None:
            body["expires_in"] = ls_schemas.TimeDeltaInput(
                days=0,
                hours=3,
                minutes=0,
            )
        elif isinstance(expiration, datetime.datetime):
            body["expires_at"] = expiration.isoformat()
        elif isinstance(expiration, datetime.timedelta):
            body["expires_in"] = ls_schemas.TimeDeltaInput(
                days=expiration.days,
                hours=expiration.seconds // 3600,
                minutes=(expiration.seconds % 3600) // 60,
            )
        else:
            raise ValueError(
                f"Invalid expiration type: {type(expiration)}. "
                "Expected datetime.datetime or datetime.timedelta."
            )

        response = await self._arequest_with_retries(
            "POST",
            "/feedback/tokens",
            content=ls_client._dumps_json(body),
        )
        return ls_schemas.FeedbackIngestToken(**response.json())

    async def read_feedback(
        self, feedback_id: ls_client.ID_TYPE
    ) -> ls_schemas.Feedback:
        """Read feedback."""
        response = await self._arequest_with_retries(
            "GET", f"/feedback/{ls_client._as_uuid(feedback_id)}"
        )
        return ls_schemas.Feedback(**response.json())

    async def list_feedback(
        self,
        *,
        run_ids: Optional[Sequence[ls_client.ID_TYPE]] = None,
        feedback_key: Optional[Sequence[str]] = None,
        feedback_source_type: Optional[Sequence[ls_schemas.FeedbackSourceType]] = None,
        limit: Optional[int] = None,
        **kwargs: Any,
    ) -> AsyncIterator[ls_schemas.Feedback]:
        """List feedback."""
        params = {
            "run": (
                [str(ls_client._as_uuid(id_)) for id_ in run_ids] if run_ids else None
            ),
            "limit": min(limit, 100) if limit is not None else 100,
            **kwargs,
        }
        if feedback_key is not None:
            params["key"] = feedback_key
        if feedback_source_type is not None:
            params["source"] = feedback_source_type
        ix = 0
        async for feedback in self._aget_paginated_list("/feedback", params=params):
            yield ls_schemas.Feedback(**feedback)
            ix += 1
            if limit is not None and ix >= limit:
                break

    async def delete_feedback(self, feedback_id: ID_TYPE) -> None:
        """Delete a feedback by ID.

        Args:
            feedback_id (Union[UUID, str]):
                The ID of the feedback to delete.

        Returns:
            None
        """
        response = await self._arequest_with_retries(
            "DELETE", f"/feedback/{ls_client._as_uuid(feedback_id, 'feedback_id')}"
        )
        ls_utils.raise_for_status_with_text(response)

    # Annotation Queue API

    async def list_annotation_queues(
        self,
        *,
        queue_ids: Optional[list[ID_TYPE]] = None,
        name: Optional[str] = None,
        name_contains: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> AsyncIterator[ls_schemas.AnnotationQueue]:
        """List the annotation queues on the LangSmith API.

        Args:
            queue_ids (Optional[List[Union[UUID, str]]]):
                The IDs of the queues to filter by.
            name (Optional[str]):
                The name of the queue to filter by.
            name_contains (Optional[str]):
                The substring that the queue name should contain.
            limit (Optional[int]):
                The maximum number of queues to return.

        Yields:
            The annotation queues.
        """
        params: dict = {
            "ids": (
                [
                    ls_client._as_uuid(id_, f"queue_ids[{i}]")
                    for i, id_ in enumerate(queue_ids)
                ]
                if queue_ids is not None
                else None
            ),
            "name": name,
            "name_contains": name_contains,
            "limit": min(limit, 100) if limit is not None else 100,
        }
        ix = 0
        async for feedback in self._aget_paginated_list(
            "/annotation-queues", params=params
        ):
            yield ls_schemas.AnnotationQueue(**feedback)
            ix += 1
            if limit is not None and ix >= limit:
                break

    async def create_annotation_queue(
        self,
        *,
        name: str,
        description: Optional[str] = None,
        queue_id: Optional[ID_TYPE] = None,
    ) -> ls_schemas.AnnotationQueue:
        """Create an annotation queue on the LangSmith API.

        Args:
            name (str):
                The name of the annotation queue.
            description (Optional[str]):
                The description of the annotation queue.
            queue_id (Optional[Union[UUID, str]]):
                The ID of the annotation queue.

        Returns:
            AnnotationQueue: The created annotation queue object.
        """
        body = {
            "name": name,
            "description": description,
            "id": str(queue_id) if queue_id is not None else str(uuid.uuid4()),
        }
        response = await self._arequest_with_retries(
            "POST",
            "/annotation-queues",
            json={k: v for k, v in body.items() if v is not None},
        )
        ls_utils.raise_for_status_with_text(response)
        return ls_schemas.AnnotationQueue(
            **response.json(),
        )

    async def read_annotation_queue(
        self, queue_id: ID_TYPE
    ) -> ls_schemas.AnnotationQueue:
        """Read an annotation queue with the specified queue ID.

        Args:
            queue_id (Union[UUID, str]): The ID of the annotation queue to read.

        Returns:
            AnnotationQueue: The annotation queue object.
        """
        # TODO: Replace when actual endpoint is added
        return await self.list_annotation_queues(queue_ids=[queue_id]).__anext__()

    async def update_annotation_queue(
        self, queue_id: ID_TYPE, *, name: str, description: Optional[str] = None
    ) -> None:
        """Update an annotation queue with the specified queue_id.

        Args:
            queue_id (Union[UUID, str]): The ID of the annotation queue to update.
            name (str): The new name for the annotation queue.
            description (Optional[str]): The new description for the
                annotation queue. Defaults to None.

        Returns:
            None
        """
        response = await self._arequest_with_retries(
            "PATCH",
            f"/annotation-queues/{ls_client._as_uuid(queue_id, 'queue_id')}",
            json={
                "name": name,
                "description": description,
            },
        )
        ls_utils.raise_for_status_with_text(response)

    async def delete_annotation_queue(self, queue_id: ID_TYPE) -> None:
        """Delete an annotation queue with the specified queue ID.

        Args:
            queue_id (Union[UUID, str]): The ID of the annotation queue to delete.

        Returns:
            None
        """
        response = await self._arequest_with_retries(
            "DELETE",
            f"/annotation-queues/{ls_client._as_uuid(queue_id, 'queue_id')}",
            headers={"Accept": "application/json", **self._client.headers},
        )
        ls_utils.raise_for_status_with_text(response)

    async def add_runs_to_annotation_queue(
        self, queue_id: ID_TYPE, *, run_ids: list[ID_TYPE]
    ) -> None:
        """Add runs to an annotation queue with the specified queue ID.

        Args:
            queue_id (Union[UUID, str]): The ID of the annotation queue.
            run_ids (List[Union[UUID, str]]): The IDs of the runs to be added to the annotation
                queue.

        Returns:
            None
        """
        response = await self._arequest_with_retries(
            "POST",
            f"/annotation-queues/{ls_client._as_uuid(queue_id, 'queue_id')}/runs",
            json=[
                str(ls_client._as_uuid(id_, f"run_ids[{i}]"))
                for i, id_ in enumerate(run_ids)
            ],
        )
        ls_utils.raise_for_status_with_text(response)

    async def delete_run_from_annotation_queue(
        self, queue_id: ID_TYPE, *, run_id: ID_TYPE
    ) -> None:
        """Delete a run from an annotation queue with the specified queue ID and run ID.

        Args:
            queue_id (Union[UUID, str]): The ID of the annotation queue.
            run_id (Union[UUID, str]): The ID of the run to be added to the annotation
                queue.

        Returns:
            None
        """
        response = await self._arequest_with_retries(
            "DELETE",
            f"/annotation-queues/{ls_client._as_uuid(queue_id, 'queue_id')}/runs/{ls_client._as_uuid(run_id, 'run_id')}",
        )
        ls_utils.raise_for_status_with_text(response)

    async def get_run_from_annotation_queue(
        self, queue_id: ID_TYPE, *, index: int
    ) -> ls_schemas.RunWithAnnotationQueueInfo:
        """Get a run from an annotation queue at the specified index.

        Args:
            queue_id (Union[UUID, str]): The ID of the annotation queue.
            index (int): The index of the run to retrieve.

        Returns:
            RunWithAnnotationQueueInfo: The run at the specified index.

        Raises:
            LangSmithNotFoundError: If the run is not found at the given index.
            LangSmithError: For other API-related errors.
        """
        base_url = f"/annotation-queues/{ls_client._as_uuid(queue_id, 'queue_id')}/run"
        response = await self._arequest_with_retries("GET", f"{base_url}/{index}")
        ls_utils.raise_for_status_with_text(response)
        return ls_schemas.RunWithAnnotationQueueInfo(**response.json())

    @ls_beta.warn_beta
    async def index_dataset(
        self,
        *,
        dataset_id: ls_client.ID_TYPE,
        tag: str = "latest",
        **kwargs: Any,
    ) -> None:
        """Enable dataset indexing. Examples are indexed by their inputs.

        This enables searching for similar examples by inputs with
        ``client.similar_examples()``.

        Args:
            dataset_id (UUID): The ID of the dataset to index.
            tag (str, optional): The version of the dataset to index. If 'latest'
                then any updates to the dataset (additions, updates, deletions of
                examples) will be reflected in the index.

        Returns:
            None

        Raises:
            requests.HTTPError
        """  # noqa: E501
        dataset_id = ls_client._as_uuid(dataset_id, "dataset_id")
        resp = await self._arequest_with_retries(
            "POST",
            f"/datasets/{dataset_id}/index",
            content=ls_client._dumps_json({"tag": tag, **kwargs}),
        )
        ls_utils.raise_for_status_with_text(resp)

    @ls_beta.warn_beta
    async def sync_indexed_dataset(
        self,
        *,
        dataset_id: ls_client.ID_TYPE,
        **kwargs: Any,
    ) -> None:
        """Sync dataset index. This already happens automatically every 5 minutes, but you can call this to force a sync.

        Args:
            dataset_id (UUID): The ID of the dataset to sync.

        Returns:
            None

        Raises:
            requests.HTTPError
        """  # noqa: E501
        dataset_id = ls_client._as_uuid(dataset_id, "dataset_id")
        resp = await self._arequest_with_retries(
            "POST",
            f"/datasets/{dataset_id}/index/sync",
            content=ls_client._dumps_json({**kwargs}),
        )
        ls_utils.raise_for_status_with_text(resp)

    @ls_beta.warn_beta
    async def similar_examples(
        self,
        inputs: dict,
        /,
        *,
        limit: int,
        dataset_id: ls_client.ID_TYPE,
        filter: Optional[str] = None,
        **kwargs: Any,
    ) -> list[ls_schemas.ExampleSearch]:
        r"""Retrieve the dataset examples whose inputs best match the current inputs.

        **Note**: Must have few-shot indexing enabled for the dataset. See
        ``client.index_dataset()``.

        Args:
            inputs (dict): The inputs to use as a search query. Must match the dataset
                input schema. Must be JSON serializable.
            limit (int): The maximum number of examples to return.
            dataset_id (str or UUID): The ID of the dataset to search over.
            filter (str, optional): A filter string to apply to the search results. Uses
                the same syntax as the `filter` parameter in `list_runs()`. Only a subset
                of operations are supported. Defaults to None.
            kwargs (Any): Additional keyword args to pass as part of request body.

        Returns:
            List of ExampleSearch objects.

        Example:
            .. code-block:: python

                from langsmith import Client

                client = Client()
                await client.similar_examples(
                    {"question": "When would i use the runnable generator"},
                    limit=3,
                    dataset_id="...",
                )

            .. code-block:: pycon

                [
                    ExampleSearch(
                        inputs={'question': 'How do I cache a Chat model? What caches can I use?'},
                        outputs={'answer': 'You can use LangChain\'s caching layer for Chat Models. This can save you money by reducing the number of API calls you make to the LLM provider, if you\'re often requesting the same completion multiple times, and speed up your application.\n\n```python\n\nfrom langchain.cache import InMemoryCache\nlangchain.llm_cache = InMemoryCache()\n\n# The first time, it is not yet in cache, so it should take longer\nllm.predict(\'Tell me a joke\')\n\n```\n\nYou can also use SQLite Cache which uses a SQLite database:\n\n```python\n  rm .langchain.db\n\nfrom langchain.cache import SQLiteCache\nlangchain.llm_cache = SQLiteCache(database_path=".langchain.db")\n\n# The first time, it is not yet in cache, so it should take longer\nllm.predict(\'Tell me a joke\') \n```\n'},
                        metadata=None,
                        id=UUID('b2ddd1c4-dff6-49ae-8544-f48e39053398'),
                        dataset_id=UUID('01b6ce0f-bfb6-4f48-bbb8-f19272135d40')
                    ),
                    ExampleSearch(
                        inputs={'question': "What's a runnable lambda?"},
                        outputs={'answer': "A runnable lambda is an object that implements LangChain's `Runnable` interface and runs a callbale (i.e., a function). Note the function must accept a single argument."},
                        metadata=None,
                        id=UUID('f94104a7-2434-4ba7-8293-6a283f4860b4'),
                        dataset_id=UUID('01b6ce0f-bfb6-4f48-bbb8-f19272135d40')
                    ),
                    ExampleSearch(
                        inputs={'question': 'Show me how to use RecursiveURLLoader'},
                        outputs={'answer': 'The RecursiveURLLoader comes from the langchain.document_loaders.recursive_url_loader module. Here\'s an example of how to use it:\n\n```python\nfrom langchain.document_loaders.recursive_url_loader import RecursiveUrlLoader\n\n# Create an instance of RecursiveUrlLoader with the URL you want to load\nloader = RecursiveUrlLoader(url="https://example.com")\n\n# Load all child links from the URL page\nchild_links = loader.load()\n\n# Print the child links\nfor link in child_links:\n    print(link)\n```\n\nMake sure to replace "https://example.com" with the actual URL you want to load. The load() method returns a list of child links found on the URL page. You can iterate over this list to access each child link.'},
                        metadata=None,
                        id=UUID('0308ea70-a803-4181-a37d-39e95f138f8c'),
                        dataset_id=UUID('01b6ce0f-bfb6-4f48-bbb8-f19272135d40')
                    ),
                ]

        """  # noqa: E501
        dataset_id = ls_client._as_uuid(dataset_id, "dataset_id")
        req = {
            "inputs": inputs,
            "limit": limit,
            **kwargs,
        }
        if filter:
            req["filter"] = filter

        resp = await self._arequest_with_retries(
            "POST",
            f"/datasets/{dataset_id}/search",
            content=ls_client._dumps_json(req),
        )
        ls_utils.raise_for_status_with_text(resp)
        examples = []
        for ex in resp.json()["examples"]:
            examples.append(ls_schemas.ExampleSearch(**ex, dataset_id=dataset_id))
        return examples

    async def _get_settings(self) -> ls_schemas.LangSmithSettings:
        """Get the settings for the current tenant.

        Returns:
            dict: The settings for the current tenant.
        """
        if self._settings is None:
            response = await self._arequest_with_retries("GET", "/settings")
            ls_utils.raise_for_status_with_text(response)
            self._settings = ls_schemas.LangSmithSettings(**response.json())

        return self._settings

    async def _current_tenant_is_owner(self, owner: str) -> bool:
        """Check if the current workspace has the same handle as owner.

        Args:
            owner (str): The owner to check against.

        Returns:
            bool: True if the current tenant is the owner, False otherwise.
        """
        settings = await self._get_settings()
        return owner == "-" or settings.tenant_handle == owner

    async def _owner_conflict_error(
        self, action: str, owner: str
    ) -> ls_utils.LangSmithUserError:
        settings = await self._get_settings()
        return ls_utils.LangSmithUserError(
            f"Cannot {action} for another tenant.\n"
            f"Current tenant: {settings.tenant_handle},\n"
            f"Requested tenant: {owner}"
        )

    async def _get_latest_commit_hash(
        self, prompt_owner_and_name: str, limit: int = 1, offset: int = 0
    ) -> Optional[str]:
        """Get the latest commit hash for a prompt.

        Args:
            prompt_owner_and_name (str): The owner and name of the prompt.
            limit (int, default=1): The maximum number of commits to fetch. Defaults to 1.
            offset (int, default=0): The number of commits to skip. Defaults to 0.

        Returns:
            Optional[str]: The latest commit hash, or None if no commits are found.
        """
        response = await self._arequest_with_retries(
            "GET",
            f"/commits/{prompt_owner_and_name}/",
            params={"limit": limit, "offset": offset},
        )
        commits = response.json()["commits"]
        return commits[0]["commit_hash"] if commits else None

    async def _like_or_unlike_prompt(
        self, prompt_identifier: str, like: bool
    ) -> dict[str, int]:
        """Like or unlike a prompt.

        Args:
            prompt_identifier (str): The identifier of the prompt.
            like (bool): True to like the prompt, False to unlike it.

        Returns:
            A dictionary with the key 'likes' and the count of likes as the value.

        Raises:
            requests.exceptions.HTTPError: If the prompt is not found or
            another error occurs.
        """
        owner, prompt_name, _ = ls_utils.parse_prompt_identifier(prompt_identifier)
        response = await self._arequest_with_retries(
            "POST", f"/likes/{owner}/{prompt_name}", json={"like": like}
        )
        response.raise_for_status()
        return response.json()

    async def _get_prompt_url(self, prompt_identifier: str) -> str:
        """Get a URL for a prompt.

        Args:
            prompt_identifier (str): The identifier of the prompt.

        Returns:
            str: The URL for the prompt.

        """
        owner, prompt_name, commit_hash = ls_utils.parse_prompt_identifier(
            prompt_identifier
        )

        if not self._current_tenant_is_owner(owner):
            return f"{self._host_url}/hub/{owner}/{prompt_name}:{commit_hash[:8]}"

        settings = await self._get_settings()
        return (
            f"{self._host_url}/prompts/{prompt_name}/{commit_hash[:8]}"
            f"?organizationId={settings.id}"
        )

    async def _prompt_exists(self, prompt_identifier: str) -> bool:
        """Check if a prompt exists.

        Args:
            prompt_identifier (str): The identifier of the prompt.

        Returns:
            bool: True if the prompt exists, False otherwise.
        """
        prompt = await self.get_prompt(prompt_identifier)
        return True if prompt else False

    async def like_prompt(self, prompt_identifier: str) -> dict[str, int]:
        """Like a prompt.

        Args:
            prompt_identifier (str): The identifier of the prompt.

        Returns:
            Dict[str, int]: A dictionary with the key 'likes' and the count of likes as the value.

        """
        return await self._like_or_unlike_prompt(prompt_identifier, like=True)

    async def unlike_prompt(self, prompt_identifier: str) -> dict[str, int]:
        """Unlike a prompt.

        Args:
            prompt_identifier (str): The identifier of the prompt.

        Returns:
            Dict[str, int]: A dictionary with the key 'likes' and the count of likes as the value.

        """
        return await self._like_or_unlike_prompt(prompt_identifier, like=False)

    async def list_prompts(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        is_public: Optional[bool] = None,
        is_archived: Optional[bool] = False,
        sort_field: ls_schemas.PromptSortField = ls_schemas.PromptSortField.updated_at,
        sort_direction: Literal["desc", "asc"] = "desc",
        query: Optional[str] = None,
    ) -> ls_schemas.ListPromptsResponse:
        """List prompts with pagination.

        Args:
            limit (int, default=100): The maximum number of prompts to return. Defaults to 100.
            offset (int, default=0): The number of prompts to skip. Defaults to 0.
            is_public (Optional[bool]): Filter prompts by if they are public.
            is_archived (Optional[bool]): Filter prompts by if they are archived.
            sort_field (PromptSortField): The field to sort by.
              Defaults to "updated_at".
            sort_direction (Literal["desc", "asc"], default="desc"): The order to sort by.
              Defaults to "desc".
            query (Optional[str]): Filter prompts by a search query.

        Returns:
            ListPromptsResponse: A response object containing
            the list of prompts.
        """
        params = {
            "limit": limit,
            "offset": offset,
            "is_public": (
                "true" if is_public else "false" if is_public is not None else None
            ),
            "is_archived": "true" if is_archived else "false",
            "sort_field": (
                sort_field.value
                if isinstance(sort_field, ls_schemas.PromptSortField)
                else sort_field
            ),
            "sort_direction": sort_direction,
            "query": query,
            "match_prefix": "true" if query else None,
        }

        response = await self._arequest_with_retries(
            "GET", "/repos/", params=_exclude_none(params)
        )
        return ls_schemas.ListPromptsResponse(**response.json())

    async def get_prompt(self, prompt_identifier: str) -> Optional[ls_schemas.Prompt]:
        """Get a specific prompt by its identifier.

        Args:
            prompt_identifier (str): The identifier of the prompt.
                The identifier should be in the format "prompt_name" or "owner/prompt_name".

        Returns:
            Optional[Prompt]: The prompt object.

        Raises:
            requests.exceptions.HTTPError: If the prompt is not found or
                another error occurs.
        """
        owner, prompt_name, _ = ls_utils.parse_prompt_identifier(prompt_identifier)
        try:
            response = await self._arequest_with_retries(
                "GET", f"/repos/{owner}/{prompt_name}"
            )
            return ls_schemas.Prompt(**response.json()["repo"])
        except ls_utils.LangSmithNotFoundError:
            return None

    async def create_prompt(
        self,
        prompt_identifier: str,
        *,
        description: Optional[str] = None,
        readme: Optional[str] = None,
        tags: Optional[Sequence[str]] = None,
        is_public: bool = False,
    ) -> ls_schemas.Prompt:
        """Create a new prompt.

        Does not attach prompt object, just creates an empty prompt.

        Args:
            prompt_identifier (str): The identifier of the prompt.
                The identifier should be in the formatof owner/name:hash, name:hash, owner/name, or name
            description (Optional[str]): A description of the prompt.
            readme (Optional[str]): A readme for the prompt.
            tags (Optional[Sequence[str]]): A list of tags for the prompt.
            is_public (bool): Whether the prompt should be public. Defaults to False.

        Returns:
            Prompt: The created prompt object.

        Raises:
            ValueError: If the current tenant is not the owner.
            HTTPError: If the server request fails.
        """
        settings = await self._get_settings()
        if is_public and not settings.tenant_handle:
            raise ls_utils.LangSmithUserError(
                "Cannot create a public prompt without first\n"
                "creating a LangChain Hub handle. "
                "You can add a handle by creating a public prompt at:\n"
                "https://smith.langchain.com/prompts"
            )

        owner, prompt_name, _ = ls_utils.parse_prompt_identifier(prompt_identifier)
        if not (await self._current_tenant_is_owner(owner=owner)):
            raise (await self._owner_conflict_error("create a prompt", owner))

        json: dict[str, Union[str, bool, Sequence[str]]] = {
            "repo_handle": prompt_name,
            "description": description or "",
            "readme": readme or "",
            "tags": tags or [],
            "is_public": is_public,
        }

        response = await self._arequest_with_retries("POST", "/repos/", json=json)
        response.raise_for_status()
        return ls_schemas.Prompt(**response.json()["repo"])

    async def create_commit(
        self,
        prompt_identifier: str,
        object: Any,
        *,
        parent_commit_hash: Optional[str] = None,
    ) -> str:
        """Create a commit for an existing prompt.

        Args:
            prompt_identifier (str): The identifier of the prompt.
            object (Any): The LangChain object to commit.
            parent_commit_hash (Optional[str]): The hash of the parent commit.
                Defaults to latest commit.

        Returns:
            str: The url of the prompt commit.

        Raises:
            HTTPError: If the server request fails.
            ValueError: If the prompt does not exist.
        """
        if not (await self._prompt_exists(prompt_identifier)):
            raise ls_utils.LangSmithNotFoundError(
                "Prompt does not exist, you must create it first."
            )

        try:
            from langchain_core.load.dump import dumps
        except ImportError:
            raise ImportError(
                "The client.create_commit function requires the langchain_core"
                "package to run.\nInstall with `pip install langchain_core`"
            )

        json_object = dumps(object)
        manifest_dict = json.loads(json_object)

        owner, prompt_name, _ = ls_utils.parse_prompt_identifier(prompt_identifier)
        prompt_owner_and_name = f"{owner}/{prompt_name}"

        if parent_commit_hash == "latest" or parent_commit_hash is None:
            parent_commit_hash = await self._get_latest_commit_hash(
                prompt_owner_and_name
            )

        request_dict = {"parent_commit": parent_commit_hash, "manifest": manifest_dict}
        response = await self._arequest_with_retries(
            "POST", f"/commits/{prompt_owner_and_name}", json=request_dict
        )

        commit_hash = response.json()["commit"]["commit_hash"]

        return await self._get_prompt_url(f"{prompt_owner_and_name}:{commit_hash}")

    async def update_prompt(
        self,
        prompt_identifier: str,
        *,
        description: Optional[str] = None,
        readme: Optional[str] = None,
        tags: Optional[Sequence[str]] = None,
        is_public: Optional[bool] = None,
        is_archived: Optional[bool] = None,
    ) -> dict[str, Any]:
        """Update a prompt's metadata.

        To update the content of a prompt, use push_prompt or create_commit instead.

        Args:
            prompt_identifier (str): The identifier of the prompt to update.
            description (Optional[str]): New description for the prompt.
            readme (Optional[str]): New readme for the prompt.
            tags (Optional[Sequence[str]]): New list of tags for the prompt.
            is_public (Optional[bool]): New public status for the prompt.
            is_archived (Optional[bool]): New archived status for the prompt.

        Returns:
            Dict[str, Any]: The updated prompt data as returned by the server.

        Raises:
            ValueError: If the prompt_identifier is empty.
            HTTPError: If the server request fails.
        """
        settings = await self._get_settings()
        if is_public and not settings.tenant_handle:
            raise ValueError(
                "Cannot create a public prompt without first\n"
                "creating a LangChain Hub handle. "
                "You can add a handle by creating a public prompt at:\n"
                "https://smith.langchain.com/prompts"
            )

        json: dict[str, Union[str, bool, Sequence[str]]] = {}

        if description is not None:
            json["description"] = description
        if readme is not None:
            json["readme"] = readme
        if is_public is not None:
            json["is_public"] = is_public
        if is_archived is not None:
            json["is_archived"] = is_archived
        if tags is not None:
            json["tags"] = tags

        owner, prompt_name, _ = ls_utils.parse_prompt_identifier(prompt_identifier)
        response = await self._arequest_with_retries(
            "PATCH", f"/repos/{owner}/{prompt_name}", json=json
        )
        response.raise_for_status()
        return response.json()

    async def delete_prompt(self, prompt_identifier: str) -> None:
        """Delete a prompt.

        Args:
            prompt_identifier (str): The identifier of the prompt to delete.

        Returns:
            bool: True if the prompt was successfully deleted, False otherwise.

        Raises:
            ValueError: If the current tenant is not the owner of the prompt.
        """
        owner, prompt_name, _ = ls_utils.parse_prompt_identifier(prompt_identifier)
        if not (await self._current_tenant_is_owner(owner)):
            raise (await self._owner_conflict_error("delete a prompt", owner))

        response = await self._arequest_with_retries(
            "DELETE", f"/repos/{owner}/{prompt_name}"
        )
        response.raise_for_status()

    async def pull_prompt_commit(
        self,
        prompt_identifier: str,
        *,
        include_model: Optional[bool] = False,
    ) -> ls_schemas.PromptCommit:
        """Pull a prompt object from the LangSmith API.

        Args:
            prompt_identifier (str): The identifier of the prompt.

        Returns:
            PromptCommit: The prompt object.

        Raises:
            ValueError: If no commits are found for the prompt.
        """
        owner, prompt_name, commit_hash = ls_utils.parse_prompt_identifier(
            prompt_identifier
        )
        response = await self._arequest_with_retries(
            "GET",
            (
                f"/commits/{owner}/{prompt_name}/{commit_hash}"
                f"{'?include_model=true' if include_model else ''}"
            ),
        )
        return ls_schemas.PromptCommit(
            **{"owner": owner, "repo": prompt_name, **response.json()}
        )

    async def list_prompt_commits(
        self,
        prompt_identifier: str,
        *,
        limit: Optional[int] = None,
        offset: int = 0,
        include_model: bool = False,
    ) -> AsyncGenerator[ls_schemas.ListedPromptCommit, None]:
        """List commits for a given prompt.

        Args:
            prompt_identifier (str): The identifier of the prompt in the format 'owner/repo_name'.
            limit (Optional[int]): The maximum number of commits to return. If None, returns all commits. Defaults to None.
            offset (int, default=0): The number of commits to skip before starting to return results. Defaults to 0.
            include_model (bool, default=False): Whether to include the model information in the commit data. Defaults to False.

        Yields:
            A ListedPromptCommit object for each commit.

        Note:
            This method uses pagination to retrieve commits. It will make multiple API calls if necessary to retrieve all commits
            or up to the specified limit.
        """
        owner, prompt_name, _ = ls_utils.parse_prompt_identifier(prompt_identifier)

        params = {
            "limit": min(100, limit) if limit is not None else limit,
            "offset": offset,
            "include_model": include_model,
        }
        i = 0
        while True:
            params["offset"] = offset
            response = await self._arequest_with_retries(
                "GET",
                f"/commits/{owner}/{prompt_name}/",
                params=params,
            )
            val = response.json()
            items = val["commits"]
            total = val["total"]

            if not items:
                break
            for it in items:
                if limit is not None and i >= limit:
                    return  # Stop iteration if we've reached the limit
                yield ls_schemas.ListedPromptCommit(
                    **{"owner": owner, "repo": prompt_name, **it}
                )
                i += 1

            offset += len(items)
            if offset >= total:
                break

    async def pull_prompt(
        self, prompt_identifier: str, *, include_model: Optional[bool] = False
    ) -> Any:
        """Pull a prompt and return it as a LangChain PromptTemplate.

        This method requires `langchain_core`.

        Args:
            prompt_identifier (str): The identifier of the prompt.
            include_model (Optional[bool], default=False): Whether to include the model information in the prompt data.

        Returns:
            Any: The prompt object in the specified format.
        """
        try:
            from langchain_core.language_models.base import BaseLanguageModel
            from langchain_core.load.load import loads
            from langchain_core.output_parsers import BaseOutputParser
            from langchain_core.prompts import BasePromptTemplate
            from langchain_core.prompts.structured import StructuredPrompt
            from langchain_core.runnables.base import RunnableBinding, RunnableSequence
        except ImportError:
            raise ImportError(
                "The client.pull_prompt function requires the langchain_core"
                "package to run.\nInstall with `pip install langchain_core`"
            )
        try:
            from langchain_core._api import suppress_langchain_beta_warning
        except ImportError:

            @contextlib.contextmanager
            def suppress_langchain_beta_warning():
                yield

        prompt_object = await self.pull_prompt_commit(
            prompt_identifier, include_model=include_model
        )
        with suppress_langchain_beta_warning():
            prompt = loads(json.dumps(prompt_object.manifest))

        if (
            isinstance(prompt, BasePromptTemplate)
            or isinstance(prompt, RunnableSequence)
            and isinstance(prompt.first, BasePromptTemplate)
        ):
            prompt_template = (
                prompt
                if isinstance(prompt, BasePromptTemplate)
                else (
                    prompt.first
                    if isinstance(prompt, RunnableSequence)
                    and isinstance(prompt.first, BasePromptTemplate)
                    else None
                )
            )
            if prompt_template is None:
                raise ls_utils.LangSmithError(
                    "Prompt object is not a valid prompt template."
                )

            if prompt_template.metadata is None:
                prompt_template.metadata = {}
            prompt_template.metadata.update(
                {
                    "lc_hub_owner": prompt_object.owner,
                    "lc_hub_repo": prompt_object.repo,
                    "lc_hub_commit_hash": prompt_object.commit_hash,
                }
            )
        if (
            include_model
            and isinstance(prompt, RunnableSequence)
            and isinstance(prompt.first, StructuredPrompt)
            # Make forward-compatible in case we let update the response type
            and (
                len(prompt.steps) == 2 and not isinstance(prompt.last, BaseOutputParser)
            )
        ):
            if isinstance(prompt.last, RunnableBinding) and isinstance(
                prompt.last.bound, BaseLanguageModel
            ):
                seq = cast(RunnableSequence, prompt.first | prompt.last.bound)
                if len(seq.steps) == 3:  # prompt | bound llm | output parser
                    rebound_llm = seq.steps[1]
                    prompt = RunnableSequence(
                        prompt.first,
                        rebound_llm.bind(**{**prompt.last.kwargs}),
                        seq.last,
                    )
                else:
                    prompt = seq  # Not sure

            elif isinstance(prompt.last, BaseLanguageModel):
                prompt: RunnableSequence = prompt.first | prompt.last  # type: ignore[no-redef, assignment]
            else:
                pass

        return prompt

    async def push_prompt(
        self,
        prompt_identifier: str,
        *,
        object: Optional[Any] = None,
        parent_commit_hash: str = "latest",
        is_public: Optional[bool] = None,
        description: Optional[str] = None,
        readme: Optional[str] = None,
        tags: Optional[Sequence[str]] = None,
    ) -> str:
        """Push a prompt to the LangSmith API.

        Can be used to update prompt metadata or prompt content.

        If the prompt does not exist, it will be created.
        If the prompt exists, it will be updated.

        Args:
            prompt_identifier (str): The identifier of the prompt.
            object (Optional[Any]): The LangChain object to push.
            parent_commit_hash (str): The parent commit hash.
              Defaults to "latest".
            is_public (Optional[bool]): Whether the prompt should be public.
                If None (default), the current visibility status is maintained for existing prompts.
                For new prompts, None defaults to private.
                Set to True to make public, or False to make private.
            description (Optional[str]): A description of the prompt.
              Defaults to an empty string.
            readme (Optional[str]): A readme for the prompt.
              Defaults to an empty string.
            tags (Optional[Sequence[str]]): A list of tags for the prompt.
              Defaults to an empty list.

        Returns:
            str: The URL of the prompt.
        """
        # Create or update prompt metadata
        if await self._prompt_exists(prompt_identifier):
            if any(
                param is not None for param in [is_public, description, readme, tags]
            ):
                await self.update_prompt(
                    prompt_identifier,
                    description=description,
                    readme=readme,
                    tags=tags,
                    is_public=is_public,
                )
        else:
            await self.create_prompt(
                prompt_identifier,
                is_public=is_public if is_public is not None else False,
                description=description,
                readme=readme,
                tags=tags,
            )

        if object is None:
            return await self._get_prompt_url(prompt_identifier=prompt_identifier)

        # Create a commit with the new manifest
        url = await self.create_commit(
            prompt_identifier,
            object,
            parent_commit_hash=parent_commit_hash,
        )
        return url


def _exclude_none(d: dict) -> dict:
    """Exclude None values from a dictionary."""
    return {k: v for k, v in d.items() if v is not None}
