"""V2 Evaluation Interface."""

from __future__ import annotations

import asyncio
import concurrent.futures as cf
import io
import logging
import pathlib
import uuid
from collections.abc import AsyncIterable, AsyncIterator, Awaitable, Iterable, Sequence
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Literal,
    Optional,
    TypeVar,
    Union,
    cast,
)

import langsmith
from langsmith import run_helpers as rh
from langsmith import run_trees, schemas
from langsmith import run_trees as rt
from langsmith import utils as ls_utils
from langsmith._internal import _aiter as aitertools
from langsmith._internal._beta_decorator import _warn_once
from langsmith.evaluation._runner import (
    AEVALUATOR_T,
    DATA_T,
    EVALUATOR_T,
    ExperimentResultRow,
    _evaluators_include_attachments,
    _ExperimentManagerMixin,
    _extract_feedback_keys,
    _ForwardResults,
    _get_target_args,
    _is_langchain_runnable,
    _load_examples_map,
    _load_experiment,
    _load_tqdm,
    _load_traces,
    _resolve_data,
    _resolve_evaluators,
    _resolve_experiment,
    _target_include_attachments,
    _to_pandas,
    _wrap_summary_evaluators,
)
from langsmith.evaluation.evaluator import (
    SUMMARY_EVALUATOR_T,
    EvaluationResult,
    EvaluationResults,
    RunEvaluator,
)

if TYPE_CHECKING:
    import pandas as pd
    from langchain_core.runnables import Runnable

    DataFrame = pd.DataFrame
else:
    DataFrame = Any

logger = logging.getLogger(__name__)

ATARGET_T = Union[
    Callable[[dict], Awaitable[dict]], Callable[[dict, dict], Awaitable[dict]]
]


