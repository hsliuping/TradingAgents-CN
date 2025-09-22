from __future__ import annotations

import atexit
import contextlib
import contextvars
import datetime
import functools
import importlib
import inspect
import logging
import os
import threading
import time
import uuid
import warnings
from collections.abc import Generator, Sequence
from concurrent.futures import Future
from pathlib import Path
from typing import (
    Any,
    Callable,
    Optional,
    TypeVar,
    Union,
    cast,
    overload,
)

from typing_extensions import TypedDict

from langsmith import client as ls_client
from langsmith import env as ls_env
from langsmith import run_helpers as rh
from langsmith import run_trees
from langsmith import run_trees as rt
from langsmith import schemas as ls_schemas
from langsmith import utils as ls_utils
from langsmith._internal import _orjson
from langsmith._internal._serde import dumps_json
from langsmith.client import ID_TYPE

try:
    import pytest  # type: ignore

    SkipException = pytest.skip.Exception
except ImportError:

    class SkipException(Exception):  # type: ignore[no-redef]
        pass


logger = logging.getLogger(__name__)


T = TypeVar("T")
U = TypeVar("U")


@overload
def test(
    func: Callable,
) -> Callable: ...


@overload
def test(
    *,
    id: Optional[uuid.UUID] = None,
    output_keys: Optional[Sequence[str]] = None,
    client: Optional[ls_client.Client] = None,
    test_suite_name: Optional[str] = None,
) -> Callable[[Callable], Callable]: ...


