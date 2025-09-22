import pytest

from literalai.api import LiteralAPI
from literalai.cache.prompt_helpers import put_prompt
from literalai.cache.shared_cache import SharedCache
from literalai.prompt_engineering.prompt import Prompt


def default_prompt(id: str = "1", name: str = "test", version: int = 1) -> Prompt:
    return Prompt(
        api=LiteralAPI(),
        id=id,
        name=name,
        version=version,
        created_at="",
        updated_at="",
        type="chat",  # type: ignore
        url="",
        version_desc=None,
        template_messages=[],
        tools=None,
        provider="",
        settings={},
        variables=[],
        variables_default_values=None,
    )


def test_singleton_instance():
    """Test that SharedCache maintains singleton pattern"""
    cache1 = SharedCache()
    cache2 = SharedCache()
    assert cache1 is cache2


def test_get_empty_cache():
    """Test getting from empty cache returns None"""
    cache = SharedCache()
    cache.clear()

    assert cache.get_cache() == {}


def test_put_and_get_prompt_by_id_by_name_version_by_name():
    """Test storing and retrieving prompt by ID by name-version by name"""
    cache = SharedCache()
    cache.clear()

    prompt = default_prompt()
    put_prompt(cache, prompt)

    retrieved_by_id = cache.get(id="1")
    assert retrieved_by_id is prompt

    retrieved_by_name_version = cache.get(name="test", version=1)
    assert retrieved_by_name_version is prompt

    retrieved_by_name = cache.get(name="test")
    assert retrieved_by_name is prompt


def test_clear_cache():
    """Test clearing the cache"""
    cache = SharedCache()
    prompt = default_prompt()
    put_prompt(cache, prompt)

    cache.clear()
    assert cache.get_cache() == {}


def test_update_existing_prompt():
    """Test updating an existing prompt"""
    cache = SharedCache()
    cache.clear()

    prompt1 = default_prompt()
    prompt2 = default_prompt(id="1", version=2)

    cache.put_prompt(prompt1)
    cache.put_prompt(prompt2)

    retrieved = cache.get(id="1")
    assert retrieved is prompt2
    assert retrieved.version == 2


def test_error_handling():
    """Test error handling for invalid inputs"""
    cache = SharedCache()
    cache.clear()

    assert cache.get_cache() == {}
    assert cache.get(key="") is None

    with pytest.raises(TypeError):
        cache.get(5)  # type: ignore

    with pytest.raises(TypeError):
        cache.put(5, "test")  # type: ignore
