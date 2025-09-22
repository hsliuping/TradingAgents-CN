from redis._parsers.helpers import pairs_to_dict
from redis.commands.vectorset.commands import CallbacksOptions


def parse_vemb_result(response, **options):
    """
    Handle VEMB result since the command can returning different result
    structures depending on input options and on quantization type of the vector set.

    Parsing VEMB result into:
    - List[Union[bytes, Union[int, float]]]
    - Dict[str, Union[bytes, str, float]]
    """
    if response is None:
        return response

    if options.get(CallbacksOptions.RAW.value):
        result = {}
        result["quantization"] = (
            response[0].decode("utf-8")
            if options.get(CallbacksOptions.ALLOW_DECODING.value)
            else response[0]
        )
        result["raw"] = response[1]
        result["l2"] = float(response[2])
        if len(response) > 3:
            result["range"] = float(response[3])
        return result
    else:
        if options.get(CallbacksOptions.RESP3.value):
            return response

        result = []
        for i in range(len(response)):
            try:
                result.append(int(response[i]))
            except ValueError:
                # if the value is not an integer, it should be a float
                result.append(float(response[i]))

        return result


def parse_vlinks_result(response, **options):
    """
    Handle VLINKS result since the command can be returning different result
    structures depending on input options.
    Parsing VLINKS result into:
    - List[List[str]]
    - List[Dict[str, Number]]
    """
    if response is None:
        return response

    if options.get(CallbacksOptions.WITHSCORES.value):
        result = []
        # Redis will return a list of list of strings.
        # This list have to be transformed to list of dicts
        for level_item in response:
            level_data_dict = {}
            for key, value in pairs_to_dict(level_item).items():
                value = float(value)
                level_data_dict[key] = value
            result.append(level_data_dict)
        return result
    else:
        # return the list of elements for each level
        # list of lists
        return response


def parse_vsim_result(response, **options):
    """
    Handle VSIM result since the command can be returning different result
    structures depending on input options.
    Parsing VSIM result into:
    - List[List[str]]
    - List[Dict[str, Number]]
    """
    if response is None:
        return response

    if options.get(CallbacksOptions.WITHSCORES.value):
        # Redis will return a list of list of pairs.
        # This list have to be transformed to dict
        result_dict = {}
        for key, value in pairs_to_dict(response).items():
            value = float(value)
            result_dict[key] = value
        return result_dict
    else:
        # return the list of elements for each level
        # list of lists
        return response