def test(*args: Any, **kwargs: Any) -> Callable:
    """Trace a pytest test case in LangSmith.

    This decorator is used to trace a pytest test to LangSmith. It ensures
    that the necessary example data is created and associated with the test function.
    The decorated function will be executed as a test case, and the results will be
    recorded and reported by LangSmith.

    Args:
        - id (Optional[uuid.UUID]): A unique identifier for the test case. If not
            provided, an ID will be generated based on the test function's module
            and name.
        - output_keys (Optional[Sequence[str]]): A list of keys to be considered as
            the output keys for the test case. These keys will be extracted from the
            test function's inputs and stored as the expected outputs.
        - client (Optional[ls_client.Client]): An instance of the LangSmith client
            to be used for communication with the LangSmith service. If not provided,
            a default client will be used.
        - test_suite_name (Optional[str]): The name of the test suite to which the
            test case belongs. If not provided, the test suite name will be determined
            based on the environment or the package name.

    Returns:
        Callable: The decorated test function.

    Environment:
        - LANGSMITH_TEST_CACHE: If set, API calls will be cached to disk to
            save time and costs during testing. Recommended to commit the
            cache files to your repository for faster CI/CD runs.
            Requires the 'langsmith[vcr]' package to be installed.
        - LANGSMITH_TEST_TRACKING: Set this variable to the path of a directory
            to enable caching of test results. This is useful for re-running tests
             without re-executing the code. Requires the 'langsmith[vcr]' package.

    Example:
        For basic usage, simply decorate a test function with `@pytest.mark.langsmith`.
        Under the hood this will call the `test` method:

        .. code-block:: python

            import pytest


            # Equivalently can decorate with `test` directly:
            # from langsmith import test
            # @test
            @pytest.mark.langsmith
            def test_addition():
                assert 3 + 4 == 7


        Any code that is traced (such as those traced using `@traceable`
        or `wrap_*` functions) will be traced within the test case for
        improved visibility and debugging.

        .. code-block:: python

            import pytest
            from langsmith import traceable


            @traceable
            def generate_numbers():
                return 3, 4


            @pytest.mark.langsmith
            def test_nested():
                # Traced code will be included in the test case
                a, b = generate_numbers()
                assert a + b == 7

        LLM calls are expensive! Cache requests by setting
        `LANGSMITH_TEST_CACHE=path/to/cache`. Check in these files to speed up
        CI/CD pipelines, so your results only change when your prompt or requested
        model changes.

        Note that this will require that you install langsmith with the `vcr` extra:

        `pip install -U "langsmith[vcr]"`

        Caching is faster if you install libyaml. See
        https://vcrpy.readthedocs.io/en/latest/installation.html#speed for more details.

        .. code-block:: python

            # os.environ["LANGSMITH_TEST_CACHE"] = "tests/cassettes"
            import openai
            import pytest
            from langsmith import wrappers

            oai_client = wrappers.wrap_openai(openai.Client())


            @pytest.mark.langsmith
            def test_openai_says_hello():
                # Traced code will be included in the test case
                response = oai_client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant."},
                        {"role": "user", "content": "Say hello!"},
                    ],
                )
                assert "hello" in response.choices[0].message.content.lower()

        LLMs are stochastic. Naive assertions are flakey. You can use langsmith's
        `expect` to score and make approximate assertions on your results.

        .. code-block:: python

            import pytest
            from langsmith import expect


            @pytest.mark.langsmith
            def test_output_semantically_close():
                response = oai_client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant."},
                        {"role": "user", "content": "Say hello!"},
                    ],
                )
                # The embedding_distance call logs the embedding distance to LangSmith
                expect.embedding_distance(
                    prediction=response.choices[0].message.content,
                    reference="Hello!",
                    # The following optional assertion logs a
                    # pass/fail score to LangSmith
                    # and raises an AssertionError if the assertion fails.
                ).to_be_less_than(1.0)
                # Compute damerau_levenshtein distance
                expect.edit_distance(
                    prediction=response.choices[0].message.content,
                    reference="Hello!",
                    # And then log a pass/fail score to LangSmith
                ).to_be_less_than(1.0)

        The `@test` decorator works natively with pytest fixtures.
        The values will populate the "inputs" of the corresponding example in LangSmith.

        .. code-block:: python

            import pytest


            @pytest.fixture
            def some_input():
                return "Some input"


            @pytest.mark.langsmith
            def test_with_fixture(some_input: str):
                assert "input" in some_input

        You can still use pytest.parametrize() as usual to run multiple test cases
        using the same test function.

        .. code-block:: python

            import pytest


            @pytest.mark.langsmith(output_keys=["expected"])
            @pytest.mark.parametrize(
                "a, b, expected",
                [
                    (1, 2, 3),
                    (3, 4, 7),
                ],
            )
            def test_addition_with_multiple_inputs(a: int, b: int, expected: int):
                assert a + b == expected

        By default, each test case will be assigned a consistent, unique identifier
        based on the function name and module. You can also provide a custom identifier
        using the `id` argument:

        .. code-block:: python

            import pytest
            import uuid

            example_id = uuid.uuid4()


            @pytest.mark.langsmith(id=str(example_id))
            def test_multiplication():
                assert 3 * 4 == 12

        By default, all test inputs are saved as "inputs" to a dataset.
        You can specify the `output_keys` argument to persist those keys
        within the dataset's "outputs" fields.

        .. code-block:: python

            import pytest


            @pytest.fixture
            def expected_output():
                return "input"


            @pytest.mark.langsmith(output_keys=["expected_output"])
            def test_with_expected_output(some_input: str, expected_output: str):
                assert expected_output in some_input


        To run these tests, use the pytest CLI. Or directly run the test functions.

        .. code-block:: python

            test_output_semantically_close()
            test_addition()
            test_nested()
            test_with_fixture("Some input")
            test_with_expected_output("Some input", "Some")
            test_multiplication()
            test_openai_says_hello()
            test_addition_with_multiple_inputs(1, 2, 3)
    """
    langtest_extra = _UTExtra(
        id=kwargs.pop("id", None),
        output_keys=kwargs.pop("output_keys", None),
        client=kwargs.pop("client", None),
        test_suite_name=kwargs.pop("test_suite_name", None),
        cache=ls_utils.get_cache_dir(kwargs.pop("cache", None)),
        metadata=kwargs.pop("metadata", None),
        repetitions=kwargs.pop("repetitions", None),
    )
    if kwargs:
        warnings.warn(f"Unexpected keyword arguments: {kwargs.keys()}")
    disable_tracking = ls_utils.test_tracking_is_disabled()
    if disable_tracking:
        logger.info(
            "LANGSMITH_TEST_TRACKING is set to 'false'."
            " Skipping LangSmith test tracking."
        )

    def decorator(func: Callable) -> Callable:
        # Handle repetitions
        repetitions = langtest_extra.get("repetitions", 1) or 1

        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(
                *test_args: Any, request: Any = None, **test_kwargs: Any
            ):
                if disable_tracking:
                    return await func(*test_args, **test_kwargs)

                # Run test multiple times for repetitions
                for i in range(repetitions):
                    repetition_extra = langtest_extra.copy()
                    await _arun_test(
                        func,
                        *test_args,
                        pytest_request=request,
                        **test_kwargs,
                        langtest_extra=repetition_extra,
                    )

            return async_wrapper

        @functools.wraps(func)
        def wrapper(*test_args: Any, request: Any = None, **test_kwargs: Any):
            if disable_tracking:
                return func(*test_args, **test_kwargs)

            # Run test multiple times for repetitions
            for i in range(repetitions):
                repetition_extra = langtest_extra.copy()
                _run_test(
                    func,
                    *test_args,
                    pytest_request=request,
                    **test_kwargs,
                    langtest_extra=repetition_extra,
                )

        return wrapper

    if args and callable(args[0]):
        return decorator(args[0])

    return decorator


## Private functions


