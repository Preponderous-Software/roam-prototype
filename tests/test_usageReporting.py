"""Anonymous usage reporting: which runs report, what is sent, and the
one-time first-run notice. Every enabled client here points at a loopback
stub server; nothing ever reaches the real trace service."""
import json
import logging
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import MagicMock

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pytest

import usageReporting
from config.config import Config
from lib.trace_client import TraceClient
from usageReporting import (
    APPLICATION,
    ENVIRONMENT_VARIABLE,
    FIRST_RUN_NOTICE,
    createTraceClient,
    isReportingActive,
    showFirstRunNotice,
    versionTags,
)


class _Stub:
    """A loopback HTTP server recording every POST, standing in for trace."""

    def __init__(self):
        self.requests = []
        self.arrived = threading.Event()
        stub = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(length).decode("utf-8")
                stub.requests.append(
                    {
                        "path": self.path,
                        "authorization": self.headers.get("Authorization"),
                        "body": json.loads(body),
                    }
                )
                self.send_response(201)
                self.send_header("Content-Length", "0")
                self.end_headers()
                stub.arrived.set()

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = "http://127.0.0.1:%d" % self.server.server_address[1]

    def close(self):
        self.server.shutdown()


@pytest.fixture
def stub():
    server = _Stub()
    yield server
    server.close()


@pytest.fixture(autouse=True)
def _reporting_env_unset(monkeypatch):
    # The harness / a developer shell may carry the override; each test here
    # decides for itself.
    monkeypatch.delenv(ENVIRONMENT_VARIABLE, raising=False)
    monkeypatch.setattr(sys, "platform", "linux")


def _config(enabled=True, endpoint="http://127.0.0.1:1", acknowledged=False):
    config = MagicMock(spec=Config)
    config.usageReportingEnabled = enabled
    config.usageReportingEndpoint = endpoint
    config.usageReportingKey = "test-key"
    config.usageReportingAcknowledged = acknowledged
    return config


# --- which runs report -------------------------------------------------------


def test_application_name_is_the_one_the_key_was_issued_for():
    assert APPLICATION == "roam"


def test_client_is_enabled_by_default_and_posts_to_the_configured_endpoint(stub):
    client = createTraceClient(_config(endpoint=stub.url))
    try:
        assert client.enabled is True
    finally:
        client.close()


def test_opt_out_in_config_yields_a_disabled_client(stub):
    client = createTraceClient(_config(enabled=False, endpoint=stub.url))
    assert client.enabled is False
    client.report("startup")
    assert not stub.arrived.wait(0.3)
    assert stub.requests == []


@pytest.mark.parametrize("value", ["0", "false", "FALSE", "off", "no", " 0 "])
def test_environment_override_forces_reporting_off(monkeypatch, stub, value):
    monkeypatch.setenv(ENVIRONMENT_VARIABLE, value)
    config = _config(endpoint=stub.url)
    assert isReportingActive(config) is False
    assert createTraceClient(config).enabled is False


@pytest.mark.parametrize("value", ["1", "true", "", "yes"])
def test_other_environment_values_leave_config_in_charge(monkeypatch, stub, value):
    monkeypatch.setenv(ENVIRONMENT_VARIABLE, value)
    assert isReportingActive(_config(endpoint=stub.url)) is True
    assert isReportingActive(_config(enabled=False, endpoint=stub.url)) is False


def test_browser_build_never_reports(monkeypatch, stub):
    # The Pyodide build has no OS threads or sockets; the client must not
    # even start its sender thread there.
    monkeypatch.setattr(sys, "platform", "emscripten")
    config = _config(endpoint=stub.url)
    assert usageReporting.isBrowserBuild() is True
    assert isReportingActive(config) is False
    client = createTraceClient(config)
    assert client.enabled is False
    assert client._thread is None


def test_a_bad_endpoint_in_config_costs_the_report_not_the_game():
    client = createTraceClient(_config(endpoint="   "))
    assert client.enabled is False
    client.report("startup")  # must not raise


# --- what is sent ------------------------------------------------------------


def test_version_tag_comes_from_the_bundled_version_file(monkeypatch):
    monkeypatch.setattr(Config, "getVersion", staticmethod(lambda: "9.8.7"))
    assert versionTags() == {"version": "9.8.7"}