async def aevaluate(
    target: Union[
        ATARGET_T, AsyncIterable[dict], Runnable, str, uuid.UUID, schemas.TracerSession
    ],
    /,
    data: Union[
        DATA_T, AsyncIterable[schemas.Example], Iterable[schemas.Example], None
    ] = None,
    evaluators: Optional[Sequence[Union[EVALUATOR_T, AEVALUATOR_T]]] = None,
    summary_evaluators: Optional[Sequence[SUMMARY_EVALUATOR_T]] = None,
    metadata: Optional[dict] = None,
    experiment_prefix: Optional[str] = None,
    description: Optional[str] = None,
    max_concurrency: Optional[int] = 0,
    num_repetitions: int = 1,
    client: Optional[langsmith.Client] = None,
    blocking: bool = True,
    experiment: Optional[Union[schemas.TracerSession, str, uuid.UUID]] = None,
    upload_results: bool = True,
    error_handling: Literal["log", "ignore"] = "log",
    **kwargs: Any,
) -> AsyncExperimentResults:
    r"""Evaluate an async target system on a given dataset.

    Args:
        target (AsyncCallable[[dict], dict] | AsyncIterable[dict] | Runnable | EXPERIMENT_T | Tuple[EXPERIMENT_T, EXPERIMENT_T]):
            The target system or experiment(s) to evaluate. Can be an async function
            that takes a dict and returns a dict, a langchain Runnable, an
            existing experiment ID, or a two-tuple of experiment IDs.
        data (Union[DATA_T, AsyncIterable[schemas.Example]]): The dataset to evaluate on. Can be a dataset name, a list of
            examples, an async generator of examples, or an async iterable of examples.
        evaluators (Optional[Sequence[EVALUATOR_T]]): A list of evaluators to run
            on each example. Defaults to None.
        summary_evaluators (Optional[Sequence[SUMMARY_EVALUATOR_T]]): A list of summary
            evaluators to run on the entire dataset. Defaults to None.
        metadata (Optional[dict]): Metadata to attach to the experiment.
            Defaults to None.
        experiment_prefix (Optional[str]): A prefix to provide for your experiment name.
            Defaults to None.
        description (Optional[str]): A description of the experiment.
        max_concurrency (int | None): The maximum number of concurrent
            evaluations to run. If None then no limit is set. If 0 then no concurrency.
            Defaults to 0.
        num_repetitions (int): The number of times to run the evaluation.
            Each item in the dataset will be run and evaluated this many times.
            Defaults to 1.
        client (Optional[langsmith.Client]): The LangSmith client to use.
            Defaults to None.
        blocking (bool): Whether to block until the evaluation is complete.
            Defaults to True.
        experiment (Optional[schemas.TracerSession]): An existing experiment to
            extend. If provided, experiment_prefix is ignored. For advanced
            usage only.
        load_nested: Whether to load all child runs for the experiment.
            Default is to only load the top-level root runs. Should only be specified
            when evaluating an existing experiment.
        error_handling (str, default="log"): How to handle individual run errors. 'log'
            will trace the runs with the error message as part of the experiment,
            'ignore' will not count the run as part of the experiment at all.

    Returns:
        AsyncIterator[ExperimentResultRow]: An async iterator over the experiment results.

    Environment:
        - LANGSMITH_TEST_CACHE: If set, API calls will be cached to disk to save time and
            cost during testing. Recommended to commit the cache files to your repository
            for faster CI/CD runs.
            Requires the 'langsmith[vcr]' package to be installed.

    Examples:
        >>> from typing import Sequence
        >>> from langsmith import Client, aevaluate
        >>> from langsmith.schemas import Example, Run
        >>> client = Client()
        >>> dataset = client.clone_public_dataset(
        ...     "https://smith.langchain.com/public/419dcab2-1d66-4b94-8901-0357ead390df/d"
        ... )
        >>> dataset_name = "Evaluate Examples"

        Basic usage:

        >>> def accuracy(run: Run, example: Example):
        ...     # Row-level evaluator for accuracy.
        ...     pred = run.outputs["output"]
        ...     expected = example.outputs["answer"]
        ...     return {"score": expected.lower() == pred.lower()}

        >>> def precision(runs: Sequence[Run], examples: Sequence[Example]):
        ...     # Experiment-level evaluator for precision.
        ...     # TP / (TP + FP)
        ...     predictions = [run.outputs["output"].lower() for run in runs]
        ...     expected = [example.outputs["answer"].lower() for example in examples]
        ...     # yes and no are the only possible answers
        ...     tp = sum([p == e for p, e in zip(predictions, expected) if p == "yes"])
        ...     fp = sum([p == "yes" and e == "no" for p, e in zip(predictions, expected)])
        ...     return {"score": tp / (tp + fp)}

        >>> import asyncio
        >>> async def apredict(inputs: dict) -> dict:
        ...     # This can be any async function or just an API call to your app.
        ...     await asyncio.sleep(0.1)
        ...     return {"output": "Yes"}
        >>> results = asyncio.run(
        ...     aevaluate(
        ...         apredict,
        ...         data=dataset_name,
        ...         evaluators=[accuracy],
        ...         summary_evaluators=[precision],
        ...         experiment_prefix="My Experiment",
        ...         description="Evaluate the accuracy of the model asynchronously.",
        ...         metadata={
        ...             "my-prompt-version": "abcd-1234",
        ...         },
        ...     )
        ... )  # doctest: +ELLIPSIS
        View the evaluation results for experiment:...

        Evaluating over only a subset of the examples using an async generator:

        >>> async def example_generator():
        ...     examples = client.list_examples(dataset_name=dataset_name, limit=5)
        ...     for example in examples:
        ...         yield example
        >>> results = asyncio.run(
        ...     aevaluate(
        ...         apredict,
        ...         data=example_generator(),
        ...         evaluators=[accuracy],
        ...         summary_evaluators=[precision],
        ...         experiment_prefix="My Subset Experiment",
        ...         description="Evaluate a subset of examples asynchronously.",
        ...     )
        ... )  # doctest: +ELLIPSIS
        View the evaluation results for experiment:...

        Streaming each prediction to more easily + eagerly debug.

        >>> results = asyncio.run(
        ...     aevaluate(
        ...         apredict,
        ...         data=dataset_name,
        ...         evaluators=[accuracy],
        ...         summary_evaluators=[precision],
        ...         experiment_prefix="My Streaming Experiment",
        ...         description="Streaming predictions for debugging.",
        ...         blocking=False,
        ...     )
        ... )  # doctest: +ELLIPSIS
        View the evaluation results for experiment:...

        >>> async def aenumerate(iterable):
        ...     async for elem in iterable:
        ...         print(elem)
        >>> asyncio.run(aenumerate(results))

        Running without concurrency:

        >>> results = asyncio.run(
        ...     aevaluate(
        ...         apredict,
        ...         data=dataset_name,
        ...         evaluators=[accuracy],
        ...         summary_evaluators=[precision],
        ...         experiment_prefix="My Experiment Without Concurrency",
        ...         description="This was run without concurrency.",
        ...         max_concurrency=0,
        ...     )
        ... )  # doctest: +ELLIPSIS
        View the evaluation results for experiment:...

        Using Async evaluators:

        >>> async def helpfulness(run: Run, example: Example):
        ...     # Row-level evaluator for helpfulness.
        ...     await asyncio.sleep(5)  # Replace with your LLM API call
        ...     return {"score": run.outputs["output"] == "Yes"}

        >>> results = asyncio.run(
        ...     aevaluate(
        ...         apredict,
        ...         data=dataset_name,
        ...         evaluators=[helpfulness],
        ...         summary_evaluators=[precision],
        ...         experiment_prefix="My Helpful Experiment",
        ...         description="Applying async evaluators example.",
        ...     )
        ... )  # doctest: +ELLIPSIS
        View the evaluation results for experiment:...


    .. versionchanged:: 0.2.0

        'max_concurrency' default updated from None (no limit on concurrency)
        to 0 (no concurrency at all).
    """  # noqa: E501
    if isinstance(target, (str, uuid.UUID, schemas.TracerSession)):
        invalid_args = {
            "num_repetitions": num_repetitions > 1,
            "experiment": bool(experiment),
            "upload_results": not upload_results,
            "experiment_prefix": bool(experiment_prefix),
            "data": bool(data),
        }
        if any(invalid_args.values()):
            msg = (
                f"Received invalid arguments. "
                f"{tuple(k for k, v in invalid_args.items() if v)} should not be "
                f"specified when target is an existing experiment."
            )
            raise ValueError(msg)
        target_id = target if isinstance(target, (str, uuid.UUID)) else target.id
        logger.debug(f"Running evaluation over existing experiment {target_id}...")
        return await aevaluate_existing(
            target,
            evaluators=evaluators,
            summary_evaluators=summary_evaluators,
            metadata=metadata,
            max_concurrency=max_concurrency,
            client=client,
            blocking=blocking,
            **kwargs,
        )
    elif isinstance(target, (list, tuple)):
        msg = (
            "Running a comparison of two existing experiments asynchronously is not "
            "currently supported. Please use the `evaluate()` method instead and make "
            "sure that your evaluators are defined as synchronous functions."
        )
        raise ValueError(msg)
    elif kwargs:
        msg = (
            f"Received unsupported arguments {kwargs}. These arguments are not "
            f"supported when creating a new experiment."
        )
        raise ValueError(msg)
    elif not data:
        msg = "Must specify 'data' when running evaluations over a target function."
        raise ValueError(msg)
    elif experiment and experiment_prefix:
        msg = (
            "Expected at most one of 'experiment' or 'experiment_prefix',"
            " but both were provided. "
            f"Got: experiment={experiment}, experiment_prefix={experiment_prefix}"
        )
        raise ValueError(msg)
    else:
        if not upload_results:
            _warn_once("'upload_results' parameter is in beta.")
        logger.debug(f"Running evaluation over target system {target}...")
        return await _aevaluate(
            target,
            data=data,
            evaluators=evaluators,
            summary_evaluators=summary_evaluators,
            metadata=metadata,
            experiment_prefix=experiment_prefix,
            description=description,
            max_concurrency=max_concurrency,
            num_repetitions=num_repetitions,
            client=client,
            blocking=blocking,
            experiment=experiment,
            upload_results=upload_results,
            error_handling=error_handling,
        )


