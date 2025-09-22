from typing import Callable, Optional
from typing_extensions import Coroutine


class Config:
    enrich_token_usage = False
    exception_logger = None
    get_common_metrics_attributes: Callable[[], dict] = lambda: {}
    upload_base64_image: Optional[
        Callable[[str, str, str, str], Coroutine[None, None, str]]
    ] = None