def _get_experiment_name(test_suite_name: str) -> str:
    # If this is a pytest-xdist multi-process run then we need to create the same
    # experiment name across processes. We can do this by accessing the
    # PYTEST_XDIST_TESTRUNID env var.
    if os.environ.get("PYTEST_XDIST_TESTRUNUID") and importlib.util.find_spec("xdist"):
        id_name = test_suite_name + os.environ["PYTEST_XDIST_TESTRUNUID"]
        id_ = str(uuid.uuid5(uuid.NAMESPACE_DNS, id_name).hex[:8])
    else:
        id_ = str(uuid.uuid4().hex[:8])

    if os.environ.get("LANGSMITH_EXPERIMENT"):
        prefix = os.environ["LANGSMITH_EXPERIMENT"]
    else:
        prefix = ls_utils.get_tracer_project(False) or "TestSuiteResult"
    name = f"{prefix}:{id_}"
    return name


def _get_test_suite_name(func: Callable) -> str:
    test_suite_name = ls_utils.get_env_var("TEST_SUITE")
    if test_suite_name:
        return test_suite_name
    repo_name = ls_env.get_git_info()["repo_name"]
    try:
        mod = inspect.getmodule(func)
        if mod:
            return f"{repo_name}.{mod.__name__}"
    except BaseException:
        logger.debug("Could not determine test suite name from file path.")

    raise ValueError("Please set the LANGSMITH_TEST_SUITE environment variable.")


def _get_test_suite(
    client: ls_client.Client, test_suite_name: str
) -> ls_schemas.Dataset:
    if client.has_dataset(dataset_name=test_suite_name):
        return client.read_dataset(dataset_name=test_suite_name)
    else:
        repo = ls_env.get_git_info().get("remote_url") or ""
        description = "Test suite"
        if repo:
            description += f" for {repo}"
        try:
            return client.create_dataset(
                dataset_name=test_suite_name,
                description=description,
                metadata={"__ls_runner": "pytest"},
            )
        except ls_utils.LangSmithConflictError:
            return client.read_dataset(dataset_name=test_suite_name)


def _start_experiment(
    client: ls_client.Client,
    test_suite: ls_schemas.Dataset,
) -> ls_schemas.TracerSession:
    experiment_name = _get_experiment_name(test_suite.name)
    try:
        return client.create_project(
            experiment_name,
            reference_dataset_id=test_suite.id,
            description="Test Suite Results.",
            metadata={
                "revision_id": ls_env.get_langchain_env_var_metadata().get(
                    "revision_id"
                ),
                "__ls_runner": "pytest",
            },
        )
    except ls_utils.LangSmithConflictError:
        return client.read_project(project_name=experiment_name)


def _get_example_id(
    func: Callable, inputs: Optional[dict], suite_id: uuid.UUID
) -> tuple[uuid.UUID, str]:
    try:
        file_path = str(Path(inspect.getfile(func)).relative_to(Path.cwd()))
    except ValueError:
        # Fall back to module name if file path is not available
        file_path = func.__module__
    identifier = f"{suite_id}{file_path}::{func.__name__}"
    # If parametrized test, need to add inputs to identifier:
    if hasattr(func, "pytestmark") and any(
        m.name == "parametrize" for m in func.pytestmark
    ):
        identifier += _stringify(inputs)
    return uuid.uuid5(uuid.NAMESPACE_DNS, identifier), identifier[len(str(suite_id)) :]


def _end_tests(test_suite: _LangSmithTestSuite):
    git_info = ls_env.get_git_info() or {}
    test_suite.shutdown()
    dataset_version = test_suite.get_dataset_version()
    dataset_id = test_suite._dataset.id
    test_suite.client.update_project(
        test_suite.experiment_id,
        metadata={
            **git_info,
            "dataset_version": dataset_version,
            "revision_id": ls_env.get_langchain_env_var_metadata().get("revision_id"),
            "__ls_runner": "pytest",
        },
    )
    if dataset_version and git_info["commit"] is not None:
        test_suite.client.update_dataset_tag(
            dataset_id=dataset_id,
            as_of=dataset_version,
            tag=f"git:commit:{git_info['commit']}",
        )
    if dataset_version and git_info["branch"] is not None:
        test_suite.client.update_dataset_tag(
            dataset_id=dataset_id,
            as_of=dataset_version,
            tag=f"git:branch:{git_info['branch']}",
        )


VT = TypeVar("VT", bound=Optional[dict])


def _serde_example_values(values: VT) -> VT:
    if values is None:
        return cast(VT, values)
    bts = ls_client._dumps_json(values)
    return _orjson.loads(bts)


