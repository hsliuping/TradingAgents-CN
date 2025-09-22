from chainlit.utils import check_module_version

if not check_module_version("langflow", "0.1.4"):
    raise ValueError(
        "Expected Langflow version >= 0.1.4. Run `pip install langflow --upgrade`"
    )

from typing import Dict, Optional, Union

import httpx


async def load_flow(schema: Union[Dict, str], tweaks: Optional[Dict] = None):
    from langflow import load_flow_from_json

    if isinstance(schema, str):
        async with httpx.AsyncClient() as client:
            response = await client.get(schema)
            if response.status_code != 200:
                raise ValueError(f"Error: {response.text}")
            schema = response.json()

    flow = load_flow_from_json(flow=schema, tweaks=tweaks)

    return flow
