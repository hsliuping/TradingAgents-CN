# Copyright 2011-present MongoDB, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you
# may not use this file except in compliance with the License.  You
# may obtain a copy of the License at
#
# https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.  See the License for the specific language governing
# permissions and limitations under the License.


"""Tools to parse and validate a MongoDB URI."""
from __future__ import annotations

from typing import Any, Optional
from urllib.parse import unquote_plus

from pymongo.common import SRV_SERVICE_NAME, _CaseInsensitiveDictionary
from pymongo.errors import ConfigurationError, InvalidURI
from pymongo.synchronous.srv_resolver import _SrvResolver
from pymongo.uri_parser_shared import (
    _ALLOWED_TXT_OPTS,
    DEFAULT_PORT,
    SCHEME,
    SCHEME_LEN,
    SRV_SCHEME_LEN,
    _check_options,
    _validate_uri,
    split_hosts,
    split_options,
)

_IS_SYNC = True


def parse_uri(
    uri: str,
    default_port: Optional[int] = DEFAULT_PORT,
    validate: bool = True,
    warn: bool = False,
    normalize: bool = True,
    connect_timeout: Optional[float] = None,
    srv_service_name: Optional[str] = None,
    srv_max_hosts: Optional[int] = None,
) -> dict[str, Any]:
    """Parse and validate a MongoDB URI.

    Returns a dict of the form::

        {
            'nodelist': <list of (host, port) tuples>,
            'username': <username> or None,
            'password': <password> or None,
            'database': <database name> or None,
            'collection': <collection name> or None,
            'options': <dict of MongoDB URI options>,
            'fqdn': <fqdn of the MongoDB+SRV URI> or None
        }

    If the URI scheme is "mongodb+srv://" DNS SRV and TXT lookups will be done
    to build nodelist and options.

    :param uri: The MongoDB URI to parse.
    :param default_port: The port number to use when one wasn't specified
          for a host in the URI.
    :param validate: If ``True`` (the default), validate and
          normalize all options. Default: ``True``.
    :param warn: When validating, if ``True`` then will warn
          the user then ignore any invalid options or values. If ``False``,
          validation will error when options are unsupported or values are
          invalid. Default: ``False``.
    :param normalize: If ``True``, convert names of URI options
          to their internally-used names. Default: ``True``.
    :param connect_timeout: The maximum time in milliseconds to
          wait for a response from the DNS server.
    :param srv_service_name: A custom SRV service name

    .. versionchanged:: 4.6
       The delimiting slash (``/``) between hosts and connection options is now optional.
       For example, "mongodb://example.com?tls=true" is now a valid URI.

    .. versionchanged:: 4.0
       To better follow RFC 3986, unquoted percent signs ("%") are no longer
       supported.

    .. versionchanged:: 3.9
        Added the ``normalize`` parameter.

    .. versionchanged:: 3.6
        Added support for mongodb+srv:// URIs.

    .. versionchanged:: 3.5
        Return the original value of the ``readPreference`` MongoDB URI option
        instead of the validated read preference mode.

    .. versionchanged:: 3.1
        ``warn`` added so invalid options can be ignored.
    """
    result = _validate_uri(uri, default_port, validate, warn, normalize, srv_max_hosts)
    result.update(
        _parse_srv(
            uri,
            default_port,
            validate,
            warn,
            normalize,
            connect_timeout,
            srv_service_name,
            srv_max_hosts,
        )
    )
    return result


def _parse_srv(
    uri: str,
    default_port: Optional[int] = DEFAULT_PORT,
    validate: bool = True,
    warn: bool = False,
    normalize: bool = True,
    connect_timeout: Optional[float] = None,
    srv_service_name: Optional[str] = None,
    srv_max_hosts: Optional[int] = None,
) -> dict[str, Any]:
    if uri.startswith(SCHEME):
        is_srv = False
        scheme_free = uri[SCHEME_LEN:]
    else:
        is_srv = True
        scheme_free = uri[SRV_SCHEME_LEN:]

    options = _CaseInsensitiveDictionary()

    host_plus_db_part, _, opts = scheme_free.partition("?")
    if "/" in host_plus_db_part:
        host_part, _, _ = host_plus_db_part.partition("/")
    else:
        host_part = host_plus_db_part

    if opts:
        options.update(split_options(opts, validate, warn, normalize))
    if srv_service_name is None:
        srv_service_name = options.get("srvServiceName", SRV_SERVICE_NAME)
    if "@" in host_part:
        _, _, hosts = host_part.rpartition("@")
    else:
        hosts = host_part

    hosts = unquote_plus(hosts)
    srv_max_hosts = srv_max_hosts or options.get("srvMaxHosts")
    if is_srv:
        nodes = split_hosts(hosts, default_port=None)
        fqdn, port = nodes[0]

        # Use the connection timeout. connectTimeoutMS passed as a keyword
        # argument overrides the same option passed in the connection string.
        connect_timeout = connect_timeout or options.get("connectTimeoutMS")
        dns_resolver = _SrvResolver(fqdn, connect_timeout, srv_service_name, srv_max_hosts)
        nodes = dns_resolver.get_hosts()
        dns_options = dns_resolver.get_options()
        if dns_options:
            parsed_dns_options = split_options(dns_options, validate, warn, normalize)
            if set(parsed_dns_options) - _ALLOWED_TXT_OPTS:
                raise ConfigurationError(
                    "Only authSource, replicaSet, and loadBalanced are supported from DNS"
                )
            for opt, val in parsed_dns_options.items():
                if opt not in options:
                    options[opt] = val
        if options.get("loadBalanced") and srv_max_hosts:
            raise InvalidURI("You cannot specify loadBalanced with srvMaxHosts")
        if options.get("replicaSet") and srv_max_hosts:
            raise InvalidURI("You cannot specify replicaSet with srvMaxHosts")
        if "tls" not in options and "ssl" not in options:
            options["tls"] = True if validate else "true"
    else:
        nodes = split_hosts(hosts, default_port=default_port)

    _check_options(nodes, options)

    return {
        "nodelist": nodes,
        "options": options,
    }