async def aevaluate_existing(
    experiment: Union[str, uuid.UUID, schemas.TracerSession],
    /,
    evaluators: Optional[Sequence[Union[EVALUATOR_T, AEVALUATOR_T]]] = None,
    summary_evaluators: Optional[Sequence[SUMMARY_EVALUATOR_T]] = None,
    metadata: Optional[dict] = None,
    max_concurrency: Optional[int] = 0,
    client: Optional[langsmith.Client] = None,
    load_nested: bool = False,
    blocking: bool = True,
) -> AsyncExperimentResults:
    r"""Evaluate existing experiment runs asynchronously.

    Args:
        experiment (Union[str, uuid.UUID]): The identifier of the experiment to evaluate.
        evaluators (Optional[Sequence[EVALUATOR_T]]): Optional sequence of evaluators to use for individual run evaluation.
        summary_evaluators (Optional[Sequence[SUMMARY_EVALUATOR_T]]): Optional sequence of evaluators
            to apply over the entire dataset.
        metadata (Optional[dict]): Optional metadata to include in the evaluation results.
        max_concurrency (int | None): The maximum number of concurrent
            evaluations to run. If None then no limit is set. If 0 then no concurrency.
            Defaults to 0.
        client (Optional[langsmith.Client]): Optional Langsmith client to use for evaluation.
        load_nested: Whether to load all child runs for the experiment.
            Default is to only load the top-level root runs.
        blocking (bool): Whether to block until evaluation is complete.

    Returns:
        AsyncIterator[ExperimentResultRow]: An async iterator over the experiment results.

    Examples:
        Define your evaluators

        >>> from typing import Sequence
        >>> from langsmith.schemas import Example, Run
        >>> def accuracy(run: Run, example: Example):
        ...     # Row-level evaluator for accuracy.
        ...     pred = run.outputs["output"]
        ...     expected = example.outputs["answer"]
        ...     return {"score": expected.lower() == pred.lower()}
        >>> def precision(runs: Sequence[Run], examples: Sequence[Example]):
        ...     # Experiment-level evaluator for precision.
        ...     # TP / (TP + FP)
        ...     predictions = [run.outputs["output"].lower() for run in runs]
        ...     expected = [example.outputs["answer"].lower() for example in examples]
        ...     # yes and no are the only possible answers
        ...     tp = sum([p == e for p, e in zip(predictions, expected) if p == "yes"])
        ...     fp = sum([p == "yes" and e == "no" for p, e in zip(predictions, expected)])
        ...     return {"score": tp / (tp + fp)}

        Load the experiment and run the evaluation.

        >>> import asyncio
        >>> import uuid
        >>> from langsmith import Client, aevaluate, aevaluate_existing
        >>> client = Client()
        >>> dataset_name = "__doctest_aevaluate_existing_" + uuid.uuid4().hex[:8]
        >>> dataset = client.create_dataset(dataset_name)
        >>> example = client.create_example(
        ...     inputs={"question": "What is 2+2?"},
        ...     outputs={"answer": "4"},
        ...     dataset_id=dataset.id
        ... )
        >>> async def apredict(inputs: dict) -> dict:
        ...     await asyncio.sleep(0.001)
        ...     return {"output": "4"}
        >>> results = asyncio.run(
        ...     aevaluate(
        ...         apredict,
        ...         data=dataset_name,
        ...         experiment_prefix="doctest_experiment"
        ...     )
        ... )  # doctest: +ELLIPSIS
        View the evaluation results for experiment:...
        >>> experiment_id = results.experiment_name
        >>> # Consume all results to ensure evaluation is complete
        >>> async def consume_results():
        ...     result_list = [r async for r in results]
        ...     return len(result_list) > 0
        >>> asyncio.run(consume_results())
        True
        >>> import time
        >>> time.sleep(3)
        >>> results = asyncio.run(
        ...     aevaluate_existing(
        ...         experiment_id,
        ...         evaluators=[accuracy],
        ...         summary_evaluators=[precision],
        ...     )
        ... )  # doctest: +ELLIPSIS
        View the evaluation results for experiment:...
        >>> client.delete_dataset(dataset_id=dataset.id)


    """  # noqa: E501
    client = client or run_trees.get_cached_client()
    project = (
        experiment
        if isinstance(experiment, schemas.TracerSession)
        else (await aitertools.aio_to_thread(_load_experiment, experiment, client))
    )
    runs = await aitertools.aio_to_thread(
        _load_traces, experiment, client, load_nested=load_nested
    )
    data_map = await aitertools.aio_to_thread(_load_examples_map, client, project)
    data = [data_map[run.reference_example_id] for run in runs]
    return await _aevaluate(
        runs,
        data=data,
        evaluators=evaluators,
        summary_evaluators=summary_evaluators,
        metadata=metadata,
        max_concurrency=max_concurrency,
        client=client,
        blocking=blocking,
        experiment=project,
    )