class _LangSmithTestSuite:
    _instances: Optional[dict] = None
    _lock = threading.RLock()

    def __init__(
        self,
        client: Optional[ls_client.Client],
        experiment: ls_schemas.TracerSession,
        dataset: ls_schemas.Dataset,
    ):
        self.client = client or rt.get_cached_client()
        self._experiment = experiment
        self._dataset = dataset
        self._dataset_version: Optional[datetime.datetime] = dataset.modified_at
        self._executor = ls_utils.ContextThreadPoolExecutor()
        atexit.register(_end_tests, self)

    @property
    def id(self):
        return self._dataset.id

    @property
    def experiment_id(self):
        return self._experiment.id

    @property
    def experiment(self):
        return self._experiment

    @classmethod
    def from_test(
        cls,
        client: Optional[ls_client.Client],
        func: Callable,
        test_suite_name: Optional[str] = None,
    ) -> _LangSmithTestSuite:
        client = client or rt.get_cached_client()
        test_suite_name = test_suite_name or _get_test_suite_name(func)
        with cls._lock:
            if not cls._instances:
                cls._instances = {}
            if test_suite_name not in cls._instances:
                test_suite = _get_test_suite(client, test_suite_name)
                experiment = _start_experiment(client, test_suite)
                cls._instances[test_suite_name] = cls(client, experiment, test_suite)
        return cls._instances[test_suite_name]

    @property
    def name(self):
        return self._experiment.name

    def get_dataset_version(self):
        return self._dataset_version

    def submit_result(
        self,
        run_id: uuid.UUID,
        error: Optional[str] = None,
        skipped: bool = False,
        pytest_plugin: Any = None,
        pytest_nodeid: Any = None,
    ) -> None:
        if skipped:
            score = None
            status = "skipped"
        elif error:
            score = 0
            status = "failed"
        else:
            score = 1
            status = "passed"
        if pytest_plugin and pytest_nodeid:
            pytest_plugin.update_process_status(pytest_nodeid, {"status": status})
        self._executor.submit(self._submit_result, run_id, score)

    def _submit_result(self, run_id: uuid.UUID, score: Optional[int]) -> None:
        # trace_id will always be run_id here because the feedback is on the root
        # test run
        self.client.create_feedback(run_id, key="pass", score=score, trace_id=run_id)

    def sync_example(
        self,
        example_id: uuid.UUID,
        *,
        inputs: Optional[dict] = None,
        outputs: Optional[dict] = None,
        metadata: Optional[dict] = None,
        pytest_plugin=None,
        pytest_nodeid=None,
    ) -> None:
        inputs = inputs or {}
        if pytest_plugin and pytest_nodeid:
            update = {"inputs": inputs, "reference_outputs": outputs}
            update = {k: v for k, v in update.items() if v is not None}
            pytest_plugin.update_process_status(pytest_nodeid, update)
        metadata = metadata.copy() if metadata else metadata
        inputs = _serde_example_values(inputs)
        outputs = _serde_example_values(outputs)
        try:
            example = self.client.read_example(example_id=example_id)
        except ls_utils.LangSmithNotFoundError:
            example = self.client.create_example(
                example_id=example_id,
                inputs=inputs,
                outputs=outputs,
                dataset_id=self.id,
                metadata=metadata,
                created_at=self._experiment.start_time,
            )
        else:
            if (
                (inputs != example.inputs)
                or (outputs is not None and outputs != example.outputs)
                or (metadata is not None and metadata != example.metadata)
                or str(example.dataset_id) != str(self.id)
            ):
                self.client.update_example(
                    example_id=example.id,
                    inputs=inputs,
                    outputs=outputs,
                    metadata=metadata,
                    dataset_id=self.id,
                )
                example = self.client.read_example(example_id=example.id)
        if self._dataset_version is None:
            self._dataset_version = example.modified_at
        elif (
            example.modified_at
            and self._dataset_version
            and example.modified_at > self._dataset_version
        ):
            self._dataset_version = example.modified_at

    def _submit_feedback(
        self,
        run_id: ID_TYPE,
        feedback: Union[dict, list],
        pytest_plugin: Any = None,
        pytest_nodeid: Any = None,
        **kwargs: Any,
    ):
        feedback = feedback if isinstance(feedback, list) else [feedback]
        for fb in feedback:
            if pytest_plugin and pytest_nodeid:
                val = fb["score"] if "score" in fb else fb["value"]
                pytest_plugin.update_process_status(
                    pytest_nodeid, {"feedback": {fb["key"]: val}}
                )
            self._executor.submit(
                self._create_feedback, run_id=run_id, feedback=fb, **kwargs
            )

    def _create_feedback(self, run_id: ID_TYPE, feedback: dict, **kwargs: Any) -> None:
        # trace_id will always be run_id here because the feedback is on the root
        # test run
        self.client.create_feedback(run_id, **feedback, **kwargs, trace_id=run_id)

    def shutdown(self):
        self._executor.shutdown()

    def end_run(
        self,
        run_tree,
        example_id,
        outputs,
        reference_outputs,
        metadata,
        pytest_plugin=None,
        pytest_nodeid=None,
    ) -> Future:
        return self._executor.submit(
            self._end_run,
            run_tree=run_tree,
            example_id=example_id,
            outputs=outputs,
            reference_outputs=reference_outputs,
            metadata=metadata,
            pytest_plugin=pytest_plugin,
            pytest_nodeid=pytest_nodeid,
        )

    def _end_run(
        self,
        run_tree,
        example_id,
        outputs,
        reference_outputs,
        metadata,
        pytest_plugin,
        pytest_nodeid,
    ) -> None:
        # TODO: remove this hack so that run durations are correct
        # Ensure example is fully updated
        self.sync_example(
            example_id,
            inputs=run_tree.inputs,
            outputs=reference_outputs,
            metadata=metadata,
        )
        run_tree.end(outputs=outputs)
        run_tree.patch()


