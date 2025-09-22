from __future__ import annotations

import base64
import mimetypes
import os
import re
from enum import Enum
from typing import Any, Dict
from urllib.parse import urlparse

import filetype  # type: ignore[import]
import requests
from google.ai.generativelanguage_v1beta.types import Part


class Route(Enum):
    """Image Loading Route"""

    BASE64 = 1
    LOCAL_FILE = 2
    URL = 3


class ImageBytesLoader:
    """Loads image bytes from multiple sources given a string.

    Currently supported:
        - B64 Encoded image string
        - URL
    """

    def load_bytes(self, image_string: str) -> bytes:
        """Routes to the correct loader based on the ``'image_string'``.

        Args:
            image_string: Can be either:
                    - B64 Encoded image string
                    - URL

        Returns:
            Image bytes.
        """

        route = self._route(image_string)

        if route == Route.BASE64:
            return self._bytes_from_b64(image_string)

        if route == Route.URL:
            return self._bytes_from_url(image_string)

        if route == Route.LOCAL_FILE:
            raise ValueError(
                "Loading from local files is no longer supported for security reasons. "
                "Please pass in images as Google Cloud Storage URI, "
                "b64 encoded image string (data:image/...), or valid image url."
            )
            return self._bytes_from_file(image_string)

        raise ValueError(
            "Image string must be one of: Google Cloud Storage URI, "
            "b64 encoded image string (data:image/...), or valid image url."
            f"Instead got '{image_string}'."
        )

    def load_part(self, image_string: str) -> Part:
        """Gets Part for loading from Gemini.

        Args:
            image_string: Can be either:
                    - B64 Encoded image string
                    - URL
        """
        route = self._route(image_string)

        if route == Route.BASE64:
            bytes_ = self._bytes_from_b64(image_string)

        if route == Route.URL:
            bytes_ = self._bytes_from_url(image_string)

        if route == Route.LOCAL_FILE:
            msg = (
                "Loading from local files is no longer supported for security reasons. "
                "Please specify images as Google Cloud Storage URI, "
                "b64 encoded image string (data:image/...), or valid image url."
            )
            raise ValueError(msg)

        inline_data: Dict[str, Any] = {"data": bytes_}

        mime_type, _ = mimetypes.guess_type(image_string)
        if not mime_type:
            kind = filetype.guess(bytes_)
            if kind:
                mime_type = kind.mime

        if mime_type:
            inline_data["mime_type"] = mime_type

        return Part(inline_data=inline_data)

    def _route(self, image_string: str) -> Route:
        if image_string.startswith("data:image/"):
            return Route.BASE64

        if self._is_url(image_string):
            return Route.URL

        if os.path.exists(image_string):
            return Route.LOCAL_FILE

        raise ValueError(
            "Image string must be one of: "
            "b64 encoded image string (data:image/...) or valid image url."
            f" Instead got '{image_string}'."
        )

    def _bytes_from_b64(self, base64_image: str) -> bytes:
        """Gets image bytes from a base64 encoded string.

        Args:
            base64_image: Encoded image in b64 format.

        Returns:
            Image bytes
        """

        pattern = r"data:image/\w{2,4};base64,(.*)"
        match = re.search(pattern, base64_image)

        if match is not None:
            encoded_string = match.group(1)
            return base64.b64decode(encoded_string)

        raise ValueError(f"Error in b64 encoded image. Must follow pattern: {pattern}")

    def _bytes_from_url(self, url: str) -> bytes:
        """Gets image bytes from a public url.

        Args:
            url: Valid url.

        Raises:
            HTTP Error if there is one.

        Returns:
            Image bytes
        """

        response = requests.get(url)

        if not response.ok:
            response.raise_for_status()

        return response.content

    def _is_url(self, url_string: str) -> bool:
        """Checks if a url is valid.

        Args:
            url_string: Url to check.

        Returns:
            Whether the url is valid.
        """
        try:
            result = urlparse(url_string)
            return all([result.scheme, result.netloc])
        except Exception:
            return False


def image_bytes_to_b64_string(
    image_bytes: bytes, encoding: str = "ascii", image_format: str = "png"
) -> str:
    """Encodes image bytes into a b64 encoded string.

    Args:
        image_bytes: Bytes of the image.
        encoding: Type of encoding in the string. ``'ascii'`` by default.
        image_format: Format of the image. ``'png'`` by default.

    Returns:
        B64 image encoded string.
    """
    encoded_bytes = base64.b64encode(image_bytes).decode(encoding)
    return f"data:image/{image_format};base64,{encoded_bytes}"
