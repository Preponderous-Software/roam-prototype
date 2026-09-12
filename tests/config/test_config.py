import os
import sys

os.environ["SDL_VIDEODRIVER"] = "dummy"
import pygame
import pytest

from src.appPaths import getBundleDirectory
from src.config.config import Config


@pytest.fixture(scope="module", autouse=True)
def init_pygame():
    pygame.init()
    yield
    pygame.quit()


@pytest.fixture(autouse=True)
def isolate_config_file(tmp_path, monkeypatch):
    configFilePath = tmp_path / "config.yml"
    configFilePath.write_text("", encoding="utf-8")
    monkeypatch.setattr(
        Config, "getConfigFilePath", staticmethod(lambda: configFilePath)
    )


def test_init_brings_up_display_when_video_not_initialized():
    # Regression: Config is constructed before the frontend initializes pygame,
    # so the video subsystem may be down. Config must bring up the display
    # itself rather than raising "video system not initialized".
    pygame.display.quit()
    assert not pygame.display.get_init()

    config = Config()  # must not raise pygame.error

    assert pygame.display.get_init()
    assert config.displayHeight > 0
    assert config.displayWidth > 0


def test_defaults():
    config = Config()

    assert config.debug == True
    assert config.fullscreen == False
    assert config.autoEatFoodInInventory == True
    assert config.removeDeadEntities == True
    assert config.showMiniMap == True
    assert config.cameraFollowPlayer == True
    assert config.limitTps == True
    assert config.dayNightCycleEnabled == True
    assert config.dayNightCycleLengthTicks == 54000
    assert config.pushableStone == True


def test_saves_base_directory_is_relative_on_non_windows(monkeypatch):
    monkeypatch.setattr(os, "name", "posix")
    monkeypatch.setattr(sys, "platform", "linux")
    assert Config.getSavesBaseDirectory() == "saves"


def test_saves_base_directory_uses_application_support_on_macos(monkeypatch):
    monkeypatch.setattr(os, "name", "posix")
    monkeypatch.setattr(sys, "platform", "darwin")
    assert Config.getSavesBaseDirectory() == os.path.join(
        Config.getUserDataDirectory(), "saves"
    )


def test_saves_base_directory_uses_appdata_on_windows(monkeypatch):
    monkeypatch.setattr(os, "name", "nt")
    appData = os.path.join(os.sep, "fake", "AppData", "Roaming")
    monkeypatch.setenv("APPDATA", appData)
    assert Config.getSavesBaseDirectory() == os.path.join(appData, "Roam", "saves")


def test_saves_base_directory_falls_back_when_appdata_missing(monkeypatch):
    monkeypatch.setattr(os, "name", "nt")
    monkeypatch.delenv("APPDATA", raising=False)
    assert Config.getSavesBaseDirectory() == "saves"


def test_default_save_directory_is_under_saves_base(monkeypatch):
    monkeypatch.setattr(os, "name", "posix")
    monkeypatch.setattr(sys, "platform", "linux")
    assert Config.getDefaultSaveDirectory() == os.path.join("saves", "defaultsavefile")


def test_config_uses_platform_default_save_directory(monkeypatch):
    # With no explicit pathToSaveDirectory in config.yml (isolate_config_file
    # writes an empty file), the platform default save directory is used.
    monkeypatch.setattr(os, "name", "posix")
    monkeypatch.setattr(sys, "platform", "linux")
    config = Config()
    assert config.pathToSaveDirectory == os.path.join("saves", "defaultsavefile")


def test_get_version_reads_bundled_version_file(monkeypatch, tmp_path):
    (tmp_path / "version.txt").write_text("1.2.3", encoding="utf-8")
    monkeypatch.setattr("src.config.config.getBundleDirectory", lambda: str(tmp_path))
    assert Config.getVersion() == "1.2.3"


def test_get_version_returns_unknown_when_missing(monkeypatch, tmp_path):
    monkeypatch.setattr("src.config.config.getBundleDirectory", lambda: str(tmp_path))
    assert Config.getVersion() == "unknown"


def test_user_data_directory_is_bundle_dir_from_source(monkeypatch):
    monkeypatch.setattr(os, "name", "posix")
    monkeypatch.setattr(sys, "platform", "linux")
    assert Config.getUserDataDirectory() == getBundleDirectory()


