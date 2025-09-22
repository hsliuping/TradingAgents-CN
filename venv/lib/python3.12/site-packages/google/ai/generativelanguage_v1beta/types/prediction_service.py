# -*- coding: utf-8 -*-
# Copyright 2025 Google LLC
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
#
from __future__ import annotations

from typing import MutableMapping, MutableSequence

from google.protobuf import struct_pb2  # type: ignore
import proto  # type: ignore

__protobuf__ = proto.module(
    package="google.ai.generativelanguage.v1beta",
    manifest={
        "PredictRequest",
        "PredictLongRunningRequest",
        "PredictResponse",
        "PredictLongRunningResponse",
        "PredictLongRunningMetadata",
        "Media",
        "Video",
        "GenerateVideoResponse",
    },
)


class PredictRequest(proto.Message):
    r"""Request message for
    [PredictionService.Predict][google.ai.generativelanguage.v1beta.PredictionService.Predict].

    Attributes:
        model (str):
            Required. The name of the model for prediction. Format:
            ``name=models/{model}``.
        instances (MutableSequence[google.protobuf.struct_pb2.Value]):
            Required. The instances that are the input to
            the prediction call.
        parameters (google.protobuf.struct_pb2.Value):
            Optional. The parameters that govern the
            prediction call.
    """

    model: str = proto.Field(
        proto.STRING,
        number=1,
    )
    instances: MutableSequence[struct_pb2.Value] = proto.RepeatedField(
        proto.MESSAGE,
        number=2,
        message=struct_pb2.Value,
    )
    parameters: struct_pb2.Value = proto.Field(
        proto.MESSAGE,
        number=3,
        message=struct_pb2.Value,
    )


class PredictLongRunningRequest(proto.Message):
    r"""Request message for [PredictionService.PredictLongRunning].

    Attributes:
        model (str):
            Required. The name of the model for prediction. Format:
            ``name=models/{model}``.
        instances (MutableSequence[google.protobuf.struct_pb2.Value]):
            Required. The instances that are the input to
            the prediction call.
        parameters (google.protobuf.struct_pb2.Value):
            Optional. The parameters that govern the
            prediction call.
    """

    model: str = proto.Field(
        proto.STRING,
        number=1,
    )
    instances: MutableSequence[struct_pb2.Value] = proto.RepeatedField(
        proto.MESSAGE,
        number=2,
        message=struct_pb2.Value,
    )
    parameters: struct_pb2.Value = proto.Field(
        proto.MESSAGE,
        number=3,
        message=struct_pb2.Value,
    )


class PredictResponse(proto.Message):
    r"""Response message for [PredictionService.Predict].

    Attributes:
        predictions (MutableSequence[google.protobuf.struct_pb2.Value]):
            The outputs of the prediction call.
    """

    predictions: MutableSequence[struct_pb2.Value] = proto.RepeatedField(
        proto.MESSAGE,
        number=1,
        message=struct_pb2.Value,
    )


class PredictLongRunningResponse(proto.Message):
    r"""Response message for [PredictionService.PredictLongRunning]

    .. _oneof: https://proto-plus-python.readthedocs.io/en/stable/fields.html#oneofs-mutually-exclusive-fields

    Attributes:
        generate_video_response (google.ai.generativelanguage_v1beta.types.GenerateVideoResponse):
            The response of the video generation
            prediction.

            This field is a member of `oneof`_ ``response``.
    """

    generate_video_response: "GenerateVideoResponse" = proto.Field(
        proto.MESSAGE,
        number=1,
        oneof="response",
        message="GenerateVideoResponse",
    )


class PredictLongRunningMetadata(proto.Message):
    r"""Metadata for PredictLongRunning long running operations."""


class Media(proto.Message):
    r"""A proto encapsulate various type of media.

    .. _oneof: https://proto-plus-python.readthedocs.io/en/stable/fields.html#oneofs-mutually-exclusive-fields

    Attributes:
        video (google.ai.generativelanguage_v1beta.types.Video):
            Video as the only one for now.  This is
            mimicking Vertex proto.

            This field is a member of `oneof`_ ``type``.
    """

    video: "Video" = proto.Field(
        proto.MESSAGE,
        number=1,
        oneof="type",
        message="Video",
    )


class Video(proto.Message):
    r"""Representation of a video.

    This message has `oneof`_ fields (mutually exclusive fields).
    For each oneof, at most one member field can be set at the same time.
    Setting any member of the oneof automatically clears all other
    members.

    .. _oneof: https://proto-plus-python.readthedocs.io/en/stable/fields.html#oneofs-mutually-exclusive-fields

    Attributes:
        video (bytes):
            Raw bytes.

            This field is a member of `oneof`_ ``content``.
        uri (str):
            Path to another storage.

            This field is a member of `oneof`_ ``content``.
    """

    video: bytes = proto.Field(
        proto.BYTES,
        number=1,
        oneof="content",
    )
    uri: str = proto.Field(
        proto.STRING,
        number=2,
        oneof="content",
    )


class GenerateVideoResponse(proto.Message):
    r"""Veo response.

    Attributes:
        generated_samples (MutableSequence[google.ai.generativelanguage_v1beta.types.Media]):
            The generated samples.
        rai_media_filtered_count (int):
            Returns if any videos were filtered due to
            RAI policies.
        rai_media_filtered_reasons (MutableSequence[str]):
            Returns rai failure reasons if any.
    """

    generated_samples: MutableSequence["Media"] = proto.RepeatedField(
        proto.MESSAGE,
        number=1,
        message="Media",
    )
    rai_media_filtered_count: int = proto.Field(
        proto.INT32,
        number=2,
    )
    rai_media_filtered_reasons: MutableSequence[str] = proto.RepeatedField(
        proto.STRING,
        number=3,
    )


__all__ = tuple(sorted(__protobuf__.manifest))