async def _aevaluate(
    target: Union[ATARGET_T, AsyncIterable[dict], Iterable[schemas.Run], Runnable],
    /,
    data: Union[DATA_T, AsyncIterable[schemas.Example]],
    evaluators: Optional[Sequence[Union[EVALUATOR_T, AEVALUATOR_T]]] = None,
    summary_evaluators: Optional[Sequence[SUMMARY_EVALUATOR_T]] = None,
    metadata: Optional[dict] = None,
    experiment_prefix: Optional[str] = None,
    description: Optional[str] = None,
    max_concurrency: Optional[int] = None,
    num_repetitions: int = 1,
    client: Optional[langsmith.Client] = None,
    blocking: bool = True,
    experiment: Optional[Union[schemas.TracerSession, str, uuid.UUID]] = None,
    upload_results: bool = True,
    error_handling: Literal["log", "ignore"] = "log",
) -> AsyncExperimentResults:
    is_async_target = (
        asyncio.iscoroutinefunction(target)
        or (hasattr(target, "__aiter__") and asyncio.iscoroutine(target.__aiter__()))
        or _is_langchain_runnable(target)
    )
    client = client or rt.get_cached_client()
    runs = None if is_async_target else cast(Iterable[schemas.Run], target)
    experiment_, runs = await aitertools.aio_to_thread(
        _resolve_experiment,
        experiment,
        runs,
        client,
    )
    num_include_attachments = int(
        _target_include_attachments(target)
    ) + _evaluators_include_attachments(evaluators)
    manager = await _AsyncExperimentManager(
        data,
        client=client,
        metadata=metadata,
        experiment=experiment_ or experiment_prefix,
        description=description,
        num_repetitions=num_repetitions,
        runs=runs,
        include_attachments=num_include_attachments > 0,
        reuse_attachments=num_repetitions * num_include_attachments > 1,
        upload_results=upload_results,
        error_handling=error_handling,
    ).astart()
    cache_dir = ls_utils.get_cache_dir(None)
    if cache_dir is not None:
        dsid = await manager.get_dataset_id()
        cache_path = pathlib.Path(cache_dir) / f"{dsid}.yaml"
    else:
        cache_path = None
    with ls_utils.with_optional_cache(cache_path, ignore_hosts=[client.api_url]):
        if is_async_target:
            if evaluators:
                # Run predictions and evaluations in a single pipeline
                manager = await manager.awith_predictions_and_evaluators(
                    cast(ATARGET_T, target), evaluators, max_concurrency=max_concurrency
                )
            else:
                manager = await manager.awith_predictions(
                    cast(ATARGET_T, target), max_concurrency=max_concurrency
                )
            if summary_evaluators:
                manager = await manager.awith_summary_evaluators(summary_evaluators)
        else:
            if evaluators:
                manager = await manager.awith_evaluators(
                    evaluators, max_concurrency=max_concurrency
                )
            if summary_evaluators:
                manager = await manager.awith_summary_evaluators(summary_evaluators)
        results = AsyncExperimentResults(manager)
        if blocking:
            await results.wait()
        return results


