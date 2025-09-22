import copy
import random
import string
from typing import List, Tuple

import redis
from redis.typing import KeysT, KeyT


def list_or_args(keys: KeysT, args: Tuple[KeyT, ...]) -> List[KeyT]:
    # returns a single new list combining keys and args
    try:
        iter(keys)
        # a string or bytes instance can be iterated, but indicates
        # keys wasn't passed as a list
        if isinstance(keys, (bytes, str)):
            keys = [keys]
        else:
            keys = list(keys)
    except TypeError:
        keys = [keys]
    if args:
        keys.extend(args)
    return keys


def nativestr(x):
    """Return the decoded binary string, or a string, depending on type."""
    r = x.decode("utf-8", "replace") if isinstance(x, bytes) else x
    if r == "null":
        return
    return r


def delist(x):
    """Given a list of binaries, return the stringified version."""
    if x is None:
        return x
    return [nativestr(obj) for obj in x]


def parse_to_list(response):
    """Optimistically parse the response to a list."""
    res = []

    special_values = {"infinity", "nan", "-infinity"}

    if response is None:
        return res

    for item in response:
        if item is None:
            res.append(None)
            continue
        try:
            item_str = nativestr(item)
        except TypeError:
            res.append(None)
            continue

        if isinstance(item_str, str) and item_str.lower() in special_values:
            res.append(item_str)  # Keep as string
        else:
            try:
                res.append(int(item))
            except ValueError:
                try:
                    res.append(float(item))
                except ValueError:
                    res.append(item_str)

    return res


def parse_list_to_dict(response):
    res = {}
    for i in range(0, len(response), 2):
        if isinstance(response[i], list):
            res["Child iterators"].append(parse_list_to_dict(response[i]))
            try:
                if isinstance(response[i + 1], list):
                    res["Child iterators"].append(parse_list_to_dict(response[i + 1]))
            except IndexError:
                pass
        elif isinstance(response[i + 1], list):
            res["Child iterators"] = [parse_list_to_dict(response[i + 1])]
        else:
            try:
                res[response[i]] = float(response[i + 1])
            except (TypeError, ValueError):
                res[response[i]] = response[i + 1]
    return res


def random_string(length=10):
    """
    Returns a random N character long string.
    """
    return "".join(  # nosec
        random.choice(string.ascii_lowercase) for x in range(length)
    )


def decode_dict_keys(obj):
    """Decode the keys of the given dictionary with utf-8."""
    newobj = copy.copy(obj)
    for k in obj.keys():
        if isinstance(k, bytes):
            newobj[k.decode("utf-8")] = newobj[k]
            newobj.pop(k)
    return newobj


def get_protocol_version(client):
    if isinstance(client, redis.Redis) or isinstance(client, redis.asyncio.Redis):
        return client.connection_pool.connection_kwargs.get("protocol")
    elif isinstance(client, redis.cluster.AbstractRedisCluster):
        return client.nodes_manager.connection_kwargs.get("protocol")