class _TestCase:
    def __init__(
        self,
        test_suite: _LangSmithTestSuite,
        example_id: uuid.UUID,
        run_id: uuid.UUID,
        metadata: Optional[dict] = None,
        pytest_plugin: Any = None,
        pytest_nodeid: Any = None,
        inputs: Optional[dict] = None,
        reference_outputs: Optional[dict] = None,
    ) -> None:
        self.test_suite = test_suite
        self.example_id = example_id
        self.run_id = run_id
        self.metadata = metadata
        self.pytest_plugin = pytest_plugin
        self.pytest_nodeid = pytest_nodeid
        self.inputs = inputs
        self.reference_outputs = reference_outputs
        self._logged_reference_outputs: Optional[dict] = None
        self._logged_outputs: Optional[dict] = None

        if pytest_plugin and pytest_nodeid:
            pytest_plugin.add_process_to_test_suite(
                test_suite._dataset.name, pytest_nodeid
            )
            if inputs:
                self.log_inputs(inputs)
            if reference_outputs:
                self.log_reference_outputs(reference_outputs)

    def sync_example(
        self, *, inputs: Optional[dict] = None, outputs: Optional[dict] = None
    ) -> None:
        self.test_suite.sync_example(
            self.example_id,
            inputs=inputs,
            outputs=outputs,
            metadata=self.metadata,
            pytest_plugin=self.pytest_plugin,
            pytest_nodeid=self.pytest_nodeid,
        )

    def submit_feedback(self, *args, **kwargs: Any):
        self.test_suite._submit_feedback(
            *args,
            **{
                **kwargs,
                **dict(
                    pytest_plugin=self.pytest_plugin,
                    pytest_nodeid=self.pytest_nodeid,
                ),
            },
        )

    def log_inputs(self, inputs: dict) -> None:
        if self.pytest_plugin and self.pytest_nodeid:
            self.pytest_plugin.update_process_status(
                self.pytest_nodeid, {"inputs": inputs}
            )

    def log_outputs(self, outputs: dict) -> None:
        self._logged_outputs = outputs
        if self.pytest_plugin and self.pytest_nodeid:
            self.pytest_plugin.update_process_status(
                self.pytest_nodeid, {"outputs": outputs}
            )

    def log_reference_outputs(self, reference_outputs: dict) -> None:
        self._logged_reference_outputs = reference_outputs
        if self.pytest_plugin and self.pytest_nodeid:
            self.pytest_plugin.update_process_status(
                self.pytest_nodeid, {"reference_outputs": reference_outputs}
            )

    def submit_test_result(
        self,
        error: Optional[str] = None,
        skipped: bool = False,
    ) -> None:
        return self.test_suite.submit_result(
            self.run_id,
            error=error,
            skipped=skipped,
            pytest_plugin=self.pytest_plugin,
            pytest_nodeid=self.pytest_nodeid,
        )

    def start_time(self) -> None:
        if self.pytest_plugin and self.pytest_nodeid:
            self.pytest_plugin.update_process_status(
                self.pytest_nodeid, {"start_time": time.time()}
            )

    def end_time(self) -> None:
        if self.pytest_plugin and self.pytest_nodeid:
            self.pytest_plugin.update_process_status(
                self.pytest_nodeid, {"end_time": time.time()}
            )

    def end_run(self, run_tree, outputs: Any) -> None:
        if not (outputs is None or isinstance(outputs, dict)):
            outputs = {"output": outputs}
        self.test_suite.end_run(
            run_tree,
            self.example_id,
            outputs,
            reference_outputs=self._logged_reference_outputs,
            metadata=self.metadata,
            pytest_plugin=self.pytest_plugin,
            pytest_nodeid=self.pytest_nodeid,
        )


_TEST_CASE = contextvars.ContextVar[Optional[_TestCase]]("_TEST_CASE", default=None)


class _UTExtra(TypedDict, total=False):
    client: Optional[ls_client.Client]
    id: Optional[uuid.UUID]
    output_keys: Optional[Sequence[str]]
    test_suite_name: Optional[str]
    cache: Optional[str]
    metadata: Optional[dict]
    repetitions: Optional[int]


