# Copyright 2019-present MongoDB, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Support for automatic client-side field level encryption.

.. seealso:: This module is compatible with both the synchronous and asynchronous PyMongo APIs.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Mapping, Optional

from pymongo.uri_parser_shared import _parse_kms_tls_options

try:
    import pymongocrypt  # type:ignore[import-untyped] # noqa: F401

    # Check for pymongocrypt>=1.10.
    from pymongocrypt import synchronous as _  # noqa: F401

    _HAVE_PYMONGOCRYPT = True
except ImportError:
    _HAVE_PYMONGOCRYPT = False
from bson import int64
from pymongo.common import validate_is_mapping
from pymongo.errors import ConfigurationError

if TYPE_CHECKING:
    from pymongo.pyopenssl_context import SSLContext
    from pymongo.typings import _AgnosticMongoClient, _DocumentTypeArg


class AutoEncryptionOpts:
    """Options to configure automatic client-side field level encryption."""

    def __init__(
        self,
        kms_providers: Mapping[str, Any],
        key_vault_namespace: str,
        key_vault_client: Optional[_AgnosticMongoClient[_DocumentTypeArg]] = None,
        schema_map: Optional[Mapping[str, Any]] = None,
        bypass_auto_encryption: bool = False,
        mongocryptd_uri: str = "mongodb://localhost:27020",
        mongocryptd_bypass_spawn: bool = False,
        mongocryptd_spawn_path: str = "mongocryptd",
        mongocryptd_spawn_args: Optional[list[str]] = None,
        kms_tls_options: Optional[Mapping[str, Any]] = None,
        crypt_shared_lib_path: Optional[str] = None,
        crypt_shared_lib_required: bool = False,
        bypass_query_analysis: bool = False,
        encrypted_fields_map: Optional[Mapping[str, Any]] = None,
        key_expiration_ms: Optional[int] = None,
    ) -> None:
        """Options to configure automatic client-side field level encryption.

        Automatic client-side field level encryption requires MongoDB >=4.2
        enterprise or a MongoDB >=4.2 Atlas cluster. Automatic encryption is not
        supported for operations on a database or view and will result in
        error.

        Although automatic encryption requires MongoDB >=4.2 enterprise or a
        MongoDB >=4.2 Atlas cluster, automatic *decryption* is supported for all
        users. To configure automatic *decryption* without automatic
        *encryption* set ``bypass_auto_encryption=True``. Explicit
        encryption and explicit decryption is also supported for all users
        with the :class:`~pymongo.asynchronous.encryption.AsyncClientEncryption` and :class:`~pymongo.encryption.ClientEncryption` classes.

        See :ref:`automatic-client-side-encryption` for an example.

        :param kms_providers: Map of KMS provider options. The `kms_providers`
            map values differ by provider:

              - `aws`: Map with "accessKeyId" and "secretAccessKey" as strings.
                These are the AWS access key ID and AWS secret access key used
                to generate KMS messages. An optional "sessionToken" may be
                included to support temporary AWS credentials.
              - `azure`: Map with "tenantId", "clientId", and "clientSecret" as
                strings. Additionally, "identityPlatformEndpoint" may also be
                specified as a string (defaults to 'login.microsoftonline.com').
                These are the Azure Active Directory credentials used to
                generate Azure Key Vault messages.
              - `gcp`: Map with "email" as a string and "privateKey"
                as `bytes` or a base64 encoded string.
                Additionally, "endpoint" may also be specified as a string
                (defaults to 'oauth2.googleapis.com'). These are the
                credentials used to generate Google Cloud KMS messages.
              - `kmip`: Map with "endpoint" as a host with required port.
                For example: ``{"endpoint": "example.com:443"}``.
              - `local`: Map with "key" as `bytes` (96 bytes in length) or
                a base64 encoded string which decodes
                to 96 bytes. "key" is the master key used to encrypt/decrypt
                data keys. This key should be generated and stored as securely
                as possible.

            KMS providers may be specified with an optional name suffix
            separated by a colon, for example "kmip:name" or "aws:name".
            Named KMS providers do not support :ref:`CSFLE on-demand credentials`.
            Named KMS providers enables more than one of each KMS provider type to be configured.
            For example, to configure multiple local KMS providers::

              kms_providers = {
                  "local": {"key": local_kek1},        # Unnamed KMS provider.
                  "local:myname": {"key": local_kek2}, # Named KMS provider with name "myname".
              }

        :param key_vault_namespace: The namespace for the key vault collection.
            The key vault collection contains all data keys used for encryption
            and decryption. Data keys are stored as documents in this MongoDB
            collection. Data keys are protected with encryption by a KMS
            provider.
        :param key_vault_client: By default, the key vault collection
            is assumed to reside in the same MongoDB cluster as the encrypted
            AsyncMongoClient/MongoClient. Use this option to route data key queries to a
            separate MongoDB cluster.
        :param schema_map: Map of collection namespace ("db.coll") to
            JSON Schema.  By default, a collection's JSONSchema is periodically
            polled with the listCollections command. But a JSONSchema may be
            specified locally with the schemaMap option.

            **Supplying a `schema_map` provides more security than relying on
            JSON Schemas obtained from the server. It protects against a
            malicious server advertising a false JSON Schema, which could trick
            the client into sending unencrypted data that should be
            encrypted.**

            Schemas supplied in the schemaMap only apply to configuring
            automatic encryption for client side encryption. Other validation
            rules in the JSON schema will not be enforced by the driver and
            will result in an error.
        :param bypass_auto_encryption: If ``True``, automatic
            encryption will be disabled but automatic decryption will still be
            enabled. Defaults to ``False``.
        :param mongocryptd_uri: The MongoDB URI used to connect
            to the *local* mongocryptd process. Defaults to
            ``'mongodb://localhost:27020'``.
        :param mongocryptd_bypass_spawn: If ``True``, the encrypted
            AsyncMongoClient/MongoClient will not attempt to spawn the mongocryptd process.
            Defaults to ``False``.
        :param mongocryptd_spawn_path: Used for spawning the
            mongocryptd process. Defaults to ``'mongocryptd'`` and spawns
            mongocryptd from the system path.
        :param mongocryptd_spawn_args: A list of string arguments to
            use when spawning the mongocryptd process. Defaults to
            ``['--idleShutdownTimeoutSecs=60']``. If the list does not include
            the ``idleShutdownTimeoutSecs`` option then
            ``'--idleShutdownTimeoutSecs=60'`` will be added.
        :param kms_tls_options:  A map of KMS provider names to TLS
            options to use when creating secure connections to KMS providers.
            Accepts the same TLS options as
            :class:`pymongo.mongo_client.AsyncMongoClient` and :class:`pymongo.mongo_client.MongoClient`. For example, to
            override the system default CA file::

              kms_tls_options={'kmip': {'tlsCAFile': certifi.where()}}

            Or to supply a client certificate::

              kms_tls_options={'kmip': {'tlsCertificateKeyFile': 'client.pem'}}
        :param crypt_shared_lib_path: Override the path to load the crypt_shared library.
        :param crypt_shared_lib_required: If True, raise an error if libmongocrypt is
            unable to load the crypt_shared library.
        :param bypass_query_analysis: If ``True``, disable automatic analysis
            of outgoing commands. Set `bypass_query_analysis` to use explicit
            encryption on indexed fields without the MongoDB Enterprise Advanced
            licensed crypt_shared library.
        :param encrypted_fields_map: Map of collection namespace ("db.coll") to documents
            that described the encrypted fields for Queryable Encryption. For example::

                {
                  "db.encryptedCollection": {
                      "escCollection": "enxcol_.encryptedCollection.esc",
                      "ecocCollection": "enxcol_.encryptedCollection.ecoc",
                      "fields": [
                          {
                              "path": "firstName",
                              "keyId": Binary.from_uuid(UUID('00000000-0000-0000-0000-000000000000')),
                              "bsonType": "string",
                              "queries": {"queryType": "equality"}
                          },
                          {
                              "path": "ssn",
                              "keyId": Binary.from_uuid(UUID('04104104-1041-0410-4104-104104104104')),
                              "bsonType": "string"
                          }
                      ]
                  }
                }
        :param key_expiration_ms: The cache expiration time for data encryption keys.
            Defaults to ``None`` which defers to libmongocrypt's default which is currently 60000.
            Set to 0 to disable key expiration.

        .. versionchanged:: 4.12
           Added the `key_expiration_ms` parameter.
        .. versionchanged:: 4.2
           Added the `encrypted_fields_map`, `crypt_shared_lib_path`, `crypt_shared_lib_required`,
           and `bypass_query_analysis` parameters.

        .. versionchanged:: 4.0
           Added the `kms_tls_options` parameter and the "kmip" KMS provider.

        .. versionadded:: 3.9
        """
        if not _HAVE_PYMONGOCRYPT:
            raise ConfigurationError(
                "client side encryption requires the pymongocrypt library: "
                "install a compatible version with: "
                "python -m pip install 'pymongo[encryption]'"
            )
        if encrypted_fields_map:
            validate_is_mapping("encrypted_fields_map", encrypted_fields_map)
        self._encrypted_fields_map = encrypted_fields_map
        self._crypt_shared_lib_path = crypt_shared_lib_path
        self._crypt_shared_lib_required = crypt_shared_lib_required
        self._kms_providers = kms_providers
        self._key_vault_namespace = key_vault_namespace
        self._key_vault_client = key_vault_client
        self._schema_map = schema_map
        self._bypass_auto_encryption = bypass_auto_encryption
        self._mongocryptd_uri = mongocryptd_uri
        self._mongocryptd_bypass_spawn = mongocryptd_bypass_spawn
        self._mongocryptd_spawn_path = mongocryptd_spawn_path
        if mongocryptd_spawn_args is None:
            mongocryptd_spawn_args = ["--idleShutdownTimeoutSecs=60"]
        self._mongocryptd_spawn_args = mongocryptd_spawn_args
        if not isinstance(self._mongocryptd_spawn_args, list):
            raise TypeError(
                f"mongocryptd_spawn_args must be a list, not {type(self._mongocryptd_spawn_args)}"
            )
        if not any("idleShutdownTimeoutSecs" in s for s in self._mongocryptd_spawn_args):
            self._mongocryptd_spawn_args.append("--idleShutdownTimeoutSecs=60")
        # Maps KMS provider name to a SSLContext.
        self._kms_tls_options = kms_tls_options
        self._sync_kms_ssl_contexts: Optional[dict[str, SSLContext]] = None
        self._async_kms_ssl_contexts: Optional[dict[str, SSLContext]] = None
        self._bypass_query_analysis = bypass_query_analysis
        self._key_expiration_ms = key_expiration_ms

    def _kms_ssl_contexts(self, is_sync: bool) -> dict[str, SSLContext]:
        if is_sync:
            if self._sync_kms_ssl_contexts is None:
                self._sync_kms_ssl_contexts = _parse_kms_tls_options(self._kms_tls_options, True)
            return self._sync_kms_ssl_contexts
        else:
            if self._async_kms_ssl_contexts is None:
                self._async_kms_ssl_contexts = _parse_kms_tls_options(self._kms_tls_options, False)
            return self._async_kms_ssl_contexts


class RangeOpts:
    """Options to configure encrypted queries using the range algorithm."""

    def __init__(
        self,
        sparsity: Optional[int] = None,
        trim_factor: Optional[int] = None,
        min: Optional[Any] = None,
        max: Optional[Any] = None,
        precision: Optional[int] = None,
    ) -> None:
        """Options to configure encrypted queries using the range algorithm.

        :param sparsity: An integer.
        :param trim_factor: An integer.
        :param min: A BSON scalar value corresponding to the type being queried.
        :param max: A BSON scalar value corresponding to the type being queried.
        :param precision: An integer, may only be set for double or decimal128 types.

        .. versionadded:: 4.4
        """
        self.min = min
        self.max = max
        self.sparsity = sparsity
        self.trim_factor = trim_factor
        self.precision = precision

    @property
    def document(self) -> dict[str, Any]:
        doc = {}
        for k, v in [
            ("sparsity", int64.Int64(self.sparsity) if self.sparsity else None),
            ("trimFactor", self.trim_factor),
            ("precision", self.precision),
            ("min", self.min),
            ("max", self.max),
        ]:
            if v is not None:
                doc[k] = v
        return doc