class _AsyncExperimentManager(_ExperimentManagerMixin):
    """Manage the execution of experiments asynchronously.

    Supports lazily running predictions and evaluations in parallel to facilitate
    result streaming and early debugging.

    Args:
        data (DATA_T): The data used for the experiment. Can be a dataset name or ID OR
            a generator of examples.
        runs (Optional[Iterable[schemas.Run]]): The runs associated with the experiment
            predictions.
        experiment (Optional[schemas.TracerSession]): The tracer session
            associated with the experiment.
        experiment_prefix (Optional[str]): The prefix for the experiment name.
        description (Optional[str]): The description for the experiment.
        metadata (Optional[dict]): Additional metadata for the experiment.
        client (Optional[langsmith.Client]): The Langsmith client used for
             the experiment.
        evaluation_results (Optional[Iterable[EvaluationResults]]): The evaluation
            sresults for the experiment.
        summary_results (Optional[Iterable[EvaluationResults]]): The aggregate results
            for the experiment.
        num_repetitions (Optional[int], default=1): The number of repetitions for
            the experiment.
        include_attachments (Optional[bool], default=False): Whether to include
            attachments. This is used for when we pull the examples for the experiment.
        reuse_attachments (Optional[bool], default=False): Whether to reuse attachments
            from examples. This is True if we need to reuse attachments across multiple
            target/evaluator functions.
        upload_results (Optional[bool], default=True): Whether to upload results
            to Langsmith.
        attachment_raw_data_dict (Optional[dict]): A dictionary to store raw data
            for attachments. Only used if we reuse attachments across multiple
            target/evaluator functions.
        error_handling (str, default="log"): How to handle individual run errors. 'log'
            will trace the runs with the error message as part of the experiment,
            'ignore' will not count the run as part of the experiment at all.
    """

    def __init__(
        self,
        data: Union[DATA_T, AsyncIterable[schemas.Example]],
        /,
        experiment: Optional[Union[schemas.TracerSession, str]] = None,
        metadata: Optional[dict] = None,
        runs: Optional[Union[Iterable[schemas.Run], AsyncIterable[schemas.Run]]] = None,
        client: Optional[langsmith.Client] = None,
        evaluation_results: Optional[AsyncIterable[EvaluationResults]] = None,
        summary_results: Optional[AsyncIterable[EvaluationResults]] = None,
        description: Optional[str] = None,
        num_repetitions: int = 1,
        include_attachments: bool = False,
        reuse_attachments: bool = False,
        upload_results: bool = True,
        attachment_raw_data_dict: Optional[dict] = None,
        error_handling: Literal["log", "ignore"] = "log",
    ):
        super().__init__(
            experiment=experiment,
            metadata=metadata,
            client=client,
            description=description,
        )
        self._data = data
        self._examples: Optional[AsyncIterable[schemas.Example]] = None
        self._runs = (
            aitertools.ensure_async_iterator(runs) if runs is not None else None
        )
        self._evaluation_results = evaluation_results
        self._summary_results = summary_results
        self._num_repetitions = num_repetitions
        self._include_attachments = include_attachments
        self._reuse_attachments = reuse_attachments
        self._upload_results = upload_results
        self._attachment_raw_data_dict = attachment_raw_data_dict
        self._error_handling = error_handling

    def _reset_example_attachments(self, example: schemas.Example) -> schemas.Example:
        """Reset attachment readers for an example.

        This is only in the case that an attachment is going to be used by more
        than 1 callable (target + evaluators). In that case we keep a single copy
        of the attachment data in self._attachment_raw_data_dict, and create
        readers from that data. This makes it so that we don't have to keep
        copies of the same data in memory, instead we can just create readers
        from the same data.
        """
        if not hasattr(example, "attachments") or not example.attachments:
            return example

        new_attachments: dict[str, schemas.AttachmentInfo] = {}
        for name, attachment in example.attachments.items():
            if (
                self._attachment_raw_data_dict is not None
                and str(example.id) + name in self._attachment_raw_data_dict
            ):
                new_attachments[name] = {
                    "presigned_url": attachment["presigned_url"],
                    "reader": io.BytesIO(
                        self._attachment_raw_data_dict[str(example.id) + name]
                    ),
                    "mime_type": attachment["mime_type"],
                }
            else:
                new_attachments[name] = attachment

        # Create a new Example instance with the updated attachments
        return schemas.Example(
            id=example.id,
            created_at=example.created_at,
            dataset_id=example.dataset_id,
            inputs=example.inputs,
            outputs=example.outputs,
            metadata=example.metadata,
            modified_at=example.modified_at,
            runs=example.runs,
            source_run_id=example.source_run_id,
            attachments=new_attachments,
            _host_url=example._host_url,
            _tenant_id=example._tenant_id,
        )

    async def aget_examples(self) -> AsyncIterator[schemas.Example]:
        if self._examples is None:
            self._examples = _aresolve_data(
                self._data,
                client=self.client,
                include_attachments=self._include_attachments,
            )
            if self._reuse_attachments and self._attachment_raw_data_dict is None:
                examples_copy, self._examples = aitertools.atee(self._examples)
                self._attachment_raw_data_dict = {
                    str(e.id) + name: value["reader"].read()
                    async for e in examples_copy
                    for name, value in (e.attachments or {}).items()
                }
            if self._num_repetitions > 1:
                examples_list = [example async for example in self._examples]
                self._examples = async_chain_from_iterable(
                    [
                        async_iter_from_list(
                            [
                                self._reset_example_attachments(example)
                                for example in examples_list
                            ]
                        )
                        for _ in range(self._num_repetitions)
                    ]
                )

        self._examples, examples_iter = aitertools.atee(
            aitertools.ensure_async_iterator(self._examples), 2, lock=asyncio.Lock()
        )
        return examples_iter

    async def get_dataset_id(self) -> str:
        if self._experiment is None or not getattr(
            self._experiment, "reference_dataset_id", None
        ):
            example = await aitertools.py_anext(await self.aget_examples())
            if example is None:
                raise ValueError("No examples found in the dataset.")
            return str(example.dataset_id)
        return str(self._experiment.reference_dataset_id)

    async def aget_runs(self) -> AsyncIterator[schemas.Run]:
        if self._runs is None:
            raise ValueError("Runs not loaded yet.")
        self._runs, runs = aitertools.atee(
            aitertools.ensure_async_iterator(self._runs), 2, lock=asyncio.Lock()
        )
        async for run in runs:
            yield run

    async def aget_evaluation_results(self) -> AsyncIterator[EvaluationResults]:
        if self._evaluation_results is None:
            async for _ in await self.aget_examples():
                yield {"results": []}
        else:
            self._evaluation_results, evaluation_results = aitertools.atee(
                aitertools.ensure_async_iterator(self._evaluation_results),
                2,
                lock=asyncio.Lock(),
            )
            async for result in evaluation_results:
                yield result

    async def astart(self) -> _AsyncExperimentManager:
        try:
            first_example = await aitertools.py_anext(await self.aget_examples())
        except StopAsyncIteration:
            raise ValueError(
                "No examples found in the dataset. "
                "Please ensure the data provided to aevaluate is not empty."
            )
        if not first_example:
            raise ValueError(
                "No examples found in the dataset."
                "Please ensure the data provided to aevaluate is not empty."
            )
        project = self._get_project(first_example) if self._upload_results else None
        self._print_experiment_start(project, first_example)
        self._metadata["num_repetitions"] = self._num_repetitions
        return self._copy(
            await self.aget_examples(),
            experiment=project,
        )

    def _get_example_with_readers(self, example: schemas.Example) -> schemas.Example:
        new_attachments: dict[str, schemas.AttachmentInfo] = {}
        for name, attachment in (example.attachments or {}).items():
            if (
                self._attachment_raw_data_dict is not None
                and str(example.id) + name in self._attachment_raw_data_dict
            ):
                reader = io.BytesIO(
                    self._attachment_raw_data_dict[str(example.id) + name]
                )
                new_attachments[name] = {
                    "presigned_url": attachment["presigned_url"],
                    "reader": reader,
                    "mime_type": attachment["mime_type"],
                }
            else:
                new_attachments[name] = attachment

        return schemas.Example(
            id=example.id,
            created_at=example.created_at,
            dataset_id=example.dataset_id,
            inputs=example.inputs,
            outputs=example.outputs,
            metadata=example.metadata,
            modified_at=example.modified_at,
            runs=example.runs,
            source_run_id=example.source_run_id,
            attachments=new_attachments,
            _host_url=example._host_url,
            _tenant_id=example._tenant_id,
        )

    async def awith_predictions_and_evaluators(
        self,
        target: ATARGET_T,
        evaluators: Sequence[Union[EVALUATOR_T, AEVALUATOR_T]],
        /,
        max_concurrency: Optional[int] = None,
    ) -> _AsyncExperimentManager:
        """Run predictions and evaluations in a single pipeline.

        This allows evaluators to process results as soon as they're available from
        the target function, rather than waiting for all predictions to complete first.
        """
        evaluators = _resolve_evaluators(evaluators)

        if not hasattr(self, "_evaluation_feedback_executor"):
            self._evaluation_feedback_executor = cf.ThreadPoolExecutor(max_workers=4)

        traceable_target = _ensure_async_traceable(target)

        async def process_example(example: schemas.Example):
            # Yield the coroutine to be awaited later
            pred = await _aforward(
                traceable_target,
                self._get_example_with_readers(example),
                self.experiment_name,
                self._metadata,
                self.client,
                _target_include_attachments(target),
                self._error_handling,
            )
            example, run = pred["example"], pred["run"]
            result = await self._arun_evaluators(
                evaluators,
                {
                    "run": run,
                    "example": example,
                    "evaluation_results": {"results": []},
                },
                feedback_executor=self._evaluation_feedback_executor,
            )
            return result

        async def process_examples():
            """Create a single task per example.

            That task is to run the target function and all the evaluators
            sequentially.
            """
            async for example in await self.aget_examples():
                yield process_example(example)

            await self._aend()

        # Run the per-example tasks with max-concurrency
        # This guarantees that max_concurrency is the upper limit
        # for the number of target/evaluators that can be run in parallel
        experiment_results = aitertools.aiter_with_concurrency(
            max_concurrency,
            process_examples(),
            _eager_consumption_timeout=0.001,
        )

        r1, r2, r3 = aitertools.atee(experiment_results, 3, lock=asyncio.Lock())

        return self._copy(
            (result["example"] async for result in r1),
            runs=(result["run"] async for result in r2),
            evaluation_results=(result["evaluation_results"] async for result in r3),
        )

    async def awith_predictions(
        self,
        target: ATARGET_T,
        /,
        max_concurrency: Optional[int] = None,
    ) -> _AsyncExperimentManager:
        _experiment_results = self._apredict(
            target,
            max_concurrency=max_concurrency,
            include_attachments=_target_include_attachments(target),
        )
        r1, r2 = aitertools.atee(_experiment_results, 2, lock=asyncio.Lock())
        return self._copy(
            (pred["example"] async for pred in r1),
            runs=(pred["run"] async for pred in r2),
        )

    async def awith_evaluators(
        self,
        evaluators: Sequence[Union[EVALUATOR_T, AEVALUATOR_T]],
        *,
        max_concurrency: Optional[int] = None,
    ) -> _AsyncExperimentManager:
        evaluators = _resolve_evaluators(evaluators)
        experiment_results = self._ascore(evaluators, max_concurrency=max_concurrency)
        r1, r2, r3 = aitertools.atee(experiment_results, 3, lock=asyncio.Lock())
        return self._copy(
            (result["example"] async for result in r1),
            runs=(result["run"] async for result in r2),
            evaluation_results=(result["evaluation_results"] async for result in r3),
        )

    async def awith_summary_evaluators(
        self,
        summary_evaluators: Sequence[SUMMARY_EVALUATOR_T],
    ) -> _AsyncExperimentManager:
        wrapped_evaluators = _wrap_summary_evaluators(summary_evaluators)
        aggregate_feedback_gen = self._aapply_summary_evaluators(wrapped_evaluators)
        return self._copy(
            await self.aget_examples(),
            runs=self.aget_runs(),
            summary_results=aggregate_feedback_gen,
        )

    async def aget_results(self) -> AsyncIterator[ExperimentResultRow]:
        async for run, example, evaluation_results in aitertools.async_zip(
            self.aget_runs(), await self.aget_examples(), self.aget_evaluation_results()
        ):
            yield ExperimentResultRow(
                run=run,
                example=example,
                evaluation_results=evaluation_results,
            )

    async def aget_summary_scores(self) -> dict[str, list[dict]]:
        if self._summary_results is None:
            return {"results": []}
        return {
            "results": [
                res  # type: ignore[misc]
                async for results in self._summary_results
                for res in results["results"]
            ]
        }

    ## Private methods

    async def _apredict(
        self,
        target: ATARGET_T,
        /,
        max_concurrency: Optional[int] = None,
        include_attachments: bool = False,
    ) -> AsyncIterator[_ForwardResults]:
        fn = _ensure_async_traceable(target)

        async def predict_all():
            async for example in await self.aget_examples():
                # Yield the coroutine to be awaited later
                yield _aforward(
                    fn,
                    self._get_example_with_readers(example),
                    self.experiment_name,
                    self._metadata,
                    self.client,
                    include_attachments,
                    self._error_handling,
                )

        async for result in aitertools.aiter_with_concurrency(
            max_concurrency, predict_all(), _eager_consumption_timeout=0.001
        ):
            yield result

        await self._aend()

    async def _ascore(
        self,
        evaluators: Sequence[RunEvaluator],
        max_concurrency: Optional[int] = None,
    ) -> AsyncIterator[ExperimentResultRow]:
        with cf.ThreadPoolExecutor(max_workers=4) as feedback_executor:

            async def score_all():
                async for current_results in self.aget_results():
                    # Yield the coroutine to be awaited later in aiter_with_concurrency
                    yield self._arun_evaluators(
                        evaluators, current_results, feedback_executor=feedback_executor
                    )

            async for result in aitertools.aiter_with_concurrency(
                max_concurrency, score_all(), _eager_consumption_timeout=0.001
            ):
                yield result

    async def _arun_evaluators(
        self,
        evaluators: Sequence[RunEvaluator],
        current_results: ExperimentResultRow,
        feedback_executor: cf.ThreadPoolExecutor,
    ) -> ExperimentResultRow:
        current_context = rh.get_tracing_context()
        metadata = {
            **(current_context["metadata"] or {}),
            **{"experiment": self.experiment_name},
        }
        with rh.tracing_context(
            **{
                **current_context,
                "project_name": "evaluators",
                "metadata": metadata,
                "enabled": "local" if not self._upload_results else True,
                "client": self.client,
            }
        ):
            run = current_results["run"]
            example = current_results["example"]
            eval_results = current_results["evaluation_results"]

            async def _run_single_evaluator(evaluator: RunEvaluator):
                evaluator_run_id = uuid.uuid4()
                try:
                    evaluator_response = await evaluator.aevaluate_run(  # type: ignore[call-arg]
                        run=run,
                        example=self._get_example_with_readers(example),
                        evaluator_run_id=evaluator_run_id,
                    )
                    selected_results = self.client._select_eval_results(
                        evaluator_response
                    )

                    if self._upload_results:
                        self.client._log_evaluation_feedback(
                            evaluator_response, run=run, _executor=feedback_executor
                        )
                    return selected_results
                except Exception as e:
                    try:
                        feedback_keys = _extract_feedback_keys(evaluator)

                        error_response = EvaluationResults(
                            results=[
                                EvaluationResult(
                                    key=key,
                                    source_run_id=evaluator_run_id,
                                    comment=repr(e),
                                    extra={"error": True},
                                )
                                for key in feedback_keys
                            ]
                        )
                        selected_results = self.client._select_eval_results(
                            error_response
                        )
                        if self._upload_results:
                            self.client._log_evaluation_feedback(
                                error_response, run=run, _executor=feedback_executor
                            )
                        return selected_results
                    except Exception as e2:
                        logger.debug(f"Error parsing feedback keys: {e2}")
                        pass
                    logger.error(
                        f"Error running evaluator {repr(evaluator)} on"
                        f" run {run.id}: {repr(e)}",
                        exc_info=True,
                    )

            all_results = []
            for evaluator in evaluators:
                all_results.append(await _run_single_evaluator(evaluator))

            for result in all_results:
                if result is not None:
                    eval_results["results"].extend(result)
            return ExperimentResultRow(
                run=run,
                example=example,
                evaluation_results=eval_results,
            )

    async def _aapply_summary_evaluators(
        self, summary_evaluators: Sequence[SUMMARY_EVALUATOR_T]
    ) -> AsyncIterator[EvaluationResults]:
        runs, examples = [], []
        async_examples = aitertools.ensure_async_iterator(await self.aget_examples())
        async for run, example in aitertools.async_zip(
            self.aget_runs(), async_examples
        ):
            runs.append(run)
            examples.append(example)
        aggregate_feedback = []
        project_id = self._get_experiment().id if self._upload_results else None
        current_context = rh.get_tracing_context()
        metadata = {
            **(current_context["metadata"] or {}),
            **{
                "experiment": self.experiment_name,
                "experiment_id": project_id,
            },
        }
        with rh.tracing_context(
            **{
                **current_context,
                "project_name": "evaluators",
                "metadata": metadata,
                "enabled": "local" if not self._upload_results else True,
                "client": self.client,
            }
        ):
            for evaluator in summary_evaluators:
                try:
                    summary_eval_result = evaluator(runs, examples)
                    flattened_results = self.client._select_eval_results(
                        summary_eval_result,
                        fn_name=evaluator.__name__,
                    )
                    aggregate_feedback.extend(flattened_results)
                    if self._upload_results:
                        for result in flattened_results:
                            feedback = result.dict(exclude={"target_run_id"})
                            evaluator_info = feedback.pop("evaluator_info", None)
                            await aitertools.aio_to_thread(
                                self.client.create_feedback,
                                **feedback,
                                run_id=None,
                                project_id=project_id,
                                source_info=evaluator_info,
                            )
                except Exception as e:
                    logger.error(
                        f"Error running summary evaluator {repr(evaluator)}: {e}",
                        exc_info=True,
                    )
        yield {"results": aggregate_feedback}

    async def _get_dataset_version(self) -> Optional[str]:
        modified_at = []
        async for example in await self.aget_examples():
            if example.modified_at:
                # Should always be defined in practice when fetched,
                # but the typing permits None
                modified_at.append(example.modified_at)

        max_modified_at = max(modified_at) if modified_at else None
        return max_modified_at.isoformat() if max_modified_at else None

    async def _get_dataset_splits(self) -> Optional[list[str]]:
        splits = set()
        async for example in await self.aget_examples():
            if (
                example.metadata
                and example.metadata.get("dataset_split")
                and isinstance(example.metadata["dataset_split"], list)
            ):
                for split in example.metadata["dataset_split"]:
                    if isinstance(split, str):
                        splits.add(split)
            else:
                splits.add("base")

        return list(splits)

    async def _aend(self) -> None:
        if not self._upload_results:
            return
        experiment = self._experiment
        if experiment is None:
            raise ValueError("Experiment not started yet.")

        project_metadata = self._get_experiment_metadata()
        project_metadata["dataset_version"] = await self._get_dataset_version()
        project_metadata["dataset_splits"] = await self._get_dataset_splits()
        self.client.update_project(
            experiment.id,
            metadata={
                **experiment.metadata,
                **project_metadata,
            },
        )

    def _copy(self, *args: Any, **kwargs: Any) -> _AsyncExperimentManager:
        default_args = (self._data,)
        default_kwargs = {
            "experiment": self._experiment,
            "metadata": self._metadata,
            "runs": self._runs,
            "client": self.client,
            "evaluation_results": self._evaluation_results,
            "summary_results": self._summary_results,
            "include_attachments": self._include_attachments,
            "reuse_attachments": self._reuse_attachments,
            "upload_results": self._upload_results,
            "attachment_raw_data_dict": self._attachment_raw_data_dict,
            "error_handling": self._error_handling,
        }
        full_args = list(args) + list(default_args[len(args) :])
        full_kwargs = {**default_kwargs, **kwargs}
        return self.__class__(*full_args, **full_kwargs)


