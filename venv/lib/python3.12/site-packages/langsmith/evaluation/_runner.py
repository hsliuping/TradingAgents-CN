"""V2 Evaluation Interface."""

from __future__ import annotations

import ast
import collections
import concurrent.futures as cf
import functools
import inspect
import io
import itertools
import logging
import pathlib
import queue
import random
import textwrap
import threading
import uuid
from collections.abc import Awaitable, Generator, Iterable, Iterator, Sequence
from contextvars import copy_context
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

from typing_extensions import TypedDict, overload

import langsmith
from langsmith import env as ls_env
from langsmith import run_helpers as rh
from langsmith import run_trees as rt
from langsmith import schemas
from langsmith import utils as ls_utils
from langsmith._internal._beta_decorator import _warn_once
from langsmith.evaluation.evaluator import (
    SUMMARY_EVALUATOR_T,
    ComparisonEvaluationResult,
    DynamicComparisonRunEvaluator,
    DynamicRunEvaluator,
    EvaluationResult,
    EvaluationResults,
    RunEvaluator,
    _normalize_summary_evaluator,
    comparison_evaluator,
    run_evaluator,
)
from langsmith.evaluation.integrations import LangChainStringEvaluator

if TYPE_CHECKING:
    import pandas as pd
    from langchain_core.runnables import Runnable

    DataFrame = pd.DataFrame
else:
    DataFrame = Any
logger = logging.getLogger(__name__)

TARGET_T = Union[Callable[[dict], dict], Callable[[dict, dict], dict]]
# Data format: dataset-name, dataset_id, or examples
DATA_T = Union[str, uuid.UUID, Iterable[schemas.Example], schemas.Dataset]
# Summary evaluator runs over the whole dataset
# and reports aggregate metric(s)
# Row-level evaluator
EVALUATOR_T = Union[
    RunEvaluator,
    Callable[
        [schemas.Run, Optional[schemas.Example]],
        Union[EvaluationResult, EvaluationResults],
    ],
    Callable[..., Union[dict, EvaluationResults, EvaluationResult]],
]
AEVALUATOR_T = Union[
    Callable[
        [schemas.Run, Optional[schemas.Example]],
        Awaitable[Union[EvaluationResult, EvaluationResults]],
    ],
]
EXPERIMENT_T = Union[str, uuid.UUID, schemas.TracerSession]


@overload
def evaluate(
    target: Union[TARGET_T, Runnable, EXPERIMENT_T],
    /,
    data: Optional[DATA_T] = None,
    evaluators: Optional[Sequence[EVALUATOR_T]] = None,
    summary_evaluators: Optional[Sequence[SUMMARY_EVALUATOR_T]] = None,
    metadata: Optional[dict] = None,
    experiment_prefix: Optional[str] = None,
    description: Optional[str] = None,
    max_concurrency: Optional[int] = 0,
    num_repetitions: int = 1,
    client: Optional[langsmith.Client] = None,
    blocking: bool = True,
    experiment: Optional[EXPERIMENT_T] = None,
    upload_results: bool = True,
    **kwargs: Any,
) -> ExperimentResults: ...


@overload
def evaluate(
    target: Union[tuple[EXPERIMENT_T, EXPERIMENT_T]],
    /,
    data: Optional[DATA_T] = None,
    evaluators: Optional[Sequence[COMPARATIVE_EVALUATOR_T]] = None,
    summary_evaluators: Optional[Sequence[SUMMARY_EVALUATOR_T]] = None,
    metadata: Optional[dict] = None,
    experiment_prefix: Optional[str] = None,
    description: Optional[str] = None,
    max_concurrency: Optional[int] = 0,
    num_repetitions: int = 1,
    client: Optional[langsmith.Client] = None,
    blocking: bool = True,
    experiment: Optional[EXPERIMENT_T] = None,
    upload_results: bool = True,
    **kwargs: Any,
) -> ComparativeExperimentResults: ...