def _create_test_case(
    func: Callable,
    *args: Any,
    pytest_request: Any,
    langtest_extra: _UTExtra,
    **kwargs: Any,
) -> _TestCase:
    client = langtest_extra["client"] or rt.get_cached_client()
    output_keys = langtest_extra["output_keys"]
    metadata = langtest_extra["metadata"]
    signature = inspect.signature(func)
    inputs = rh._get_inputs_safe(signature, *args, **kwargs) or None
    outputs = None
    if output_keys:
        outputs = {}
        if not inputs:
            msg = (
                "'output_keys' should only be specified when marked test function has "
                "input arguments."
            )
            raise ValueError(msg)
        for k in output_keys:
            outputs[k] = inputs.pop(k, None)
    test_suite = _LangSmithTestSuite.from_test(
        client, func, langtest_extra.get("test_suite_name")
    )
    example_id, example_name = _get_example_id(func, inputs, test_suite.id)
    example_id = langtest_extra["id"] or example_id
    pytest_plugin = (
        pytest_request.config.pluginmanager.get_plugin("langsmith_output_plugin")
        if pytest_request
        else None
    )
    pytest_nodeid = pytest_request.node.nodeid if pytest_request else None
    if pytest_plugin:
        pytest_plugin.test_suite_urls[test_suite._dataset.name] = (
            cast(str, test_suite._dataset.url)
            + "/compare?selectedSessions="
            + str(test_suite.experiment_id)
        )
    test_case = _TestCase(
        test_suite,
        example_id,
        run_id=uuid.uuid4(),
        metadata=metadata,
        inputs=inputs,
        reference_outputs=outputs,
        pytest_plugin=pytest_plugin,
        pytest_nodeid=pytest_nodeid,
    )
    return test_case


def _run_test(
    func: Callable,
    *test_args: Any,
    pytest_request: Any,
    langtest_extra: _UTExtra,
    **test_kwargs: Any,
) -> None:
    test_case = _create_test_case(
        func,
        *test_args,
        **test_kwargs,
        pytest_request=pytest_request,
        langtest_extra=langtest_extra,
    )
    _TEST_CASE.set(test_case)

    def _test():
        test_case.start_time()
        with rh.trace(
            name=getattr(func, "__name__", "Test"),
            run_id=test_case.run_id,
            reference_example_id=test_case.example_id,
            inputs=test_case.inputs,
            metadata={
                # Experiment run metadata is prefixed with "ls_example_" in
                # the ingest backend, but we must reproduce this behavior here
                # because the example may not have been created before the trace
                # starts.
                f"ls_example_{k}": v
                for k, v in (test_case.metadata or {}).items()
            },
            project_name=test_case.test_suite.name,
            exceptions_to_handle=(SkipException,),
            _end_on_exit=False,
        ) as run_tree:
            try:
                result = func(*test_args, **test_kwargs)
            except SkipException as e:
                test_case.submit_test_result(error=repr(e), skipped=True)
                test_case.end_run(run_tree, {"skipped_reason": repr(e)})
                raise e
            except BaseException as e:
                test_case.submit_test_result(error=repr(e))
                test_case.end_run(run_tree, None)
                raise e
            else:
                test_case.end_run(run_tree, result)
            finally:
                test_case.end_time()
        try:
            test_case.submit_test_result()
        except BaseException as e:
            logger.warning(
                f"Failed to create feedback for run_id {test_case.run_id}:\n{e}"
            )

    if langtest_extra["cache"]:
        cache_path = Path(langtest_extra["cache"]) / f"{test_case.test_suite.id}.yaml"
    else:
        cache_path = None
    current_context = rh.get_tracing_context()
    metadata = {
        **(current_context["metadata"] or {}),
        **{
            "experiment": test_case.test_suite.experiment.name,
            "reference_example_id": str(test_case.example_id),
        },
    }
    with (
        rh.tracing_context(**{**current_context, "metadata": metadata}),
        ls_utils.with_optional_cache(
            cache_path, ignore_hosts=[test_case.test_suite.client.api_url]
        ),
    ):
        _test()


async def _arun_test(
    func: Callable,
    *test_args: Any,
    pytest_request: Any,
    langtest_extra: _UTExtra,
    **test_kwargs: Any,
) -> None:
    test_case = _create_test_case(
        func,
        *test_args,
        **test_kwargs,
        pytest_request=pytest_request,
        langtest_extra=langtest_extra,
    )
    _TEST_CASE.set(test_case)

    async def _test():
        test_case.start_time()
        with rh.trace(
            name=getattr(func, "__name__", "Test"),
            run_id=test_case.run_id,
            reference_example_id=test_case.example_id,
            inputs=test_case.inputs,
            metadata={
                # Experiment run metadata is prefixed with "ls_example_" in
                # the ingest backend, but we must reproduce this behavior here
                # because the example may not have been created before the trace
                # starts.
                f"ls_example_{k}": v
                for k, v in (test_case.metadata or {}).items()
            },
            project_name=test_case.test_suite.name,
            exceptions_to_handle=(SkipException,),
            _end_on_exit=False,
        ) as run_tree:
            try:
                result = await func(*test_args, **test_kwargs)
            except SkipException as e:
                test_case.submit_test_result(error=repr(e), skipped=True)
                test_case.end_run(run_tree, {"skipped_reason": repr(e)})
                raise e
            except BaseException as e:
                test_case.submit_test_result(error=repr(e))
                test_case.end_run(run_tree, None)
                raise e
            else:
                test_case.end_run(run_tree, result)
            finally:
                test_case.end_time()
        try:
            test_case.submit_test_result()
        except BaseException as e:
            logger.warning(
                f"Failed to create feedback for run_id {test_case.run_id}:\n{e}"
            )

    if langtest_extra["cache"]:
        cache_path = Path(langtest_extra["cache"]) / f"{test_case.test_suite.id}.yaml"
    else:
        cache_path = None
    current_context = rh.get_tracing_context()
    metadata = {
        **(current_context["metadata"] or {}),
        **{
            "experiment": test_case.test_suite.experiment.name,
            "reference_example_id": str(test_case.example_id),
        },
    }
    with (
        rh.tracing_context(**{**current_context, "metadata": metadata}),
        ls_utils.with_optional_cache(
            cache_path, ignore_hosts=[test_case.test_suite.client.api_url]
        ),
    ):
        await _test()