def test_user_data_directory_uses_application_support_on_macos(monkeypatch):
    monkeypatch.setattr(os, "name", "posix")
    monkeypatch.setattr(sys, "platform", "darwin")
    expected = os.path.join(
        os.path.expanduser("~"), "Library", "Application Support", "Roam"
    )
    assert Config.getUserDataDirectory() == expected


def test_user_data_directory_uses_appdata_on_windows(monkeypatch):
    monkeypatch.setattr(os, "name", "nt")
    appData = os.path.join(os.sep, "fake", "AppData", "Roaming")
    monkeypatch.setenv("APPDATA", appData)
    assert Config.getUserDataDirectory() == os.path.join(appData, "Roam")


def test_user_data_directory_falls_back_when_appdata_missing(monkeypatch):
    monkeypatch.setattr(os, "name", "nt")
    monkeypatch.delenv("APPDATA", raising=False)
    assert Config.getUserDataDirectory() == getBundleDirectory()


def test_ensure_user_config_seeds_from_bundled(monkeypatch, tmp_path):
    bundled = tmp_path / "bundle" / "config.yml"
    bundled.parent.mkdir()
    bundled.write_text("debug: false\n", encoding="utf-8")
    user = tmp_path / "user" / "config.yml"
    monkeypatch.setattr(Config, "getConfigFilePath", staticmethod(lambda: user))
    monkeypatch.setattr(
        Config, "getBundledConfigFilePath", staticmethod(lambda: bundled)
    )

    Config.ensureUserConfigExists()

    assert user.exists()
    assert user.read_text(encoding="utf-8") == "debug: false\n"


def test_ensure_user_config_noop_when_same_file(monkeypatch, tmp_path):
    # Use a subpath so it doesn't collide with the autouse fixture's
    # tmp_path/config.yml.
    same = tmp_path / "sub" / "config.yml"
    monkeypatch.setattr(Config, "getConfigFilePath", staticmethod(lambda: same))
    monkeypatch.setattr(Config, "getBundledConfigFilePath", staticmethod(lambda: same))

    Config.ensureUserConfigExists()

    assert not same.exists()


def test_ensure_user_config_noop_when_user_already_exists(monkeypatch, tmp_path):
    bundled = tmp_path / "bundled.yml"
    bundled.write_text("debug: false\n", encoding="utf-8")
    user = tmp_path / "user.yml"
    user.write_text("debug: true\n", encoding="utf-8")
    monkeypatch.setattr(Config, "getConfigFilePath", staticmethod(lambda: user))
    monkeypatch.setattr(
        Config, "getBundledConfigFilePath", staticmethod(lambda: bundled)
    )

    Config.ensureUserConfigExists()

    assert user.read_text(encoding="utf-8") == "debug: true\n"


def test_toggle_camera_follow_player():
    config = Config()

    assert config.cameraFollowPlayer == True
    config.cameraFollowPlayer = False
    assert config.cameraFollowPlayer == False
    config.cameraFollowPlayer = True
    assert config.cameraFollowPlayer == True


def test_toggle_limit_tps():
    config = Config()

    assert config.limitTps == True
    config.limitTps = False
    assert config.limitTps == False
    config.limitTps = True
    assert config.limitTps == True


def test_toggle_pushable_stone():
    config = Config()

    assert config.pushableStone == True
    config.pushableStone = False
    assert config.pushableStone == False
    config.pushableStone = True
    assert config.pushableStone == True