class AsyncExperimentResults:
    def __init__(
        self,
        experiment_manager: _AsyncExperimentManager,
    ):
        self._manager = experiment_manager
        self._results: list[ExperimentResultRow] = []
        self._lock = asyncio.Lock()
        self._task = asyncio.create_task(self._process_data(self._manager))
        self._processed_count = 0

    @property
    def experiment_name(self) -> str:
        return self._manager.experiment_name

    def __aiter__(self) -> AsyncIterator[ExperimentResultRow]:
        return self

    async def __anext__(self) -> ExperimentResultRow:
        async def _wait_until_index(index: int) -> None:
            while self._processed_count < index:
                await asyncio.sleep(0.05)

        while True:
            async with self._lock:
                if self._processed_count < len(self._results):
                    result = self._results[self._processed_count]
                    self._processed_count += 1
                    return result
                elif self._task.done():
                    raise StopAsyncIteration

            await asyncio.shield(
                asyncio.wait_for(_wait_until_index(len(self._results)), timeout=None)
            )

    async def _process_data(self, manager: _AsyncExperimentManager) -> None:
        tqdm = _load_tqdm()
        async for item in tqdm(manager.aget_results()):
            async with self._lock:
                self._results.append(item)
        summary_scores = await manager.aget_summary_scores()
        async with self._lock:
            self._summary_results = summary_scores

    def to_pandas(
        self, start: Optional[int] = 0, end: Optional[int] = None
    ) -> DataFrame:
        return _to_pandas(self._results, start=start, end=end)

    def _repr_html_(self) -> str:
        import importlib.util

        if self._results and importlib.util.find_spec("pandas"):
            df = self.to_pandas(0, 5)
            return df._repr_html_()  # type: ignore[operator]
        else:
            return self.__repr__()

    def __len__(self) -> int:
        return len(self._results)

    def __repr__(self) -> str:
        return f"<AsyncExperimentResults {self.experiment_name}>"

    async def wait(self) -> None:
        await self._task


