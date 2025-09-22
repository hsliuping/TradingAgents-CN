from unittest import mock

import requests
from update_checker import UpdateChecker, update_check


PACKAGE = "praw"


def mock_response(response, latest_version="5.0.0"):
    response.json = mock.Mock(
        return_value={"releases": {"0.0.1": [], latest_version: []}}
    )
    response.status_code = 200


@mock.patch("requests.get")
def test_checker_check__no_update_to_beta_version(mock_get):
    mock_response(mock_get.return_value, "3.7.0b1")
    checker = UpdateChecker(bypass_cache=True)
    assert checker.check(PACKAGE, "3.6") is None


@mock.patch("requests.get")
def test_checker_check__update_to_beta_version_from_beta_version(mock_get):
    mock_response(mock_get.return_value, "4.0.0b5")
    checker = UpdateChecker(bypass_cache=True)
    result = checker.check(PACKAGE, "4.0.0b4")
    assert result.available_version == "4.0.0b5"


@mock.patch("requests.get")
def test_checker_check__update_to_rc_version_from_beta_version(mock_get):
    mock_response(mock_get.return_value, "4.0.0rc1")
    checker = UpdateChecker(bypass_cache=True)
    result = checker.check(PACKAGE, "4.0.0b4")
    assert result.available_version == "4.0.0rc1"


@mock.patch("requests.get")
def test_checker_check__successful(mock_get):
    mock_response(mock_get.return_value)
    checker = UpdateChecker(bypass_cache=True)
    result = checker.check(PACKAGE, "1.0.0")
    assert result.available_version == "5.0.0"


@mock.patch("requests.get")
def test_checker_check__unsuccessful(mock_get):
    mock_get.side_effect = requests.exceptions.RequestException
    checker = UpdateChecker(bypass_cache=True)
    assert checker.check(PACKAGE, "1.0.0") is None


@mock.patch("requests.get")
def test_update_check__successful__has_no_update(mock_get, capsys):
    mock_response(mock_get.return_value, "0.0.2")
    update_check(PACKAGE, "0.0.2", bypass_cache=True)
    assert "" == capsys.readouterr().err


@mock.patch("requests.get")
def test_update_check__successful__has_update(mock_get, capsys):
    mock_response(mock_get.return_value)
    update_check(PACKAGE, "0.0.1", bypass_cache=True)
    assert (
        "Version 0.0.1 of praw is outdated. Version 5.0.0 is available.\n"
        == capsys.readouterr().err
    )


@mock.patch("requests.get")
def test_update_check__unsuccessful(mock_get, capsys):
    mock_get.side_effect = requests.exceptions.RequestException
    update_check(PACKAGE, "0.0.1", bypass_cache=True)
    assert "" == capsys.readouterr().err