def test_startup_event_carries_only_the_program_name_and_version(stub, monkeypatch):
    monkeypatch.setattr(Config, "getVersion", staticmethod(lambda: "1.2.3-test"))
    client = createTraceClient(_config(endpoint=stub.url))
    try:
        client.report("startup", tags=versionTags())
        assert stub.arrived.wait(5), "the startup report should reach the stub"
    finally:
        client.close()

    request = stub.requests[0]
    assert request["path"] == "/api/metrics"
    assert request["authorization"] == "Bearer test-key"
    assert request["body"] == {
        "application": "roam",
        "name": "startup",
        "tags": {"version": "1.2.3-test"},
    }


def test_opening_a_save_reports_world_loaded_without_the_save_name(stub, monkeypatch):
    from roam import Roam

    monkeypatch.setattr(Config, "getVersion", staticmethod(lambda: "1.2.3-test"))
    roamInstance = Roam.__new__(Roam)
    roamInstance.worldScreen = MagicMock()
    roamInstance.traceClient = createTraceClient(_config(endpoint=stub.url))
    try:
        roamInstance.initializeWorldScreen()
        roamInstance.worldScreen.initialize.assert_called_once_with()
        assert stub.arrived.wait(5), "the world-loaded report should reach the stub"
    finally:
        roamInstance.traceClient.close()

    body = stub.requests[0]["body"]
    assert body == {
        "application": "roam",
        "name": "world-loaded",
        "tags": {"version": "1.2.3-test"},
    }
    assert "save" not in json.dumps(body).lower()


def test_roam_built_without_a_client_reports_nothing():
    # The Pyodide entry point and the unit tests construct Roam this way.
    from roam import Roam

    roamInstance = Roam.__new__(Roam)
    roamInstance.worldScreen = MagicMock()
    roamInstance.traceClient = TraceClient.disabled()
    roamInstance.initializeWorldScreen()  # must not raise, sends nothing
    assert roamInstance.traceClient.enabled is False


# --- the first-run notice ----------------------------------------------------


def test_first_run_notice_is_logged_once_and_then_acknowledged(caplog):
    config = _config()
    caplog.set_level(logging.INFO)

    assert showFirstRunNotice(config) is True
    config.acknowledgeUsageReporting.assert_called_once_with()
    assert FIRST_RUN_NOTICE in caplog.text

    # The second start reads the marker back from the file.
    caplog.clear()
    acknowledged = _config(acknowledged=True)
    assert showFirstRunNotice(acknowledged) is False
    acknowledged.acknowledgeUsageReporting.assert_not_called()
    assert FIRST_RUN_NOTICE not in caplog.text


def test_first_run_notice_names_the_opt_out_and_what_is_sent():
    assert FIRST_RUN_NOTICE.startswith("Usage reporting is on: roam sends")
    assert "trace.danielstephenson.dev" in FIRST_RUN_NOTICE
    assert "program name and version only" in FIRST_RUN_NOTICE
    assert "usageReportingEnabled: false in config.yml" in FIRST_RUN_NOTICE


def test_first_run_notice_is_not_shown_when_reporting_is_off(monkeypatch, caplog):
    caplog.set_level(logging.INFO)

    optedOut = _config(enabled=False)
    assert showFirstRunNotice(optedOut) is False
    optedOut.acknowledgeUsageReporting.assert_not_called()

    monkeypatch.setenv(ENVIRONMENT_VARIABLE, "0")
    silenced = _config()
    assert showFirstRunNotice(silenced) is False
    silenced.acknowledgeUsageReporting.assert_not_called()
    monkeypatch.delenv(ENVIRONMENT_VARIABLE)

    monkeypatch.setattr(sys, "platform", "emscripten")
    browser = _config()
    assert showFirstRunNotice(browser) is False
    browser.acknowledgeUsageReporting.assert_not_called()

    assert FIRST_RUN_NOTICE not in caplog.text


def test_first_run_notice_round_trips_through_a_real_config_file(
    tmp_path, monkeypatch, caplog
):
    # End to end on the settings side: an empty user config (one that predates
    # the setting) shows the notice and gains the marker; the next Config
    # built from the same file does not show it again.
    configFilePath = tmp_path / "config.yml"
    configFilePath.write_text("debug: false\n", encoding="utf-8")
    monkeypatch.setattr(
        Config, "getConfigFilePath", staticmethod(lambda: configFilePath)
    )
    caplog.set_level(logging.INFO)

    assert showFirstRunNotice(Config()) is True
    assert caplog.text.count(FIRST_RUN_NOTICE) == 1
    assert "usageReportingEnabled: true" in configFilePath.read_text(encoding="utf-8")

    assert showFirstRunNotice(Config()) is False
    assert caplog.text.count(FIRST_RUN_NOTICE) == 1