async def _aforward(
    fn: rh.SupportsLangsmithExtra[[dict], Awaitable],
    example: schemas.Example,
    experiment_name: str,
    metadata: dict,
    client: langsmith.Client,
    include_attachments: bool = False,
    error_handling: Literal["log", "ignore"] = "log",
) -> _ForwardResults:
    run: Optional[schemas.RunBase] = None

    def _get_run(r: run_trees.RunTree) -> None:
        nonlocal run
        run = r

    def _set_reference_example_id(r: rt.RunTree) -> None:
        r.reference_example_id = example.id

    langsmith_extra = rh.LangSmithExtra(
        on_end=_get_run,
        project_name=experiment_name,
        metadata={
            **metadata,
            "example_version": (example.modified_at or example.created_at).isoformat(),
        },
        client=client,
    )
    if error_handling == "log":
        langsmith_extra["reference_example_id"] = example.id
    elif error_handling == "ignore":
        langsmith_extra["_on_success"] = _set_reference_example_id
    else:
        raise ValueError(f"Unrecognized error_handling value: {error_handling=}")

    with rh.tracing_context(enabled=True):
        try:
            arg_names = _get_target_args(fn)
            args = [getattr(example, argn) for argn in arg_names]
            await fn(*args, langsmith_extra=langsmith_extra)
        except Exception as e:
            logger.error(
                f"Error running target function: {e}", exc_info=True, stacklevel=1
            )
        return _ForwardResults(
            run=cast(schemas.Run, run),
            example=example,
        )


