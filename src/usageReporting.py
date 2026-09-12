# @author Claude
# @since September 11th, 2026
"""Anonymous usage reporting to the trace service.

Roam reports two events to https://trace.danielstephenson.dev so the number
of installations actually being played can be seen: ``startup`` once per
launch and ``world-loaded`` each time a save is opened. Each carries the
program name ("roam") and the game version — nothing else. No usernames,
hostnames, IPs, paths or save names are ever sent.

The transport is the vendored ``lib.trace_client`` (standard library only),
which posts from a single daemon thread, never raises into the game, and
drops reports rather than queueing more than a few hundred. Reporting is on
by default and turned off with ``usageReportingEnabled: false`` in
config.yml. It is never on in the browser (Pyodide) build, which has no real
threads or sockets, and it can be forced off for a process with the
``ROAM_USAGE_REPORTING=0`` environment variable — the test harness does that
so a test run is never counted as a player.
"""
import os
import sys

from config.config import Config
from gameLogging.logger import getLogger
from lib.trace_client import TraceClient

_logger = getLogger(__name__)

# The program name the trace key was issued for. Not the display name.
APPLICATION = "roam"

# Environment override, for test harnesses and containers: any of these values
# (case-insensitive) forces reporting off regardless of config.yml.
ENVIRONMENT_VARIABLE = "ROAM_USAGE_REPORTING"
_OFF_VALUES = frozenset({"0", "false", "off", "no"})

OPT_OUT_INSTRUCTION = "usageReportingEnabled: false in config.yml"

FIRST_RUN_NOTICE = (
    "Usage reporting is on: roam sends a startup event and a world-loaded "
    "event (program name and version only) to trace.danielstephenson.dev. "
    "Turn it off with " + OPT_OUT_INSTRUCTION + "."
)


def isBrowserBuild():
    # The Pyodide build runs the same sources under Emscripten, where there
    # are no OS threads and no sockets; the client must not even be started.
    return sys.platform == "emscripten"


def isDisabledByEnvironment():
    value = os.environ.get(ENVIRONMENT_VARIABLE)
    if value is None:
        return False
    return value.strip().lower() in _OFF_VALUES


def isReportingActive(config):
    """Whether this process reports at all: on in config, not the browser
    build, and not switched off through the environment."""
    return (
        bool(config.usageReportingEnabled)
        and not isBrowserBuild()
        and not isDisabledByEnvironment()
    )


def createTraceClient(config):
    """Build the client for this run. Returns a disabled client (which does
    nothing and starts no thread) whenever reporting is not active, and never
    raises: a bad endpoint or key in config.yml costs the report, not the
    game."""
    if not isReportingActive(config):
        return TraceClient.disabled()
    try:
        return TraceClient(
            config.usageReportingEndpoint,
            APPLICATION,
            key=config.usageReportingKey,
            enabled=True,
        )
    except Exception as failure:  # noqa: BLE001 - reporting must never stop the game
        _logger.warning("usage reporting could not be started", error=str(failure))
        return TraceClient.disabled()


def showFirstRunNotice(config):
    """Log the one-line notice the first time the game starts with reporting
    active and no usageReporting* setting in the config file yet, then write
    the setting so the notice is not shown again. Returns True when shown."""
    if not isReportingActive(config) or config.usageReportingAcknowledged:
        return False
    _logger.info(FIRST_RUN_NOTICE)
    config.acknowledgeUsageReporting()
    return True


def versionTags():
    return {"version": Config.getVersion()}