# For backwards compatibility
unit = test


def log_inputs(inputs: dict, /) -> None:
    """Log run inputs from within a pytest test run.

    .. warning::

        This API is in beta and might change in future versions.

    Should only be used in pytest tests decorated with @pytest.mark.langsmith.

    Args:
        inputs: Inputs to log.

    Example:
        .. code-block:: python

            from langsmith import testing as t


            @pytest.mark.langsmith
            def test_foo() -> None:
                x = 0
                y = 1
                t.log_inputs({"x": x, "y": y})
                assert foo(x, y) == 2
    """
    if ls_utils.test_tracking_is_disabled():
        logger.info("LANGSMITH_TEST_TRACKING is set to 'false'. Skipping log_inputs.")
        return
    run_tree = rh.get_current_run_tree()
    test_case = _TEST_CASE.get()
    if not run_tree or not test_case:
        msg = (
            "log_inputs should only be called within a pytest test decorated with "
            "@pytest.mark.langsmith, and with tracing enabled (by setting the "
            "LANGSMITH_TRACING environment variable to 'true')."
        )
        raise ValueError(msg)
    run_tree.add_inputs(inputs)
    test_case.log_inputs(inputs)


def log_outputs(outputs: dict, /) -> None:
    """Log run outputs from within a pytest test run.

    .. warning::

        This API is in beta and might change in future versions.

    Should only be used in pytest tests decorated with @pytest.mark.langsmith.

    Args:
        outputs: Outputs to log.

    Example:
        .. code-block:: python

            from langsmith import testing as t


            @pytest.mark.langsmith
            def test_foo() -> None:
                x = 0
                y = 1
                result = foo(x, y)
                t.log_outputs({"foo": result})
                assert result == 2
    """
    if ls_utils.test_tracking_is_disabled():
        logger.info("LANGSMITH_TEST_TRACKING is set to 'false'. Skipping log_outputs.")
        return
    run_tree = rh.get_current_run_tree()
    test_case = _TEST_CASE.get()
    if not run_tree or not test_case:
        msg = (
            "log_outputs should only be called within a pytest test decorated with "
            "@pytest.mark.langsmith, and with tracing enabled (by setting the "
            "LANGSMITH_TRACING environment variable to 'true')."
        )
        raise ValueError(msg)
    outputs = _dumpd(outputs)
    run_tree.add_outputs(outputs)
    test_case.log_outputs(outputs)


def log_reference_outputs(reference_outputs: dict, /) -> None:
    """Log example reference outputs from within a pytest test run.

    .. warning::

        This API is in beta and might change in future versions.

    Should only be used in pytest tests decorated with @pytest.mark.langsmith.

    Args:
        outputs: Reference outputs to log.

    Example:
        .. code-block:: python

            from langsmith import testing


            @pytest.mark.langsmith
            def test_foo() -> None:
                x = 0
                y = 1
                expected = 2
                testing.log_reference_outputs({"foo": expected})
                assert foo(x, y) == expected
    """
    if ls_utils.test_tracking_is_disabled():
        logger.info(
            "LANGSMITH_TEST_TRACKING is set to 'false'. Skipping log_reference_outputs."
        )
        return
    test_case = _TEST_CASE.get()
    if not test_case:
        msg = (
            "log_reference_outputs should only be called within a pytest test "
            "decorated with @pytest.mark.langsmith."
        )
        raise ValueError(msg)
    test_case.log_reference_outputs(reference_outputs)