def test_reads_values_from_config_file(tmp_path, monkeypatch):
    configFilePath = tmp_path / "config.yml"
    configFilePath.write_text(
        (
            "debug: false\n"
            "fullscreen: true\n"
            "cameraFollowPlayer: false\n"
            "limitTps: false\n"
            "pushableStone: false\n"
            "playerMovementEnergyCost: 0.75\n"
            "pathToSaveDirectory: saves/custom\n"
            "black: [1, 2, 3]\n"
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        Config, "getConfigFilePath", staticmethod(lambda: configFilePath)
    )

    config = Config()

    assert not config.debug
    assert config.fullscreen
    assert not config.cameraFollowPlayer
    assert not config.limitTps
    assert not config.pushableStone
    assert config.playerMovementEnergyCost == 0.75
    assert config.pathToSaveDirectory == "saves/custom"
    assert config.black == (1, 2, 3)


def test_handles_read_errors_with_defaults(tmp_path, monkeypatch):
    # Point the config path at a directory: it "exists" but open() raises
    # IsADirectoryError (an OSError), so Config must fall back to defaults.
    unreadable = tmp_path / "config_dir"
    unreadable.mkdir()
    monkeypatch.setattr(Config, "getConfigFilePath", staticmethod(lambda: unreadable))

    config = Config()

    assert config.debug
    assert config.black == (0, 0, 0)


def test_ignores_invalid_or_empty_values(tmp_path, monkeypatch):
    configFilePath = tmp_path / "config.yml"
    configFilePath.write_text(
        (
            "debug:\n"
            "ticksPerSecond: fast\n"
            "black: none\n"
            "pathToSaveDirectory:\n"
            "displayWidth: none\n"
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        Config, "getConfigFilePath", staticmethod(lambda: configFilePath)
    )

    config = Config()

    assert config.debug
    assert config.ticksPerSecond == 30
    assert config.black == (0, 0, 0)
    # An empty pathToSaveDirectory falls back to the platform default, which is
    # the %APPDATA% path on Windows and "saves/defaultsavefile" elsewhere.
    assert config.pathToSaveDirectory == Config.getDefaultSaveDirectory()
    assert config.displayWidth == config.displayHeight


def test_preserves_hash_character_in_quoted_strings(tmp_path, monkeypatch):
    configFilePath = tmp_path / "config.yml"
    configFilePath.write_text(
        ('pathToSaveDirectory: "saves/#1" # keep this value\n' "debug: true\n"),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        Config, "getConfigFilePath", staticmethod(lambda: configFilePath)
    )

    config = Config()

    assert config.pathToSaveDirectory == "saves/#1"


def test_inline_comments_are_ignored_for_unquoted_values(tmp_path, monkeypatch):
    configFilePath = tmp_path / "config.yml"
    configFilePath.write_text(
        ("debug: true # enabled\n" "ticksPerSecond: 45 # faster tick rate\n"),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        Config, "getConfigFilePath", staticmethod(lambda: configFilePath)
    )

    config = Config()

    assert config.debug
    assert config.ticksPerSecond == 45


def test_preserves_hash_after_escaped_quote_in_string(tmp_path, monkeypatch):
    configFilePath = tmp_path / "config.yml"
    configFilePath.write_text(
        ('pathToSaveDirectory: "saves/\\"#1" # keep after escaped quote\n'),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        Config, "getConfigFilePath", staticmethod(lambda: configFilePath)
    )

    config = Config()

    assert "#1" in config.pathToSaveDirectory
    assert config.pathToSaveDirectory.startswith("saves/")


def test_save_window_size_creates_entries(tmp_path, monkeypatch):
    configFilePath = tmp_path / "config.yml"
    configFilePath.write_text("debug: true\n", encoding="utf-8")
    monkeypatch.setattr(
        Config, "getConfigFilePath", staticmethod(lambda: configFilePath)
    )

    config = Config()
    config.saveWindowSize(800, 600)

    content = configFilePath.read_text(encoding="utf-8")
    assert "savedWindowWidth: 800" in content
    assert "savedWindowHeight: 600" in content


def test_save_window_size_updates_existing_entries(tmp_path, monkeypatch):
    configFilePath = tmp_path / "config.yml"
    configFilePath.write_text(
        "savedWindowWidth: 500\nsavedWindowHeight: 500\n", encoding="utf-8"
    )
    monkeypatch.setattr(
        Config, "getConfigFilePath", staticmethod(lambda: configFilePath)
    )

    config = Config()
    config.saveWindowSize(900, 700)

    content = configFilePath.read_text(encoding="utf-8")
    assert "savedWindowWidth: 900" in content
    assert "savedWindowHeight: 700" in content
    assert "500" not in content


def test_save_window_size_matches_whitespace_before_colon(tmp_path, monkeypatch):
    configFilePath = tmp_path / "config.yml"
    configFilePath.write_text(
        "savedWindowWidth : 500\nsavedWindowHeight : 500\n", encoding="utf-8"
    )
    monkeypatch.setattr(
        Config, "getConfigFilePath", staticmethod(lambda: configFilePath)
    )

    config = Config()
    config.saveWindowSize(900, 700)

    content = configFilePath.read_text(encoding="utf-8")
    assert "savedWindowWidth: 900" in content
    assert "savedWindowHeight: 700" in content
    # No duplicate keys — old lines were replaced, not appended
    assert content.count("savedWindowWidth") == 1
    assert content.count("savedWindowHeight") == 1


def test_save_window_size_clamps_to_minimum(tmp_path, monkeypatch):
    configFilePath = tmp_path / "config.yml"
    configFilePath.write_text("", encoding="utf-8")
    monkeypatch.setattr(
        Config, "getConfigFilePath", staticmethod(lambda: configFilePath)
    )

    config = Config()
    config.saveWindowSize(100, 200)

    content = configFilePath.read_text(encoding="utf-8")
    assert "savedWindowWidth: 400" in content
    assert "savedWindowHeight: 400" in content


def test_write_key_values_updates_appends_and_preserves(tmp_path, monkeypatch):
    configFilePath = tmp_path / "config.yml"
    configFilePath.write_text("# a comment\n\nexisting: old\n", encoding="utf-8")
    monkeypatch.setattr(
        Config, "getConfigFilePath", staticmethod(lambda: configFilePath)
    )

    config = Config()
    config._writeKeyValues({"existing": "new", "added": "value"}, "failed to write")

    content = configFilePath.read_text(encoding="utf-8")
    # Existing key updated in place (no duplicate), new key appended
    assert "existing: new" in content
    assert "old" not in content
    assert content.count("existing") == 1
    assert "added: value" in content
    # Comment and blank line preserved verbatim
    assert "# a comment" in content


def test_get_rooms_directory_format():
    config = Config()
    config.pathToSaveDirectory = "saves/myworld"
    # Single source of truth for the <saveDir>/rooms directory.
    assert config.getRoomsDirectory() == "saves/myworld/rooms"


def test_get_room_file_path_format():
    config = Config()
    config.pathToSaveDirectory = "saves/myworld"
    # Pins the on-disk room-file layout that all save/load call sites depend on
    assert config.getRoomFilePath(2, -3) == "saves/myworld/rooms/room_2_-3.json"
    assert config.getRoomFilePath(0, 0) == "saves/myworld/rooms/room_0_0.json"


def test_saved_window_size_is_loaded_on_init(tmp_path, monkeypatch):
    configFilePath = tmp_path / "config.yml"
    configFilePath.write_text(
        "savedWindowWidth: 800\nsavedWindowHeight: 600\n", encoding="utf-8"
    )
    monkeypatch.setattr(
        Config, "getConfigFilePath", staticmethod(lambda: configFilePath)
    )

    config = Config()

    assert config.displayWidth == 800.0
    assert config.displayHeight == 600.0


def test_saved_window_size_fallback_when_too_large(tmp_path, monkeypatch):
    configFilePath = tmp_path / "config.yml"
    configFilePath.write_text(
        "savedWindowWidth: 99999\nsavedWindowHeight: 99999\n", encoding="utf-8"
    )
    monkeypatch.setattr(
        Config, "getConfigFilePath", staticmethod(lambda: configFilePath)
    )

    config = Config()

    # Should fall back to default (90% of screen height)
    screenHeight = pygame.display.Info().current_h
    expectedDefault = screenHeight * 0.90
    assert config.displayWidth == expectedDefault
    assert config.displayHeight == expectedDefault


def test_manual_display_overrides_saved_window_size(tmp_path, monkeypatch):
    configFilePath = tmp_path / "config.yml"
    configFilePath.write_text(
        (
            "savedWindowWidth: 800\n"
            "savedWindowHeight: 600\n"
            "displayWidth: 1024\n"
            "displayHeight: 768\n"
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        Config, "getConfigFilePath", staticmethod(lambda: configFilePath)
    )

    config = Config()

    assert config.displayWidth == 1024.0
    assert config.displayHeight == 768.0


def test_no_saved_dimensions_uses_default(tmp_path, monkeypatch):
    configFilePath = tmp_path / "config.yml"
    configFilePath.write_text("", encoding="utf-8")
    monkeypatch.setattr(
        Config, "getConfigFilePath", staticmethod(lambda: configFilePath)
    )

    config = Config()

    screenHeight = pygame.display.Info().current_h
    expectedDefault = screenHeight * 0.90
    assert config.displayWidth == expectedDefault
    assert config.displayHeight == expectedDefault


def test_save_window_size_preserves_other_config(tmp_path, monkeypatch):
    configFilePath = tmp_path / "config.yml"
    configFilePath.write_text("debug: false\nticksPerSecond: 60\n", encoding="utf-8")
    monkeypatch.setattr(
        Config, "getConfigFilePath", staticmethod(lambda: configFilePath)
    )

    config = Config()
    config.saveWindowSize(800, 600)

    content = configFilePath.read_text(encoding="utf-8")
    assert "debug: false" in content
    assert "ticksPerSecond: 60" in content
    assert "savedWindowWidth: 800" in content
    assert "savedWindowHeight: 600" in content


# --- anonymous usage reporting settings ---


def test_usage_reporting_defaults_to_on_with_the_built_in_endpoint_and_key():
    from src.config.config import (
        USAGE_REPORTING_ENDPOINT_DEFAULT,
        USAGE_REPORTING_KEY_DEFAULT,
    )

    # isolate_config_file writes an empty file: no usageReporting* keys at all.
    config = Config()

    assert config.usageReportingEnabled is True
    assert config.usageReportingEndpoint == USAGE_REPORTING_ENDPOINT_DEFAULT
    assert config.usageReportingEndpoint == "https://trace.danielstephenson.dev"
    assert config.usageReportingKey == USAGE_REPORTING_KEY_DEFAULT
    assert config.usageReportingKey != ""
    assert config.usageReportingAcknowledged is False


def test_usage_reporting_opt_out_and_overrides_are_read(tmp_path, monkeypatch):
    configFilePath = tmp_path / "config.yml"
    configFilePath.write_text(
        "usageReportingEnabled: false\n"
        "usageReportingEndpoint: http://127.0.0.1:1\n"
        "usageReportingKey: not-the-real-key\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        Config, "getConfigFilePath", staticmethod(lambda: configFilePath)
    )

    config = Config()

    assert config.usageReportingEnabled is False
    assert config.usageReportingEndpoint == "http://127.0.0.1:1"
    assert config.usageReportingKey == "not-the-real-key"
    assert config.usageReportingAcknowledged is True


def test_usage_reporting_setting_present_counts_as_acknowledged(tmp_path, monkeypatch):
    configFilePath = tmp_path / "config.yml"
    configFilePath.write_text("usageReportingEnabled: true\n", encoding="utf-8")
    monkeypatch.setattr(
        Config, "getConfigFilePath", staticmethod(lambda: configFilePath)
    )

    config = Config()

    assert config.usageReportingEnabled is True
    assert config.usageReportingAcknowledged is True


def test_acknowledge_usage_reporting_writes_the_setting_once(tmp_path, monkeypatch):
    configFilePath = tmp_path / "config.yml"
    configFilePath.write_text("debug: false\n", encoding="utf-8")
    monkeypatch.setattr(
        Config, "getConfigFilePath", staticmethod(lambda: configFilePath)
    )

    config = Config()
    assert config.usageReportingAcknowledged is False
    config.acknowledgeUsageReporting()

    content = configFilePath.read_text(encoding="utf-8")
    assert content == "debug: false\nusageReportingEnabled: true\n"
    assert config.usageReportingAcknowledged is True
    # A second Config sees the marker, so the notice would not be shown again.
    assert Config().usageReportingAcknowledged is True


def test_acknowledge_usage_reporting_keeps_an_opt_out(tmp_path, monkeypatch):
    configFilePath = tmp_path / "config.yml"
    configFilePath.write_text("usageReportingEnabled: false\n", encoding="utf-8")
    monkeypatch.setattr(
        Config, "getConfigFilePath", staticmethod(lambda: configFilePath)
    )

    config = Config()
    config.acknowledgeUsageReporting()

    assert (
        configFilePath.read_text(encoding="utf-8") == "usageReportingEnabled: false\n"
    )