def _ensure_async_traceable(
    target: ATARGET_T,
) -> rh.SupportsLangsmithExtra[[dict], Awaitable]:
    if not asyncio.iscoroutinefunction(target) and not _is_langchain_runnable(target):
        if callable(target):
            raise ValueError(
                "Target must be an async function. For sync functions, use evaluate."
                " Example usage:\n\n"
                "async def predict(inputs: dict) -> dict:\n"
                "    # do work, like chain.invoke(inputs)\n"
                "    return {...}\n"
                "await aevaluate(predict, ...)"
            )
        else:
            raise ValueError(
                "Target must be a callable async function. "
                "Received a non-callable object. Example usage:\n\n"
                "async def predict(inputs: dict) -> dict:\n"
                "    # do work, like chain.invoke(inputs)\n"
                "    return {...}\n"
                "await aevaluate(predict, ...)"
            )
    if rh.is_traceable_function(target):
        return target  # type: ignore
    else:
        if _is_langchain_runnable(target):
            target = target.ainvoke  # type: ignore[union-attr]
        return rh.traceable(name="AsyncTarget")(target)  # type: ignore[arg-type]


def _aresolve_data(
    data: Union[DATA_T, AsyncIterable[schemas.Example]],
    *,
    client: langsmith.Client,
    include_attachments: bool = False,
) -> AsyncIterator[schemas.Example]:
    """Return the examples for the given dataset."""
    if isinstance(data, AsyncIterable):
        return aitertools.ensure_async_iterator(data)
    return aitertools.ensure_async_iterator(
        _resolve_data(data, client=client, include_attachments=include_attachments)
    )


T = TypeVar("T")


async def async_chain_from_iterable(
    iterable: Iterable[AsyncIterable[T]],
) -> AsyncIterator[T]:
    """Chain multiple async iterables."""
    for sub_iterable in iterable:
        async for item in sub_iterable:
            yield item


async def async_iter_from_list(
    examples: list[schemas.Example],
) -> AsyncIterable[schemas.Example]:
    """Convert a list of examples to an async iterable."""
    for example in examples:
        yield example
