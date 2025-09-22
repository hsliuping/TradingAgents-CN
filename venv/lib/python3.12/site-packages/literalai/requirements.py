from importlib.metadata import version

from packaging.requirements import Requirement


# Function to check if all packages meet the specified requirements
def check_all_requirements(requirements):
    for req_str in requirements:
        # Parse the requirement string using packaging.requirements.Requirement
        req = Requirement(req_str)

        try:
            # Get the installed version of the package
            installed_version = version(req.name)
        except Exception:
            # Package not installed, return False
            return False

        # Check if the installed version satisfies the requirement
        if not req.specifier.contains(installed_version, prereleases=False):
            # Requirement not met, return False
            return False

    # All requirements were met, return True
    return True
