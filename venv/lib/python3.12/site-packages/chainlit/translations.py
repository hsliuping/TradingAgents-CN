# TODO:
# - Support linting plural
# - Support interpolation


def compare_json_structures(truth, to_compare, path=""):
    """
    Compare the structure of two deeply nested JSON objects.
    Args:
        truth (dict): The 'truth' JSON object.
        to_compare (dict): The 'to_compare' JSON object.
        path (str): The current path for error reporting (used internally).
    Returns:
        A list of differences found.
    """
    if not isinstance(truth, dict) or not isinstance(to_compare, dict):
        raise ValueError("Both inputs must be dictionaries.")

    errors = []

    truth_keys = set(truth.keys())
    to_compare_keys = set(to_compare.keys())

    extra_keys = to_compare_keys - truth_keys
    missing_keys = truth_keys - to_compare_keys

    for key in extra_keys:
        errors.append(f"⚠️ Extra key: '{path + '.' + key if path else key}'")

    for key in missing_keys:
        errors.append(f"❌ Missing key: '{path + '.' + key if path else key}'")

    for key in truth_keys & to_compare_keys:
        if isinstance(truth[key], dict) and isinstance(to_compare[key], dict):
            # Recursive call to navigate through nested dictionaries
            errors += compare_json_structures(
                truth[key], to_compare[key], path + "." + key if path else key
            )
        elif not isinstance(truth[key], dict) and not isinstance(to_compare[key], dict):
            # If both are not dicts, we are at leaf nodes and structure matches; skip value comparison
            continue
        else:
            # Structure mismatch: one is a dict, the other is not
            errors.append(
                f"❌ Structure mismatch at: '{path + '.' + key if path else key}'"
            )

    return errors


def lint_translation_json(file, truth, to_compare):
    print(f"\nLinting {file}...")

    errors = compare_json_structures(truth, to_compare)

    if errors:
        for error in errors:
            print(f"{error}")
    else:
        print(f"✅ No errors found in {file}")
