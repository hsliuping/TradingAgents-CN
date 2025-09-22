# Copyright The OpenTelemetry Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from argparse import REMAINDER, ArgumentParser
from logging import getLogger
from os import environ, execl, getcwd
from os.path import abspath, dirname, pathsep
from re import sub
from shutil import which

from opentelemetry.instrumentation.auto_instrumentation._load import (
    _load_configurators,
    _load_distro,
    _load_instrumentors,
)
from opentelemetry.instrumentation.utils import _python_path_without_directory
from opentelemetry.instrumentation.version import __version__
from opentelemetry.util._importlib_metadata import entry_points

_logger = getLogger(__name__)


def run() -> None:
    parser = ArgumentParser(
        description="""
        opentelemetry-instrument automatically instruments a Python
        program and its dependencies and then runs the program.
        """,
        epilog="""
        Optional arguments (except for --help and --version) for opentelemetry-instrument
        directly correspond with OpenTelemetry environment variables. The
        corresponding optional argument is formed by removing the OTEL_ or
        OTEL_PYTHON_ prefix from the environment variable and lower casing the
        rest. For example, the optional argument --attribute_value_length_limit
        corresponds with the environment variable
        OTEL_ATTRIBUTE_VALUE_LENGTH_LIMIT.

        These optional arguments will override the current value of the
        corresponding environment variable during the execution of the command.
        """,
    )

    argument_otel_environment_variable = {}

    for entry_point in entry_points(
        group="opentelemetry_environment_variables"
    ):
        environment_variable_module = entry_point.load()

        for attribute in dir(environment_variable_module):
            if attribute.startswith("OTEL_"):
                argument = sub(r"OTEL_(PYTHON_)?", "", attribute).lower()

                parser.add_argument(
                    f"--{argument}",
                    required=False,
                )
                argument_otel_environment_variable[argument] = attribute

    parser.add_argument(
        "--version",
        help="print version information",
        action="version",
        version="%(prog)s " + __version__,
    )
    parser.add_argument("command", help="Your Python application.")
    parser.add_argument(
        "command_args",
        help="Arguments for your application.",
        nargs=REMAINDER,
    )

    args = parser.parse_args()

    for argument, otel_environment_variable in (
        argument_otel_environment_variable
    ).items():
        value = getattr(args, argument)
        if value is not None:
            environ[otel_environment_variable] = value

    python_path = environ.get("PYTHONPATH")

    if not python_path:
        python_path = []

    else:
        python_path = python_path.split(pathsep)

    cwd_path = getcwd()

    # This is being added to support applications that are being run from their
    # own executable, like Django.
    # FIXME investigate if there is another way to achieve this
    if cwd_path not in python_path:
        python_path.insert(0, cwd_path)

    filedir_path = dirname(abspath(__file__))

    python_path = [path for path in python_path if path != filedir_path]

    python_path.insert(0, filedir_path)

    environ["PYTHONPATH"] = pathsep.join(python_path)

    executable = which(args.command)
    execl(executable, executable, *args.command_args)


def initialize(*, swallow_exceptions: bool = True) -> None:
    """
    Setup auto-instrumentation, called by the sitecustomize module

    :param swallow_exceptions: Whether or not to propagate instrumentation exceptions to the caller. Exceptions are logged and swallowed by default.
    """
    # prevents auto-instrumentation of subprocesses if code execs another python process
    if "PYTHONPATH" in environ:
        environ["PYTHONPATH"] = _python_path_without_directory(
            environ["PYTHONPATH"], dirname(abspath(__file__)), pathsep
        )

    try:
        distro = _load_distro()
        distro.configure()
        _load_configurators()
        _load_instrumentors(distro)
    except Exception as exc:  # pylint: disable=broad-except
        _logger.exception("Failed to auto initialize OpenTelemetry")
        if not swallow_exceptions:
            raise exc