def evaluate(
    target: Union[TARGET_T, Runnable, EXPERIMENT_T, tuple[EXPERIMENT_T, EXPERIMENT_T]],
    /,
    data: Optional[DATA_T] = None,
    evaluators: Optional[
        Union[Sequence[EVALUATOR_T], Sequence[COMPARATIVE_EVALUATOR_T]]
    ] = None,
    summary_evaluators: Optional[Sequence[SUMMARY_EVALUATOR_T]] = None,
    metadata: Optional[dict] = None,
    experiment_prefix: Optional[str] = None,
    description: Optional[str] = None,
    max_concurrency: Optional[int] = 0,
    num_repetitions: int = 1,
    client: Optional[langsmith.Client] = None,
    blocking: bool = True,
    experiment: Optional[EXPERIMENT_T] = None,
    upload_results: bool = True,
    error_handling: Literal["log", "ignore"] = "log",
    **kwargs: Any,
) -> Union[ExperimentResults, ComparativeExperimentResults]:
    r"""Evaluate a target system on a given dataset.

    Args:
        target (TARGET_T | Runnable | EXPERIMENT_T | Tuple[EXPERIMENT_T, EXPERIMENT_T]):
            The target system or experiment(s) to evaluate. Can be a function
            that takes a dict and returns a dict, a langchain Runnable, an
            existing experiment ID, or a two-tuple of experiment IDs.
        data (DATA_T): The dataset to evaluate on. Can be a dataset name, a list of
            examples, or a generator of examples.
        evaluators (Sequence[EVALUATOR_T] | Sequence[COMPARATIVE_EVALUATOR_T] | None):
            A list of evaluators to run on each example. The evaluator signature
            depends on the target type. Default to None.
        summary_evaluators (Sequence[SUMMARY_EVALUATOR_T] | None): A list of summary
            evaluators to run on the entire dataset. Should not be specified if
            comparing two existing experiments. Defaults to None.
        metadata (dict | None): Metadata to attach to the experiment.
            Defaults to None.
        experiment_prefix (str | None): A prefix to provide for your experiment name.
            Defaults to None.
        description (str | None): A free-form text description for the experiment.
        max_concurrency (int | None): The maximum number of concurrent
            evaluations to run. If None then no limit is set. If 0 then no concurrency.
            Defaults to 0.
        client (langsmith.Client | None): The LangSmith client to use.
            Defaults to None.
        blocking (bool): Whether to block until the evaluation is complete.
            Defaults to True.
        num_repetitions (int): The number of times to run the evaluation.
            Each item in the dataset will be run and evaluated this many times.
            Defaults to 1.
        experiment (schemas.TracerSession | None): An existing experiment to
            extend. If provided, experiment_prefix is ignored. For advanced
            usage only. Should not be specified if target is an existing experiment or
            two-tuple fo experiments.
        load_nested (bool): Whether to load all child runs for the experiment.
            Default is to only load the top-level root runs. Should only be specified
            when target is an existing experiment or two-tuple of experiments.
        randomize_order (bool): Whether to randomize the order of the outputs for each
            evaluation. Default is False. Should only be specified when target is a
            two-tuple of existing experiments.
        error_handling (str, default="log"): How to handle individual run errors. 'log'
            will trace the runs with the error message as part of the experiment,
            'ignore' will not count the run as part of the experiment at all.

    Returns:
        ExperimentResults: If target is a function, Runnable, or existing experiment.
        ComparativeExperimentResults: If target is a two-tuple of existing experiments.

    Examples:
        Prepare the dataset:

        >>> from typing import Sequence
        >>> from langsmith import Client
        >>> from langsmith.evaluation import evaluate
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
        >>> def predict(inputs: dict) -> dict:
        ...     # This can be any function or just an API call to your app.
        ...     return {"output": "Yes"}
        >>> results = evaluate(
        ...     predict,
        ...     data=dataset_name,
        ...     evaluators=[accuracy],
        ...     summary_evaluators=[precision],
        ...     experiment_prefix="My Experiment",
        ...     description="Evaluating the accuracy of a simple prediction model.",
        ...     metadata={
        ...         "my-prompt-version": "abcd-1234",
        ...     },
        ... )  # doctest: +ELLIPSIS
        View the evaluation results for experiment:...

        Evaluating over only a subset of the examples

        >>> experiment_name = results.experiment_name
        >>> examples = client.list_examples(dataset_name=dataset_name, limit=5)
        >>> results = evaluate(
        ...     predict,
        ...     data=examples,
        ...     evaluators=[accuracy],
        ...     summary_evaluators=[precision],
        ...     experiment_prefix="My Experiment",
        ...     description="Just testing a subset synchronously.",
        ... )  # doctest: +ELLIPSIS
        View the evaluation results for experiment:...

        Streaming each prediction to more easily + eagerly debug.

        >>> results = evaluate(
        ...     predict,
        ...     data=dataset_name,
        ...     evaluators=[accuracy],
        ...     summary_evaluators=[precision],
        ...     description="I don't even have to block!",
        ...     blocking=False,
        ... )  # doctest: +ELLIPSIS
        View the evaluation results for experiment:...
        >>> for i, result in enumerate(results):  # doctest: +ELLIPSIS
        ...     pass

        Using the `evaluate` API with an off-the-shelf LangChain evaluator:

        >>> from langsmith.evaluation import LangChainStringEvaluator
        >>> from langchain_openai import ChatOpenAI
        >>> def prepare_criteria_data(run: Run, example: Example):
        ...     return {
        ...         "prediction": run.outputs["output"],
        ...         "reference": example.outputs["answer"],
        ...         "input": str(example.inputs),
        ...     }
        >>> results = evaluate(
        ...     predict,
        ...     data=dataset_name,
        ...     evaluators=[
        ...         accuracy,
        ...         LangChainStringEvaluator("embedding_distance"),
        ...         LangChainStringEvaluator(
        ...             "labeled_criteria",
        ...             config={
        ...                 "criteria": {
        ...                     "usefulness": "The prediction is useful if it is correct"
        ...                     " and/or asks a useful followup question."
        ...                 },
        ...                 "llm": ChatOpenAI(model="gpt-4o"),
        ...             },
        ...             prepare_data=prepare_criteria_data,
        ...         ),
        ...     ],
        ...     description="Evaluating with off-the-shelf LangChain evaluators.",
        ...     summary_evaluators=[precision],
        ... )  # doctest: +ELLIPSIS
        View the evaluation results for experiment:...

        Evaluating a LangChain object:

        >>> from langchain_core.runnables import chain as as_runnable
        >>> @as_runnable
        ... def nested_predict(inputs):
        ...     return {"output": "Yes"}
        >>> @as_runnable
        ... def lc_predict(inputs):
        ...     return nested_predict.invoke(inputs)
        >>> results = evaluate(
        ...     lc_predict.invoke,
        ...     data=dataset_name,
        ...     evaluators=[accuracy],
        ...     description="This time we're evaluating a LangChain object.",
        ...     summary_evaluators=[precision],
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
        return evaluate_existing(
            target,
            evaluators=cast(Optional[Sequence[EVALUATOR_T]], evaluators),
            summary_evaluators=summary_evaluators,
            metadata=metadata,
            max_concurrency=max_concurrency,
            client=client,
            blocking=blocking,
            **kwargs,
        )
    elif isinstance(target, (list, tuple)):
        invalid_args = {
            "num_repetitions": num_repetitions > 1,
            "experiment": bool(experiment),
            "upload_results": not upload_results,
            "summary_evaluators": bool(summary_evaluators),
            "data": bool(data),
        }
        if len(target) != 2 or not all(
            isinstance(t, (str, uuid.UUID, schemas.TracerSession)) for t in target
        ):
            msg = (
                "Received invalid target. If a tuple is specified it must have length "
                "2 and each element should by the ID or schemas.TracerSession of an "
                f"existing experiment. Received {target=}"
            )
            raise ValueError(msg)
        elif any(invalid_args.values()):
            msg = (
                f"Received invalid arguments. "
                f"{tuple(k for k, v in invalid_args.items() if v)} should not be "
                f"specified when target is two existing experiments."
            )
            raise ValueError(msg)
        if max_concurrency is not None:
            kwargs["max_concurrency"] = max_concurrency
        target_ids = [t if isinstance(t, (str, uuid.UUID)) else t.id for t in target]
        logger.debug(
            f"Running pairwise evaluation over existing experiments {target_ids}..."
        )
        return evaluate_comparative(
            target,
            evaluators=cast(Sequence[COMPARATIVE_EVALUATOR_T], evaluators or ()),
            experiment_prefix=experiment_prefix,
            description=description,
            client=client,
            metadata=metadata,
            **kwargs,
        )
    elif kwargs:
        msg = (
            f"Received unsupported arguments {kwargs}. These arguments are not "
            f"supported when creating a new experiment."
        )
        raise ValueError(msg)
    elif not data:
        msg = "Must specify 'data' when running evaluations over a target function."
        raise ValueError(msg)
    elif callable(target) and rh.is_async(target):
        msg = (
            "Async functions are not supported by `evaluate`. "
            "Please use `aevaluate` instead:\n\n"
            "from langsmith import aevaluate\n\n"
            "await aevaluate(\n"
            "    async_target_function,\n"
            "    data=data,\n"
            "    evaluators=evaluators,\n"
            "    # ... other parameters\n"
            ")"
        )
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
        return _evaluate(
            target,
            data=data,
            evaluators=cast(Optional[Sequence[EVALUATOR_T]], evaluators),
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


def evaluate_existing(
    experiment: Union[str, uuid.UUID, schemas.TracerSession],
    /,
    evaluators: Optional[Sequence[EVALUATOR_T]] = None,
    summary_evaluators: Optional[Sequence[SUMMARY_EVALUATOR_T]] = None,
    metadata: Optional[dict] = None,
    max_concurrency: Optional[int] = 0,
    client: Optional[langsmith.Client] = None,
    load_nested: bool = False,
    blocking: bool = True,
) -> ExperimentResults:
    r"""Evaluate existing experiment runs.

    Args:
        experiment (Union[str, uuid.UUID]): The identifier of the experiment to evaluate.
        data (DATA_T): The data to use for evaluation.
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
        ExperimentResults: The evaluation results.

    Environment:
        - LANGSMITH_TEST_CACHE: If set, API calls will be cached to disk to save time and
            cost during testing. Recommended to commit the cache files to your repository
            for faster CI/CD runs.
            Requires the 'langsmith[vcr]' package to be installed.

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

        >>> import uuid
        >>> from langsmith import Client
        >>> from langsmith.evaluation import evaluate, evaluate_existing
        >>> client = Client()
        >>> dataset_name = "__doctest_evaluate_existing_" + uuid.uuid4().hex[:8]
        >>> dataset = client.create_dataset(dataset_name)
        >>> example = client.create_example(
        ...     inputs={"question": "What is 2+2?"},
        ...     outputs={"answer": "4"},
        ...     dataset_id=dataset.id
        ... )
        >>> def predict(inputs: dict) -> dict:
        ...     return {"output": "4"}
        >>> # First run inference on the dataset
        ... results = evaluate(
        ...     predict,
        ...     data=dataset_name,
        ...     experiment_prefix="doctest_experiment"
        ... )  # doctest: +ELLIPSIS
        View the evaluation results for experiment:...
        >>> experiment_id = results.experiment_name
        >>> # Wait for the experiment to be fully processed and check if we have results
        >>> len(results) > 0
        True
        >>> import time
        >>> time.sleep(2)
        >>> results = evaluate_existing(
        ...     experiment_id,
        ...     evaluators=[accuracy],
        ...     summary_evaluators=[precision],
        ... )  # doctest: +ELLIPSIS
        View the evaluation results for experiment:...
        >>> client.delete_dataset(dataset_id=dataset.id)
    """  # noqa: E501
    client = client or rt.get_cached_client(timeout_ms=(20_000, 90_001))
    project = _load_experiment(experiment, client)
    runs = _load_traces(experiment, client, load_nested=load_nested)
    data_map = _load_examples_map(client, project)
    data = [data_map[cast(uuid.UUID, run.reference_example_id)] for run in runs]
    return _evaluate(
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


class ExperimentResultRow(TypedDict):
    run: schemas.Run
    example: schemas.Example
    evaluation_results: EvaluationResults


class ExperimentResults:
    """Represents the results of an evaluate() call.

    This class provides an iterator interface to iterate over the experiment results
    as they become available. It also provides methods to access the experiment name,
    the number of results, and to wait for the results to be processed.

    Methods:
        experiment_name() -> str: Returns the name of the experiment.
        wait() -> None: Waits for the experiment data to be processed.
    """

    def __init__(self, experiment_manager: _ExperimentManager, blocking: bool = True):
        self._manager = experiment_manager
        self._results: list[ExperimentResultRow] = []
        self._queue: queue.Queue[ExperimentResultRow] = queue.Queue()
        self._processing_complete = threading.Event()
        if not blocking:
            self._thread: Optional[threading.Thread] = threading.Thread(
                target=self._process_data
            )
            self._thread.start()
        else:
            self._thread = None
            self._process_data()

    @property
    def experiment_name(self) -> str:
        return self._manager.experiment_name

    def __iter__(self) -> Iterator[ExperimentResultRow]:
        ix = 0
        while (
            not self._processing_complete.is_set()
            or not self._queue.empty()
            or ix < len(self._results)
        ):
            try:
                if ix < len(self._results):
                    yield self._results[ix]
                    ix += 1
                else:
                    self._queue.get(block=True, timeout=0.1)
            except queue.Empty:
                continue

    def _process_data(self) -> None:
        tqdm = _load_tqdm()
        results = self._manager.get_results()
        for item in tqdm(results):
            self._queue.put(item)
            self._results.append(item)

        summary_scores = self._manager.get_summary_scores()
        self._summary_results = summary_scores

        self._processing_complete.set()

    def __len__(self) -> int:
        return len(self._results)

    def to_pandas(
        self, start: Optional[int] = 0, end: Optional[int] = None
    ) -> DataFrame:
        return _to_pandas(self._results, start=start, end=end)

    def _repr_html_(self) -> str:
        import importlib.util

        if self._results and importlib.util.find_spec("pandas"):
            df = self.to_pandas()
            return df._repr_html_()  # type: ignore[operator]
        else:
            return self.__repr__()

    def __repr__(self) -> str:
        return f"<ExperimentResults {self.experiment_name}>"

    def wait(self) -> None:
        """Wait for the evaluation runner to complete.

        This method blocks the current thread until the evaluation runner has
        finished its execution.
        """
        if self._thread:
            self._thread.join()


## Public API for Comparison Experiments

# Row-level evaluator
COMPARATIVE_EVALUATOR_T = Callable[
    [Sequence[schemas.Run], Optional[schemas.Example]],
    Union[
        Union[ComparisonEvaluationResult, dict],
        Awaitable[Union[ComparisonEvaluationResult, dict]],
    ],
]


def evaluate_comparative(
    experiments: tuple[EXPERIMENT_T, EXPERIMENT_T],
    /,
    evaluators: Sequence[COMPARATIVE_EVALUATOR_T],
    experiment_prefix: Optional[str] = None,
    description: Optional[str] = None,
    max_concurrency: int = 5,
    client: Optional[langsmith.Client] = None,
    metadata: Optional[dict] = None,
    load_nested: bool = False,
    randomize_order: bool = False,
) -> ComparativeExperimentResults:
    r"""Evaluate existing experiment runs against each other.

    This lets you use pairwise preference scoring to generate more
    reliable feedback in your experiments.

    Args:
        experiments (Tuple[Union[str, uuid.UUID], Union[str, uuid.UUID]]):
            The identifiers of the experiments to compare.
        evaluators (Sequence[COMPARATIVE_EVALUATOR_T]):
            A list of evaluators to run on each example.
        experiment_prefix (Optional[str]): A prefix to provide for your experiment name.
            Defaults to None.
        description (Optional[str]): A free-form text description for the experiment.
        max_concurrency (int): The maximum number of concurrent evaluations to run.
            Defaults to 5.
        client (Optional[langsmith.Client]): The LangSmith client to use.
            Defaults to None.
        metadata (Optional[dict]): Metadata to attach to the experiment.
            Defaults to None.
        load_nested (bool): Whether to load all child runs for the experiment.
            Default is to only load the top-level root runs.
        randomize_order (bool): Whether to randomize the order of the outputs for each evaluation.
            Default is False.

    Returns:
        ComparativeExperimentResults: The results of the comparative evaluation.

    Examples:
        Suppose you want to compare two prompts to see which one is more effective.
        You would first prepare your dataset:

        >>> from typing import Sequence
        >>> from langsmith import Client
        >>> from langsmith.evaluation import evaluate
        >>> from langsmith.schemas import Example, Run
        >>> client = Client()
        >>> dataset = client.clone_public_dataset(
        ...     "https://smith.langchain.com/public/419dcab2-1d66-4b94-8901-0357ead390df/d"
        ... )
        >>> dataset_name = "Evaluate Examples"

        Then you would run your different prompts:
        >>> import functools
        >>> import openai
        >>> from langsmith.evaluation import evaluate
        >>> from langsmith.wrappers import wrap_openai
        >>> oai_client = openai.Client()
        >>> wrapped_client = wrap_openai(oai_client)
        >>> prompt_1 = "You are a helpful assistant."
        >>> prompt_2 = "You are an exceedingly helpful assistant."
        >>> def predict(inputs: dict, prompt: str) -> dict:
        ...     completion = wrapped_client.chat.completions.create(
        ...         model="gpt-4o-mini",
        ...         messages=[
        ...             {"role": "system", "content": prompt},
        ...             {
        ...                 "role": "user",
        ...                 "content": f"Context: {inputs['context']}"
        ...                 f"\n\ninputs['question']",
        ...             },
        ...         ],
        ...     )
        ...     return {"output": completion.choices[0].message.content}
        >>> results_1 = evaluate(
        ...     functools.partial(predict, prompt=prompt_1),
        ...     data=dataset_name,
        ...     description="Evaluating our basic system prompt.",
        ...     blocking=False,  # Run these experiments in parallel
        ... )  # doctest: +ELLIPSIS
        View the evaluation results for experiment:...
        >>> results_2 = evaluate(
        ...     functools.partial(predict, prompt=prompt_2),
        ...     data=dataset_name,
        ...     description="Evaluating our advanced system prompt.",
        ...     blocking=False,
        ... )  # doctest: +ELLIPSIS
        View the evaluation results for experiment:...
        >>> results_1.wait()
        >>> results_2.wait()

            Finally, you would compare the two prompts directly:
        >>> import json
        >>> from langsmith.evaluation import evaluate_comparative
        >>> from langsmith import schemas
        >>> def score_preferences(runs: list, example: schemas.Example):
        ...     assert len(runs) == 2  # Comparing 2 systems
        ...     assert isinstance(example, schemas.Example)
        ...     assert all(run.reference_example_id == example.id for run in runs)
        ...     pred_a = runs[0].outputs["output"]
        ...     pred_b = runs[1].outputs["output"]
        ...     ground_truth = example.outputs["answer"]
        ...     tools = [
        ...         {
        ...             "type": "function",
        ...             "function": {
        ...                 "name": "rank_preferences",
        ...                 "description": "Saves the prefered response ('A' or 'B')",
        ...                 "parameters": {
        ...                     "type": "object",
        ...                     "properties": {
        ...                         "reasoning": {
        ...                             "type": "string",
        ...                             "description": "The reasoning behind the choice.",
        ...                         },
        ...                         "preferred_option": {
        ...                             "type": "string",
        ...                             "enum": ["A", "B"],
        ...                             "description": "The preferred option, either 'A' or 'B'",
        ...                         },
        ...                     },
        ...                     "required": ["preferred_option"],
        ...                 },
        ...             },
        ...         }
        ...     ]
        ...     completion = openai.Client().chat.completions.create(
        ...         model="gpt-4o-mini",
        ...         messages=[
        ...             {"role": "system", "content": "Select the better response."},
        ...             {
        ...                 "role": "user",
        ...                 "content": f"Option A: {pred_a}"
        ...                 f"\n\nOption B: {pred_b}"
        ...                 f"\n\nGround Truth: {ground_truth}",
        ...             },
        ...         ],
        ...         tools=tools,
        ...         tool_choice={
        ...             "type": "function",
        ...             "function": {"name": "rank_preferences"},
        ...         },
        ...     )
        ...     tool_args = completion.choices[0].message.tool_calls[0].function.arguments
        ...     loaded_args = json.loads(tool_args)
        ...     preference = loaded_args["preferred_option"]
        ...     comment = loaded_args["reasoning"]
        ...     if preference == "A":
        ...         return {
        ...             "key": "ranked_preference",
        ...             "scores": {runs[0].id: 1, runs[1].id: 0},
        ...             "comment": comment,
        ...         }
        ...     else:
        ...         return {
        ...             "key": "ranked_preference",
        ...             "scores": {runs[0].id: 0, runs[1].id: 1},
        ...             "comment": comment,
        ...         }
        >>> def score_length_difference(runs: list, example: schemas.Example):
        ...     # Just return whichever response is longer.
        ...     # Just an example, not actually useful in real life.
        ...     assert len(runs) == 2  # Comparing 2 systems
        ...     assert isinstance(example, schemas.Example)
        ...     assert all(run.reference_example_id == example.id for run in runs)
        ...     pred_a = runs[0].outputs["output"]
        ...     pred_b = runs[1].outputs["output"]
        ...     if len(pred_a) > len(pred_b):
        ...         return {
        ...             "key": "length_difference",
        ...             "scores": {runs[0].id: 1, runs[1].id: 0},
        ...         }
        ...     else:
        ...         return {
        ...             "key": "length_difference",
        ...             "scores": {runs[0].id: 0, runs[1].id: 1},
        ...         }
        >>> results = evaluate_comparative(
        ...     [results_1.experiment_name, results_2.experiment_name],
        ...     evaluators=[score_preferences, score_length_difference],
        ...     client=client,
        ... )  # doctest: +ELLIPSIS
        View the pairwise evaluation results at:...
        >>> eval_results = list(results)
        >>> assert len(eval_results) >= 10  # doctest: +SKIP
        >>> assert all(
        ...     "feedback.ranked_preference" in r["evaluation_results"]
        ...     for r in eval_results
        ... )  # doctest: +SKIP
        >>> assert all(
        ...     "feedback.length_difference" in r["evaluation_results"]
        ...     for r in eval_results
        ... )  # doctest: +SKIP
    """  # noqa: E501
    if len(experiments) < 2:
        raise ValueError("Comparative evaluation requires at least 2 experiments.")
    if not evaluators:
        raise ValueError(
            "At least one evaluator is required for comparative evaluation."
        )
    if max_concurrency < 0:
        raise ValueError("max_concurrency must be a positive integer.")
    client = client or rt.get_cached_client()

    # TODO: Add information about comparison experiments
    projects = [_load_experiment(experiment, client) for experiment in experiments]
    ref_datasets_ = [str(p.reference_dataset_id) for p in projects]
    if not len(set(ref_datasets_)) == 1:
        raise ValueError("All experiments must have the same reference dataset.")
    experiment_ids = [p.id for p in projects]
    if experiment_prefix is None:
        experiment_names = [p.name for p in projects if p.name is not None]
        experiment_name = (
            " vs. ".join(experiment_names) + "-" + str(uuid.uuid4().hex[:4])
        )
    else:
        experiment_name = experiment_prefix + "-" + str(uuid.uuid4().hex[:8])
    comparative_experiment_id = uuid.uuid4()
    comparative_experiment = client.create_comparative_experiment(
        experiment_name,
        experiments=experiment_ids,
        description=description,
        metadata=metadata,
        id=comparative_experiment_id,
    )
    _print_comparative_experiment_start(
        cast(
            tuple[schemas.TracerSessionResult, schemas.TracerSessionResult],
            tuple(projects),
        ),
        comparative_experiment,
    )
    runs = [
        _load_traces(experiment, client, load_nested=load_nested)
        for experiment in experiments
    ]
    # Only check intersections for the experiments
    examples_intersection = None
    for runs_list in runs:
        example_ids_set = {run.reference_example_id for run in runs_list}
        if examples_intersection is None:
            examples_intersection = example_ids_set
        else:
            examples_intersection &= example_ids_set
    example_ids_nullable = (
        list(examples_intersection) if examples_intersection is not None else []
    )
    example_ids = [eid for eid in example_ids_nullable if eid is not None]
    # TODO: Warn if different dataset versions, etc. are used in the different
    # experiments. We aren't providing any training wheels here.
    batch_size = 99
    data = {}
    for i in range(0, len(example_ids), batch_size):
        example_ids_batch = example_ids[i : i + batch_size]
        for e in client.list_examples(
            dataset_id=projects[0].reference_dataset_id,
            as_of=projects[0].metadata.get("dataset_version"),
            example_ids=example_ids_batch,
        ):
            data[e.id] = e
    runs_dict: dict[uuid.UUID, list[schemas.Run]] = collections.defaultdict(list)
    for runs_list in runs:
        for run in runs_list:
            if run.reference_example_id in data:
                runs_dict[cast(uuid.UUID, run.reference_example_id)].append(run)

    comparators = [comparison_evaluator(evaluator) for evaluator in evaluators or []]
    results: dict = {}

    def evaluate_and_submit_feedback(
        runs_list: list[schemas.Run],
        example: schemas.Example,
        comparator: DynamicComparisonRunEvaluator,
        executor: cf.Executor,
    ) -> ComparisonEvaluationResult:
        feedback_group_id = uuid.uuid4()
        if randomize_order:
            random.shuffle(runs_list)
        with rh.tracing_context(project_name="evaluators", client=client):
            result = comparator.compare_runs(runs_list, example)
            if client is None:
                raise ValueError("Client is required to submit feedback.")
        comments = (
            {str(rid): result.comment for rid in result.scores}
            if isinstance(result.comment, str)
            else (result.comment or {})
        )
        for run_id, score in result.scores.items():
            executor.submit(
                client.create_feedback,
                run_id=run_id,
                key=result.key,
                score=score,
                comment=comments.get(str(run_id)),
                comparative_experiment_id=comparative_experiment.id,
                source_run_id=result.source_run_id,
                feedback_group_id=feedback_group_id,
            )
        return result

    tqdm = _load_tqdm()
    with ls_utils.ContextThreadPoolExecutor(
        max_workers=max_concurrency or 1
    ) as executor:
        futures = []
        for example_id, runs_list in tqdm(runs_dict.items()):
            results[example_id] = {"runs": runs_list}
            for comparator in comparators:
                if max_concurrency > 1:
                    future = executor.submit(
                        evaluate_and_submit_feedback,
                        runs_list,
                        data[example_id],
                        comparator,
                        executor,
                    )
                    futures.append(future)
                else:
                    result = evaluate_and_submit_feedback(
                        runs_list, data[example_id], comparator, executor
                    )
                    results[example_id][f"feedback.{result.key}"] = result
            if futures:
                cf.wait(futures)
                for future in futures:
                    result = future.result()
                    results[example_id][f"feedback.{result.key}"] = result

    return ComparativeExperimentResults(results, data)


class ComparativeExperimentResults:
    """Represents the results of an evaluate_comparative() call.

    This class provides an iterator interface to iterate over the experiment results
    as they become available. It also provides methods to access the experiment name,
    the number of results, and to wait for the results to be processed.

    Methods:
        experiment_name() -> str: Returns the name of the experiment.
        wait() -> None: Waits for the experiment data to be processed.
    """

    def __init__(
        self,
        results: dict,
        examples: Optional[dict[uuid.UUID, schemas.Example]] = None,
    ):
        self._results = results
        self._examples = examples

    def __getitem__(self, key):
        """Return the result associated with the given key."""
        return self._results[key]

    def __iter__(self):
        for key, value in self._results.items():
            yield {
                "example": self._examples[key] if self._examples else None,
                "evaluation_results": value,
            }


## Private API


def _print_comparative_experiment_start(
    experiments: tuple[schemas.TracerSession, schemas.TracerSession],
    comparative_experiment: schemas.ComparativeExperiment,
) -> None:
    url = experiments[0].url or experiments[1].url
    if url:
        project_url = url.split("?")[0]
        dataset_id = comparative_experiment.reference_dataset_id
        base_url = project_url.split("/projects/p/")[0]
        comparison_url = (
            f"{base_url}/datasets/{dataset_id}/compare?"
            f"selectedSessions={'%2C'.join([str(e.id) for e in experiments])}"
            f"&comparativeExperiment={comparative_experiment.id}"
        )
        print(  # noqa: T201
            f"View the pairwise evaluation results at:\n{comparison_url}\n\n"
        )


def _is_callable(target: Union[TARGET_T, Iterable[schemas.Run], Runnable]) -> bool:
    return callable(target) or _is_langchain_runnable(target)


def _evaluate(
    target: Union[TARGET_T, Iterable[schemas.Run], Runnable],
    /,
    data: DATA_T,
    evaluators: Optional[Sequence[EVALUATOR_T]] = None,
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
) -> ExperimentResults:
    # Initialize the experiment manager.
    client = client or rt.get_cached_client()
    runs = None if _is_callable(target) else cast(Iterable[schemas.Run], target)
    experiment_, runs = _resolve_experiment(experiment, runs, client)

    manager = _ExperimentManager(
        data,
        client=client,
        metadata=metadata,
        experiment=experiment_ or experiment_prefix,
        description=description,
        num_repetitions=num_repetitions,
        # If provided, we don't need to create a new experiment.
        runs=runs,
        # Create or resolve the experiment.
        include_attachments=_include_attachments(target, evaluators),
        upload_results=upload_results,
        error_handling=error_handling,
    ).start()
    if cache_dir := ls_utils.get_cache_dir(None):
        cache_path = pathlib.Path(cache_dir) / f"{manager.dataset_id}.yaml"
    else:
        cache_path = None
    with ls_utils.with_optional_cache(cache_path, ignore_hosts=[client.api_url]):
        if _is_callable(target):
            # Add predictions to the experiment.
            manager = manager.with_predictions(
                cast(TARGET_T, target), max_concurrency=max_concurrency
            )
        if evaluators:
            # Apply evaluators to the predictions.
            manager = manager.with_evaluators(
                evaluators, max_concurrency=max_concurrency
            )
        if summary_evaluators:
            # Apply the experiment-level summary evaluators.
            manager = manager.with_summary_evaluators(summary_evaluators)
        # Start consuming the results.
        results = ExperimentResults(manager, blocking=blocking)
        return results


def _is_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
        return True
    except ValueError:
        return False


def _load_experiment(
    project: EXPERIMENT_T, client: langsmith.Client
) -> schemas.TracerSession:
    if isinstance(project, schemas.TracerSession):
        return project
    elif isinstance(project, uuid.UUID) or _is_uuid(project):
        return client.read_project(project_id=project)
    else:
        return client.read_project(project_name=project)


def _load_traces(
    project: Union[str, uuid.UUID, schemas.TracerSession],
    client: langsmith.Client,
    load_nested: bool = False,
) -> list[schemas.Run]:
    """Load nested traces for a given project."""
    is_root = None if load_nested else True
    if isinstance(project, schemas.TracerSession):
        runs = client.list_runs(project_id=project.id, is_root=is_root)
    elif isinstance(project, uuid.UUID) or _is_uuid(project):
        runs = client.list_runs(project_id=project, is_root=is_root)
    else:
        runs = client.list_runs(project_name=project, is_root=is_root)
    if not load_nested:
        return list(runs)

    treemap: collections.defaultdict[uuid.UUID, list[schemas.Run]] = (
        collections.defaultdict(list)
    )
    results = []
    all_runs = {}
    for run in runs:
        if run.parent_run_id is not None:
            treemap[run.parent_run_id].append(run)
        else:
            results.append(run)
        all_runs[run.id] = run
    for run_id, child_runs in treemap.items():
        all_runs[run_id].child_runs = sorted(child_runs, key=lambda r: r.dotted_order)
    return results


def _load_examples_map(
    client: langsmith.Client, project: schemas.TracerSession
) -> dict[uuid.UUID, schemas.Example]:
    return {
        e.id: e
        for e in client.list_examples(
            dataset_id=project.reference_dataset_id,
            as_of=project.metadata.get("dataset_version"),
        )
    }


IT = TypeVar("IT")


def _load_tqdm() -> Callable[[IT], IT]:
    try:
        from tqdm.auto import tqdm
    except ImportError:
        return lambda x: x
    return tqdm  # type: ignore[return-value]


ET = TypeVar("ET", bound="_ExperimentManagerMixin")


class _ExperimentManagerMixin:
    def __init__(
        self,
        /,
        experiment: Optional[Union[schemas.TracerSession, str]],
        metadata: Optional[dict] = None,
        client: Optional[langsmith.Client] = None,
        description: Optional[str] = None,
    ):
        self.client = client or rt.get_cached_client()
        self._experiment: Optional[schemas.TracerSession] = None
        if experiment is None:
            self._experiment_name = _get_random_name()
        elif isinstance(experiment, str):
            self._experiment_name = experiment + "-" + str(uuid.uuid4().hex[:8])
        else:
            self._experiment_name = cast(str, experiment.name)
            self._experiment = experiment

        metadata = metadata or {}
        if not metadata.get("revision_id"):
            metadata = {
                "revision_id": ls_env.get_langchain_env_var_metadata().get(
                    "revision_id"
                ),
                **metadata,
            }
        self._metadata = metadata or {}
        self._description = description

    @property
    def experiment_name(self) -> str:
        if self._experiment_name is not None:
            return self._experiment_name
        raise ValueError(
            "Experiment name not provided, and experiment not yet started."
        )

    def _get_experiment(self) -> schemas.TracerSession:
        if self._experiment is None:
            raise ValueError("Experiment not started yet.")
        return self._experiment

    def _get_experiment_metadata(self):
        project_metadata = self._metadata or {}
        git_info = ls_env.get_git_info()
        if git_info:
            project_metadata = {
                **project_metadata,
                "git": git_info,
            }
        if self._experiment:
            project_metadata = {
                **self._experiment.metadata,
                **project_metadata,
            }
        return project_metadata

    def _create_experiment(
        self, dataset_id: uuid.UUID, metadata: dict
    ) -> schemas.TracerSession:
        # There is a chance of name collision, so we'll retry
        starting_name = self._experiment_name
        num_attempts = 10
        for _ in range(num_attempts):
            try:
                return self.client.create_project(
                    self._experiment_name,
                    description=self._description,
                    reference_dataset_id=dataset_id,
                    metadata=metadata,
                )
            except ls_utils.LangSmithConflictError:
                self._experiment_name = f"{starting_name}-{str(uuid.uuid4().hex[:6])}"
        raise ValueError(
            f"Could not find a unique experiment name in {num_attempts} attempts."
            " Please try again with a different experiment name."
        )

    def _get_project(self, first_example: schemas.Example) -> schemas.TracerSession:
        if self._experiment is None:
            project_metadata = self._get_experiment_metadata()
            project = self._create_experiment(
                first_example.dataset_id, project_metadata
            )
        else:
            project = self._experiment
        return project

    def _print_experiment_start(
        self, project: Optional[schemas.TracerSession], first_example: schemas.Example
    ) -> None:
        if project and project.url:
            # TODO: Make this a public API
            project_url = project.url.split("?")[0]
            dataset_id = first_example.dataset_id
            base_url = project_url.split("/projects/p/")[0]
            comparison_url = (
                f"{base_url}/datasets/{dataset_id}/compare?"
                f"selectedSessions={project.id}"
            )
            print(  # noqa: T201
                f"View the evaluation results for experiment: '{self.experiment_name}'"
                f" at:\n{comparison_url}\n\n"
            )
        else:
            # HACKHACK
            print(  # noqa: T201
                "Starting evaluation of experiment: %s", self.experiment_name
            )


class _ExperimentManager(_ExperimentManagerMixin):
    """Manage the execution of experiments.

    Supports lazily running predictions and evaluations in parallel to facilitate
    result streaming and early debugging.

    Args:
        data (DATA_T): The data used for the experiment. Can be a dataset name or ID OR
            a generator of examples.
        num_repetitions (int): The number of times to run over the data.
        runs (Optional[Iterable[schemas.Run]]): The runs associated with the experiment
            predictions.
        experiment (Optional[schemas.TracerSession]): The tracer session
            associated with the experiment.
        experiment_prefix (Optional[str]): The prefix for the experiment name.
        metadata (Optional[dict]): Additional metadata for the experiment.
        client (Optional[langsmith.Client]): The Langsmith client used for
             the experiment.
        evaluation_results (Optional[Iterable[EvaluationResults]]): The evaluation
            sresults for the experiment.
        summary_results (Optional[Iterable[EvaluationResults]]): The aggregate results
            for the experiment.
    """

    def __init__(
        self,
        data: DATA_T,
        /,
        experiment: Optional[Union[schemas.TracerSession, str]],
        metadata: Optional[dict] = None,
        client: Optional[langsmith.Client] = None,
        runs: Optional[Iterable[schemas.Run]] = None,
        evaluation_results: Optional[Iterable[EvaluationResults]] = None,
        summary_results: Optional[Iterable[EvaluationResults]] = None,
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
        self._examples: Optional[Iterable[schemas.Example]] = None
        self._runs = runs
        self._evaluation_results = evaluation_results
        self._summary_results = summary_results
        self._num_repetitions = num_repetitions
        self._include_attachments = include_attachments
        self._reuse_attachments = reuse_attachments
        self._upload_results = upload_results
        self._attachment_raw_data_dict = attachment_raw_data_dict
        self._error_handling = error_handling

    def _reset_example_attachment_readers(
        self, example: schemas.Example
    ) -> schemas.Example:
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

    @property
    def examples(self) -> Iterable[schemas.Example]:
        if self._examples is None:
            self._examples = _resolve_data(
                self._data,
                client=self.client,
                include_attachments=self._include_attachments,
            )
            if self._reuse_attachments and self._attachment_raw_data_dict is None:
                examples_copy, self._examples = itertools.tee(self._examples)
                self._attachment_raw_data_dict = {
                    str(e.id) + name: value["reader"].read()
                    for e in examples_copy
                    for name, value in (e.attachments or {}).items()
                }
            if self._num_repetitions > 1:
                examples_list = list(self._examples)
                self._examples = itertools.chain.from_iterable(
                    [
                        self._reset_example_attachment_readers(example)
                        for example in examples_list
                    ]
                    for _ in range(self._num_repetitions)
                )
        self._examples, examples_iter = itertools.tee(self._examples)
        return examples_iter

    @property
    def dataset_id(self) -> str:
        if self._experiment is None or not getattr(
            self._experiment, "reference_dataset_id", None
        ):
            example = next(iter(self.examples))
            return str(example.dataset_id)
        return str(
            cast(schemas.TracerSessionResult, self._experiment).reference_dataset_id
        )

    @property
    def evaluation_results(self) -> Iterable[EvaluationResults]:
        if self._evaluation_results is None:
            return ({"results": []} for _ in self.examples)
        return self._evaluation_results

    @property
    def runs(self) -> Iterable[schemas.Run]:
        if self._runs is None:
            raise ValueError(
                "Runs not provided in this experiment. Please predict first."
            )
        self._runs, runs_iter = itertools.tee(self._runs)
        return runs_iter

    def start(self) -> _ExperimentManager:
        first_example = next(itertools.islice(self.examples, 1))
        project = self._get_project(first_example) if self._upload_results else None
        self._print_experiment_start(project, first_example)
        self._metadata["num_repetitions"] = self._num_repetitions
        return self._copy(self.examples, experiment=project)

    def with_predictions(
        self,
        target: TARGET_T,
        /,
        max_concurrency: Optional[int] = None,
    ) -> _ExperimentManager:
        """Lazily apply the target function to the experiment."""
        context = copy_context()
        _experiment_results = context.run(
            self._predict,
            target,
            max_concurrency=max_concurrency,
            include_attachments=_target_include_attachments(target),
        )
        r1, r2 = itertools.tee(_experiment_results, 2)
        return self._copy(
            (pred["example"] for pred in r1), runs=(pred["run"] for pred in r2)
        )

    def with_evaluators(
        self,
        evaluators: Sequence[
            Union[
                EVALUATOR_T,
                RunEvaluator,
            ]
        ],
        *,
        max_concurrency: Optional[int] = None,
    ) -> _ExperimentManager:
        """Lazily apply the provided evaluators to the experiment."""
        evaluators = _resolve_evaluators(evaluators)
        context = copy_context()
        experiment_results = context.run(
            self._score, evaluators, max_concurrency=max_concurrency
        )
        # Split the generator into three so the manager
        # can consume each value individually.
        r1, r2, r3 = itertools.tee(experiment_results, 3)
        return self._copy(
            (result["example"] for result in r1),
            runs=(result["run"] for result in r2),
            evaluation_results=(result["evaluation_results"] for result in r3),
        )

    def with_summary_evaluators(
        self,
        summary_evaluators: Sequence[SUMMARY_EVALUATOR_T],
    ) -> _ExperimentManager:
        """Lazily apply the provided summary evaluators to the experiment."""
        wrapped_evaluators = _wrap_summary_evaluators(summary_evaluators)
        context = copy_context()
        aggregate_feedback_gen = context.run(
            self._apply_summary_evaluators, wrapped_evaluators
        )
        return self._copy(
            self.examples, runs=self.runs, summary_results=aggregate_feedback_gen
        )

    def get_results(self) -> Iterable[ExperimentResultRow]:
        """Return the traces, evaluation results, and associated examples."""
        for run, example, evaluation_results in zip(
            self.runs, self.examples, self.evaluation_results
        ):
            yield ExperimentResultRow(
                run=run,
                example=example,
                evaluation_results=evaluation_results,
            )

    def get_summary_scores(self) -> dict[str, list[dict]]:
        """If summary_evaluators were applied, consume and return the results."""
        if self._summary_results is None:
            return {"results": []}
        # Consume the generator
        return {
            "results": [
                res  # type: ignore[misc]
                for results in self._summary_results
                for res in results["results"]
            ]
        }

    # Private methods

    def _predict(
        self,
        target: TARGET_T,
        /,
        max_concurrency: Optional[int] = None,
        include_attachments: bool = False,
    ) -> Generator[_ForwardResults, None, None]:
        """Run the target function on the examples."""
        fn = _ensure_traceable(target)

        if max_concurrency == 0:
            for example in self.examples:
                yield _forward(
                    fn,
                    example,
                    self.experiment_name,
                    self._metadata,
                    self.client,
                    self._upload_results,
                    include_attachments,
                    self._error_handling,
                )

        else:
            with ls_utils.ContextThreadPoolExecutor(max_concurrency) as executor:
                futures = [
                    executor.submit(
                        _forward,
                        fn,
                        example,
                        self.experiment_name,
                        self._metadata,
                        self.client,
                        self._upload_results,
                        include_attachments,
                        self._error_handling,
                    )
                    for example in self.examples
                ]
                for future in cf.as_completed(futures):
                    yield future.result()
        # Close out the project.
        self._end()

    def _run_evaluators(
        self,
        evaluators: Sequence[RunEvaluator],
        current_results: ExperimentResultRow,
        executor: cf.ThreadPoolExecutor,
    ) -> ExperimentResultRow:
        current_context = rh.get_tracing_context()
        metadata = {
            **(current_context["metadata"] or {}),
            **{
                "experiment": self.experiment_name,
                "reference_example_id": current_results["example"].id,
                "reference_run_id": current_results["run"].id,
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
            run = current_results["run"]
            example = current_results["example"]
            eval_results = current_results["evaluation_results"]
            for evaluator in evaluators:
                evaluator_run_id = uuid.uuid4()
                try:
                    evaluator_response = evaluator.evaluate_run(  # type: ignore[call-arg]
                        run=run,
                        example=example,
                        evaluator_run_id=evaluator_run_id,
                    )

                    eval_results["results"].extend(
                        self.client._select_eval_results(evaluator_response)
                    )
                    if self._upload_results:
                        # TODO: This is a hack
                        self.client._log_evaluation_feedback(
                            evaluator_response, run=run, _executor=executor
                        )
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
                        eval_results["results"].extend(
                            self.client._select_eval_results(error_response)
                        )
                        if self._upload_results:
                            # TODO: This is a hack
                            self.client._log_evaluation_feedback(
                                error_response, run=run, _executor=executor
                            )
                    except Exception as e2:
                        logger.debug(f"Error parsing feedback keys: {e2}")
                        pass
                    logger.error(
                        f"Error running evaluator {repr(evaluator)} on"
                        f" run {run.id if run else ''}: {repr(e)}",
                        exc_info=True,
                    )
                if example.attachments is not None:
                    for attachment in example.attachments:
                        reader = example.attachments[attachment]["reader"]
                        reader.seek(0)

            return ExperimentResultRow(
                run=run,
                example=example,
                evaluation_results=eval_results,
            )

    def _score(
        self,
        evaluators: Sequence[RunEvaluator],
        max_concurrency: Optional[int] = None,
    ) -> Iterable[ExperimentResultRow]:
        """Run the evaluators on the prediction stream.

        Expects runs to be available in the manager.
        (e.g. from a previous prediction step)
        """
        with ls_utils.ContextThreadPoolExecutor(
            max_workers=max_concurrency or 1
        ) as executor:
            if max_concurrency == 0:
                context = copy_context()
                for current_results in self.get_results():
                    yield context.run(
                        self._run_evaluators,
                        evaluators,
                        current_results,
                        executor,
                    )
            else:
                futures = set()
                for current_results in self.get_results():
                    futures.add(
                        executor.submit(
                            self._run_evaluators,
                            evaluators,
                            current_results,
                            executor,
                        )
                    )
                    try:
                        # Since prediction may be slow, yield (with a timeout) to
                        # allow for early results to be emitted.
                        for future in cf.as_completed(futures, timeout=0.001):
                            yield future.result()
                            futures.remove(future)
                    except (cf.TimeoutError, TimeoutError):
                        pass
                for future in cf.as_completed(futures):
                    result = future.result()
                    yield result

    def _apply_summary_evaluators(
        self, summary_evaluators: Sequence[SUMMARY_EVALUATOR_T]
    ) -> Generator[EvaluationResults, None, None]:
        runs, examples = [], []
        for run, example in zip(self.runs, self.examples):
            runs.append(run)
            examples.append(example)
        aggregate_feedback = []
        with ls_utils.ContextThreadPoolExecutor() as executor:
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
                    "client": self.client,
                    "enabled": "local" if not self._upload_results else True,
                }
            ):
                for evaluator in summary_evaluators:
                    try:
                        summary_eval_result = evaluator(runs, examples)
                        # TODO: Expose public API for this.
                        flattened_results = self.client._select_eval_results(
                            summary_eval_result,
                            fn_name=evaluator.__name__,
                        )
                        aggregate_feedback.extend(flattened_results)
                        if self._upload_results:
                            for result in flattened_results:
                                feedback = result.dict(exclude={"target_run_id"})
                                evaluator_info = feedback.pop("evaluator_info", None)
                                executor.submit(
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

    def _get_dataset_version(self) -> Optional[str]:
        examples = list(self.examples)
        modified_at = [ex.modified_at for ex in examples if ex.modified_at]
        # Should always be defined in practice when fetched,
        # but the typing permits None
        max_modified_at = max(modified_at) if modified_at else None
        return max_modified_at.isoformat() if max_modified_at else None

    def _get_dataset_splits(self) -> Optional[list[str]]:
        examples = list(self.examples)
        splits = set()
        for example in examples:
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

    def _end(self) -> None:
        if not self._upload_results:
            return
        experiment = self._experiment
        if experiment is None:
            raise ValueError("Experiment not started yet.")

        project_metadata = self._get_experiment_metadata()
        project_metadata["dataset_version"] = self._get_dataset_version()
        project_metadata["dataset_splits"] = self._get_dataset_splits()
        self.client.update_project(
            experiment.id,
            metadata={
                **experiment.metadata,
                **project_metadata,
            },
        )

    def _copy(self, *args: Any, **kwargs: Any) -> _ExperimentManager:
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


def _resolve_evaluators(
    evaluators: Sequence[Union[EVALUATOR_T, RunEvaluator, AEVALUATOR_T]],
) -> Sequence[RunEvaluator]:
    results = []
    for evaluator in evaluators:
        if isinstance(evaluator, RunEvaluator):
            results.append(evaluator)
        elif isinstance(evaluator, LangChainStringEvaluator):
            results.append(evaluator.as_run_evaluator())
        else:
            results.append(run_evaluator(evaluator))
    return results


def _wrap_summary_evaluators(
    evaluators: Sequence[SUMMARY_EVALUATOR_T],
) -> list[SUMMARY_EVALUATOR_T]:
    def _wrap(evaluator: SUMMARY_EVALUATOR_T) -> SUMMARY_EVALUATOR_T:
        eval_name = getattr(evaluator, "__name__", "BatchEvaluator")
        evaluator = _normalize_summary_evaluator(evaluator)

        @functools.wraps(evaluator)
        def _wrapper_inner(
            runs: Sequence[schemas.Run], examples: Sequence[schemas.Example]
        ) -> Union[EvaluationResult, EvaluationResults]:
            @rh.traceable(name=eval_name)
            def _wrapper_super_inner(
                runs_: str, examples_: str
            ) -> Union[EvaluationResult, EvaluationResults]:
                return evaluator(list(runs), list(examples))

            return _wrapper_super_inner(
                f"Runs[] (Length={len(runs)})", f"Examples[] (Length={len(examples)})"
            )

        return _wrapper_inner

    results = []
    for evaluator in evaluators:
        results.append(_wrap(evaluator))
    return results


class _ForwardResults(TypedDict):
    run: schemas.Run
    example: schemas.Example


def _forward(
    fn: rh.SupportsLangsmithExtra,
    example: schemas.Example,
    experiment_name: str,
    metadata: dict,
    client: langsmith.Client,
    upload_results: bool,
    include_attachments: bool = False,
    error_handling: Literal["log", "ignore"] = "log",
) -> _ForwardResults:
    run: Optional[schemas.RunBase] = None

    def _get_run(r: rt.RunTree) -> None:
        nonlocal run
        run = r

    def _set_reference_example_id(r: rt.RunTree) -> None:
        r.reference_example_id = example.id

    example_version = (example.modified_at or example.created_at).isoformat()
    langsmith_extra = rh.LangSmithExtra(
        on_end=_get_run,
        project_name=experiment_name,
        metadata={**metadata, "example_version": example_version},
        client=client,
    )
    if error_handling == "log":
        langsmith_extra["reference_example_id"] = example.id
    elif error_handling == "ignore":
        # Only set the reference_example_id if the run succeeds.
        langsmith_extra["_on_success"] = _set_reference_example_id
    else:
        raise ValueError(f"Unrecognized error_handling value: {error_handling=}")

    with rh.tracing_context(enabled="local" if not upload_results else True):
        try:
            arg_names = _get_target_args(fn)
            args = [getattr(example, argn) for argn in arg_names]
            fn(*args, langsmith_extra=langsmith_extra)
            # Reset attachment readers if attachments were used.
            if include_attachments and example.attachments is not None:
                for attachment in example.attachments:
                    reader = example.attachments[attachment]["reader"]
                    reader.seek(0)
        except Exception as e:
            logger.error(
                f"Error running target function: {e}", exc_info=True, stacklevel=1
            )
        return _ForwardResults(run=cast(schemas.Run, run), example=example)


def _is_valid_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
        return True
    except ValueError:
        return False


def _resolve_data(
    data: DATA_T,
    *,
    client: langsmith.Client,
    include_attachments: bool = False,
) -> Iterable[schemas.Example]:
    """Return the examples for the given dataset."""
    if isinstance(data, uuid.UUID):
        return client.list_examples(
            dataset_id=data, include_attachments=include_attachments
        )
    elif isinstance(data, str) and _is_valid_uuid(data):
        return client.list_examples(
            dataset_id=uuid.UUID(data), include_attachments=include_attachments
        )
    elif isinstance(data, str):
        return client.list_examples(
            dataset_name=data, include_attachments=include_attachments
        )
    elif isinstance(data, schemas.Dataset):
        return client.list_examples(
            dataset_id=data.id, include_attachments=include_attachments
        )
    return data


def _ensure_traceable(
    target: TARGET_T | rh.SupportsLangsmithExtra[[dict], dict] | Runnable,
) -> rh.SupportsLangsmithExtra[[dict], dict]:
    """Ensure the target function is traceable."""
    if not _is_callable(target):
        raise ValueError(
            "Target must be a callable function or a langchain/langgraph object. For "
            "example:\n\n"
            "def predict(inputs: dict) -> dict:\n"
            "    # do work, like chain.invoke(inputs)\n"
            "    return {...}\n\n"
            "evaluate(\n"
            "    predict,\n"
            "    ...\n"
            ")"
        )

    if rh.is_traceable_function(target):
        fn: rh.SupportsLangsmithExtra[[dict], dict] = target
    else:
        if _is_langchain_runnable(target):
            target = target.invoke  # type: ignore[union-attr]
        fn = rh.traceable(name="Target")(cast(Callable, target))
    return fn


def _include_attachments(target: Any, evaluators: Optional[Sequence]) -> bool:
    return _target_include_attachments(target) or bool(
        _evaluators_include_attachments(evaluators)
    )


def _evaluators_include_attachments(evaluators: Optional[Sequence]) -> int:
    if evaluators is None:
        return 0

    return sum(_evaluator_uses_attachments(e) for e in evaluators)


def _evaluator_uses_attachments(evaluator: Any) -> bool:
    if not callable(evaluator):
        return False
    sig = inspect.signature(evaluator)
    params = list(sig.parameters.values())
    positional_params = [
        p for p in params if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
    ]
    return any(p.name == "attachments" for p in positional_params)


def _target_include_attachments(target: Any) -> bool:
    """Whether the target function accepts attachments."""
    return "attachments" in _get_target_args(target)


def _get_target_args(target: Any) -> list[str]:
    """Whether the target function accepts attachments."""
    if not callable(target):
        return []
    if _is_langchain_runnable(target):
        return ["inputs"]
    # Check function signature
    sig = inspect.signature(target)
    params = list(sig.parameters.values())
    positional_params = [
        p for p in params if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
    ]
    positional_no_default = [p for p in positional_params if p.default is p.empty]

    if len(positional_params) == 0:
        raise ValueError(
            "Target function must accept at least one positional argument (inputs)."
        )
    elif len(positional_no_default) > 3:
        raise ValueError(
            "Target function must accept at most three "
            "arguments without default values: (inputs, attachments, metadata)."
        )
    elif len(positional_no_default) > 1 and {
        p.name for p in positional_no_default
    }.difference(["inputs", "attachments", "metadata"]):
        raise ValueError(
            "When passing multiple positional arguments without default values, they "
            "must be named 'inputs', 'attachments', or 'metadata'. Received: "
            f"{[p.name for p in positional_no_default]}"
        )
    else:
        args = []
        for p in positional_params[:3]:
            if p.name in {"inputs", "attachments", "metadata"}:
                args.append(p.name)
            else:
                break
        return args or ["inputs"]


def _resolve_experiment(
    experiment: Optional[Union[schemas.TracerSession, str, uuid.UUID]],
    runs: Optional[Iterable[schemas.Run]],
    client: langsmith.Client,
) -> tuple[
    Optional[Union[schemas.TracerSession, str]], Optional[Iterable[schemas.Run]]
]:
    # TODO: Remove this, handle outside the manager
    if experiment is not None:
        if isinstance(experiment, schemas.TracerSession):
            experiment_ = experiment
        else:
            experiment_ = _load_experiment(experiment, client)

        if not experiment_.name:
            raise ValueError("Experiment name must be defined if provided.")
        if not experiment_.reference_dataset_id:
            raise ValueError(
                "Experiment must have an associated reference_dataset_id, "
                "but none was provided."
            )
        return experiment_, runs
    # If we have runs, that means the experiment was already started.
    if runs is not None:
        runs_, runs = itertools.tee(runs)
        first_run = next(runs_)
        experiment_ = client.read_project(project_id=first_run.session_id)
        if not experiment_.name:
            raise ValueError("Experiment name not found for provided runs.")
        return experiment_, runs
    return None, None


def _get_random_name() -> str:
    from langsmith.evaluation._name_generation import random_name  # noqa: F401

    return random_name()


def _extract_feedback_keys(evaluator: RunEvaluator):
    if isinstance(evaluator, DynamicRunEvaluator):
        if getattr(evaluator, "func", None):
            return _extract_code_evaluator_feedback_keys(evaluator.func)
        elif getattr(evaluator, "afunc", None):
            return _extract_code_evaluator_feedback_keys(evaluator.afunc)
    # TODO: Support for DynamicComparisonRunEvaluator
    if hasattr(evaluator, "evaluator"):
        # LangChainStringEvaluator
        if getattr(getattr(evaluator, "evaluator"), "evaluation_name", None):
            return [evaluator.evaluator.evaluation_name]
    return []


def _extract_code_evaluator_feedback_keys(func: Callable) -> list[str]:
    python_code = inspect.getsource(func)

    def extract_dict_keys(node):
        if isinstance(node, ast.Dict):
            keys = []
            key_value = None
            for key, value in zip(node.keys, node.values):
                if isinstance(key, (ast.Str, ast.Constant)):
                    key_str = key.s if isinstance(key, ast.Str) else key.value
                    if key_str == "key" and isinstance(value, (ast.Str, ast.Constant)):
                        key_value = (
                            value.s if isinstance(value, ast.Str) else value.value
                        )
            return [key_value] if key_value else keys
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "dict"
        ):
            for keyword in node.keywords:
                if keyword.arg == "key" and isinstance(
                    keyword.value, (ast.Str, ast.Constant)
                ):
                    return [
                        (
                            keyword.value.s
                            if isinstance(keyword.value, ast.Str)
                            else keyword.value.value
                        )
                    ]
        return []

    def extract_evaluation_result_key(node):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "EvaluationResult"
        ):
            for keyword in node.keywords:
                if keyword.arg == "key" and isinstance(
                    keyword.value, (ast.Str, ast.Constant)
                ):
                    return [
                        (
                            keyword.value.s
                            if isinstance(keyword.value, ast.Str)
                            else keyword.value.value
                        )
                    ]
        return []

    def extract_evaluation_results_keys(node, variables):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "EvaluationResults"
        ):
            for keyword in node.keywords:
                if keyword.arg == "results":
                    if isinstance(keyword.value, ast.Name):
                        return variables.get(keyword.value.id, [])
                    elif isinstance(keyword.value, ast.List):
                        keys = []
                        for elt in keyword.value.elts:
                            keys.extend(extract_evaluation_result_key(elt))
                        return keys
        elif isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values):
                if isinstance(key, (ast.Str, ast.Constant)) and key.s == "results":
                    if isinstance(value, ast.List):
                        keys = []
                        for elt in value.elts:
                            if isinstance(elt, ast.Dict):
                                for elt_key, elt_value in zip(elt.keys, elt.values):
                                    if (
                                        isinstance(elt_key, (ast.Str, ast.Constant))
                                        and elt_key.s == "key"
                                    ):
                                        if isinstance(
                                            elt_value, (ast.Str, ast.Constant)
                                        ):
                                            keys.append(elt_value.s)
                            elif (
                                isinstance(elt, ast.Call)
                                and isinstance(elt.func, ast.Name)
                                and elt.func.id in ("EvaluationResult", "dict")
                            ):
                                for keyword in elt.keywords:
                                    if keyword.arg == "key" and isinstance(
                                        keyword.value, (ast.Str, ast.Constant)
                                    ):
                                        keys.append(
                                            keyword.value.s
                                            if isinstance(keyword.value, ast.Str)
                                            else keyword.value.value
                                        )

                        return keys
        return []

    python_code = textwrap.dedent(python_code)

    try:
        tree = ast.parse(python_code)
        function_def = tree.body[0]
        if not isinstance(function_def, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return []

        variables = {}
        keys = []

        for node in ast.walk(function_def):
            if isinstance(node, ast.Assign):
                if isinstance(node.value, ast.List):
                    list_keys = []
                    for elt in node.value.elts:
                        list_keys.extend(extract_evaluation_result_key(elt))
                    if isinstance(node.targets[0], ast.Name):
                        variables[node.targets[0].id] = list_keys
            elif isinstance(node, ast.Return) and node.value is not None:
                dict_keys = extract_dict_keys(node.value)
                eval_result_key = extract_evaluation_result_key(node.value)
                eval_results_keys = extract_evaluation_results_keys(
                    node.value, variables
                )

                keys.extend(dict_keys)
                keys.extend(eval_result_key)
                keys.extend(eval_results_keys)

        # If no keys found, return the function name
        return keys if keys else [function_def.name]

    except SyntaxError:
        return []


def _to_pandas(
    results: list[ExperimentResultRow],
    start: Optional[int] = 0,
    end: Optional[int] = None,
):
    try:
        import pandas as pd
    except ImportError as e:
        raise ImportError(
            "The 'pandas' library is required to use the 'to_pandas' function. "
            "Please install it using 'pip install pandas' or "
            "'conda install pandas' before calling this method."
        ) from e

    return pd.DataFrame(_flatten_experiment_results(results, start=start, end=end))


def _flatten_experiment_results(
    results: list[ExperimentResultRow],
    start: Optional[int] = 0,
    end: Optional[int] = None,
):
    return [
        {
            **{f"inputs.{k}": v for k, v in (x["example"].inputs or {}).items()},
            **{f"outputs.{k}": v for k, v in (x["run"].outputs or {}).items()},
            "error": x["run"].error,
            **(
                {f"reference.{k}": v for k, v in x["example"].outputs.items()}
                if x["example"].outputs is not None
                else {}
            ),
            **{
                f"feedback.{r.key}": r.score if r.score is not None else r.value
                for r in x["evaluation_results"]["results"]
            },
            "execution_time": (
                (x["run"].end_time - x["run"].start_time).total_seconds()
                if x["run"].end_time
                else None
            ),
            "example_id": x["run"].reference_example_id,
            "id": x["run"].id,
        }
        for x in results[start:end]
    ]


@functools.lru_cache(maxsize=1)
def _import_langchain_runnable() -> Optional[type]:
    try:
        from langchain_core.runnables import Runnable

        return Runnable
    except ImportError:
        return None


def _is_langchain_runnable(o: Any) -> bool:
    return bool((Runnable := _import_langchain_runnable()) and isinstance(o, Runnable))