def log_feedback(
    feedback: Optional[Union[dict, list[dict]]] = None,
    /,
    *,
    key: str,
    score: Optional[Union[int, bool, float]] = None,
    value: Optional[Union[str, int, float, bool]] = None,
    **kwargs: Any,
) -> None:
    """Log run feedback from within a pytest test run.

    .. warning::

        This API is in beta and might change in future versions.

    Should only be used in pytest tests decorated with @pytest.mark.langsmith.

    Args:
        key: Feedback name.
        score: Numerical feedback value.
        value: Categorical feedback value
        kwargs: Any other Client.create_feedback args.

    Example:
        .. code-block:: python

            import pytest
            from langsmith import testing as t


            @pytest.mark.langsmith
            def test_foo() -> None:
                x = 0
                y = 1
                expected = 2
                result = foo(x, y)
                t.log_feedback(key="right_type", score=isinstance(result, int))
                assert result == expected
    """
    if ls_utils.test_tracking_is_disabled():
        logger.info("LANGSMITH_TEST_TRACKING is set to 'false'. Skipping log_feedback.")
        return
    if feedback and any((key, score, value)):
        msg = "Must specify one of 'feedback' and ('key', 'score', 'value'), not both."
        raise ValueError(msg)
    elif not (feedback or key):
        msg = "Must specify at least one of 'feedback' or ('key', 'score', value')."
        raise ValueError(msg)
    elif key:
        feedback = {"key": key}
        if score is not None:
            feedback["score"] = score
        if value is not None:
            feedback["value"] = value
    else:
        pass

    run_tree = rh.get_current_run_tree()
    test_case = _TEST_CASE.get()
    if not run_tree or not test_case:
        msg = (
            "log_feedback should only be called within a pytest test decorated with "
            "@pytest.mark.langsmith, and with tracing enabled (by setting the "
            "LANGSMITH_TRACING environment variable to 'true')."
        )
        raise ValueError(msg)
    if run_tree.session_name == "evaluators" and run_tree.metadata.get(
        "reference_run_id"
    ):
        run_id = run_tree.metadata["reference_run_id"]
        run_tree.add_outputs(
            feedback if isinstance(feedback, dict) else {"feedback": feedback}
        )
        kwargs["source_run_id"] = run_tree.id
    else:
        run_id = run_tree.trace_id
    test_case.submit_feedback(run_id, cast(Union[list, dict], feedback), **kwargs)


@contextlib.contextmanager
def trace_feedback(
    *, name: str = "Feedback"
) -> Generator[Optional[run_trees.RunTree], None, None]:
    """Trace the computation of a pytest run feedback as its own run.

    .. warning::

        This API is in beta and might change in future versions.

    Args:
        name: Feedback run name. Defaults to "Feedback".

    Example:
        .. code-block:: python

            import openai
            import pytest

            from langsmith import testing as t
            from langsmith import wrappers

            oai_client = wrappers.wrap_openai(openai.Client())


            @pytest.mark.langsmith
            def test_openai_says_hello():
                # Traced code will be included in the test case
                text = "Say hello!"
                response = oai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant."},
                        {"role": "user", "content": text},
                    ],
                )
                t.log_inputs({"text": text})
                t.log_outputs({"response": response.choices[0].message.content})
                t.log_reference_outputs({"response": "hello!"})

                # Use this context manager to trace any steps used for generating evaluation
                # feedback separately from the main application logic
                with t.trace_feedback():
                    grade = oai_client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[
                            {
                                "role": "system",
                                "content": "Return 1 if 'hello' is in the user message and 0 otherwise.",
                            },
                            {
                                "role": "user",
                                "content": response.choices[0].message.content,
                            },
                        ],
                    )
                    # Make sure to log relevant feedback within the context for the
                    # trace to be associated with this feedback.
                    t.log_feedback(
                        key="llm_judge", score=float(grade.choices[0].message.content)
                    )

                assert "hello" in response.choices[0].message.content.lower()
    """  # noqa: E501
    if ls_utils.test_tracking_is_disabled():
        logger.info("LANGSMITH_TEST_TRACKING is set to 'false'. Skipping log_feedback.")
        yield None
        return
    test_case = _TEST_CASE.get()
    if not test_case:
        msg = (
            "trace_feedback should only be called within a pytest test decorated with "
            "@pytest.mark.langsmith, and with tracing enabled (by setting the "
            "LANGSMITH_TRACING environment variable to 'true')."
        )
        raise ValueError(msg)
    metadata = {
        "experiment": test_case.test_suite.experiment.name,
        "reference_example_id": test_case.example_id,
        "reference_run_id": test_case.run_id,
    }
    with rh.trace(
        name=name,
        inputs=test_case._logged_outputs,
        parent="ignore",
        project_name="evaluators",
        metadata=metadata,
    ) as run_tree:
        yield run_tree


def _stringify(x: Any) -> str:
    try:
        return dumps_json(x).decode("utf-8", errors="surrogateescape")
    except Exception:
        return str(x)


def _dumpd(x: Any) -> Any:
    """Serialize LangChain Serializable objects."""
    dumpd = _get_langchain_dumpd()
    if not dumpd:
        return x
    try:
        serialized = dumpd(x)
        return serialized
    except Exception:
        return x


@functools.lru_cache
def _get_langchain_dumpd() -> Optional[Callable]:
    try:
        from langchain_core.load import dumpd

        return dumpd
    except ImportError:
        return None
