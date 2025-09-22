# Copyright 2014-present MongoDB, Inc.
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

"""Support for SSL in PyMongo."""
from __future__ import annotations

import types
import warnings
from typing import Any, Optional, Union

from pymongo.errors import ConfigurationError

HAVE_SSL = True
HAVE_PYSSL = True

try:
    import pymongo.pyopenssl_context as _pyssl
except (ImportError, AttributeError) as exc:
    HAVE_PYSSL = False
    if isinstance(exc, AttributeError):
        warnings.warn(
            "Failed to use the installed version of PyOpenSSL. "
            "Falling back to stdlib ssl, disabling OCSP support. "
            "This is likely caused by incompatible versions "
            "of PyOpenSSL < 23.2.0 and cryptography >= 42.0.0. "
            "Try updating PyOpenSSL >= 23.2.0 to enable OCSP.",
            UserWarning,
            stacklevel=2,
        )
try:
    import pymongo.ssl_context as _ssl
except ImportError:
    HAVE_SSL = False


if HAVE_SSL:
    # Note: The validate* functions below deal with users passing
    # CPython ssl module constants to configure certificate verification
    # at a high level. This is legacy behavior, but requires us to
    # import the ssl module even if we're only using it for this purpose.
    import ssl as _stdlibssl  # noqa: F401
    from ssl import CERT_NONE, CERT_REQUIRED

    IPADDR_SAFE = True

    if HAVE_PYSSL:
        PYSSLError: Any = _pyssl.SSLError
        BLOCKING_IO_ERRORS: tuple = _ssl.BLOCKING_IO_ERRORS + _pyssl.BLOCKING_IO_ERRORS
        BLOCKING_IO_READ_ERROR: tuple = (_pyssl.BLOCKING_IO_READ_ERROR, _ssl.BLOCKING_IO_READ_ERROR)
        BLOCKING_IO_WRITE_ERROR: tuple = (
            _pyssl.BLOCKING_IO_WRITE_ERROR,
            _ssl.BLOCKING_IO_WRITE_ERROR,
        )
    else:
        PYSSLError = _ssl.SSLError
        BLOCKING_IO_ERRORS = _ssl.BLOCKING_IO_ERRORS
        BLOCKING_IO_READ_ERROR = (_ssl.BLOCKING_IO_READ_ERROR,)
        BLOCKING_IO_WRITE_ERROR = (_ssl.BLOCKING_IO_WRITE_ERROR,)
    SSLError = _ssl.SSLError
    BLOCKING_IO_LOOKUP_ERROR = BLOCKING_IO_READ_ERROR

    def _has_sni(is_sync: bool) -> bool:
        if is_sync and HAVE_PYSSL:
            return _pyssl.HAS_SNI
        return _ssl.HAS_SNI

    def get_ssl_context(
        certfile: Optional[str],
        passphrase: Optional[str],
        ca_certs: Optional[str],
        crlfile: Optional[str],
        allow_invalid_certificates: bool,
        allow_invalid_hostnames: bool,
        disable_ocsp_endpoint_check: bool,
        is_sync: bool,
    ) -> Union[_pyssl.SSLContext, _ssl.SSLContext]:  # type: ignore[name-defined]
        """Create and return an SSLContext object."""
        if is_sync and HAVE_PYSSL:
            ssl: types.ModuleType = _pyssl
        else:
            ssl = _ssl
        verify_mode = CERT_NONE if allow_invalid_certificates else CERT_REQUIRED
        ctx = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
        if verify_mode != CERT_NONE:
            ctx.check_hostname = not allow_invalid_hostnames
        else:
            ctx.check_hostname = False
        if hasattr(ctx, "check_ocsp_endpoint"):
            ctx.check_ocsp_endpoint = not disable_ocsp_endpoint_check
        if hasattr(ctx, "options"):
            # Explicitly disable SSLv2, SSLv3 and TLS compression. Note that
            # up to date versions of MongoDB 2.4 and above already disable
            # SSLv2 and SSLv3, python disables SSLv2 by default in >= 2.7.7
            # and >= 3.3.4 and SSLv3 in >= 3.4.3.
            ctx.options |= ssl.OP_NO_SSLv2
            ctx.options |= ssl.OP_NO_SSLv3
            ctx.options |= ssl.OP_NO_COMPRESSION
            ctx.options |= ssl.OP_NO_RENEGOTIATION
        if certfile is not None:
            try:
                ctx.load_cert_chain(certfile, None, passphrase)
            except ssl.SSLError as exc:
                raise ConfigurationError(f"Private key doesn't match certificate: {exc}") from None
        if crlfile is not None:
            if ssl.IS_PYOPENSSL:
                raise ConfigurationError("tlsCRLFile cannot be used with PyOpenSSL")
            # Match the server's behavior.
            ctx.verify_flags = getattr(ssl, "VERIFY_CRL_CHECK_LEAF", 0)
            ctx.load_verify_locations(crlfile)
        if ca_certs is not None:
            ctx.load_verify_locations(ca_certs)
        elif verify_mode != CERT_NONE:
            ctx.load_default_certs()
        ctx.verify_mode = verify_mode
        return ctx

else:

    class SSLError(Exception):  # type: ignore
        pass

    IPADDR_SAFE = False
    BLOCKING_IO_ERRORS = ()

    def _has_sni(is_sync: bool) -> bool:  # noqa: ARG001
        return False

    def get_ssl_context(*dummy):  # type: ignore
        """No ssl module, raise ConfigurationError."""
        raise ConfigurationError("The ssl module is not available")
