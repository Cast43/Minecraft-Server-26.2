from pathlib import Path
from unittest.mock import MagicMock, Mock

import pytest

from app.classes.shared.backup_mgr import BackupManager


@pytest.mark.parametrize(
    "test_case",
    [
        ("2024-01-02-03-04-05.manifest", "snapshot_backup"),  # Normal snapshot backup
        ("2024-01-02_03-04-05.zip", "zip_vault"),  # Normal zip backup
        (
            "9999-12-31-23-59-59.manifest",
            "snapshot_backup",
        ),  # Python max datetime valid snapshot
        (
            "9999-12-31_23-59-59.zip",
            "zip_vault",
        ),  # Python max datetime valid zip backup
        (
            "0001-01-01-0-0-0.manifest",
            "snapshot_backup",
        ),  # Minimum datetime snapshot backup
        (
            "0001-01-01_0-0-0.zip",
            "zip_vault",
        ),  # Minimum datetime zip backup
    ],
)
def test_restore_starter_allowed_backups(monkeypatch, tmp_path, test_case):
    """Test restore_starter with a valid examples."""
    backup_file, backup_type = test_case

    # Start test setup
    mgr = BackupManager(MagicMock(), MagicMock(), MagicMock)

    def mock_valid_restore_starter(
        _unused_self,
        mock_backup_config,
        mock_backup_location: Path,
        mock_backup_file: str,
        _unused_svr_object,
        _unused_in_place_bool,
    ):
        assert mock_backup_config["backup_id"] == 1
        assert mock_backup_config["backup_type"] == backup_type
        assert mock_backup_config["backup_location"] == str(tmp_path)
        assert mock_backup_config["known_test_value"] == "test_value"
        assert mock_backup_location == tmp_path / backup_file
        assert mock_backup_file == backup_file

    monkeypatch.setattr(
        BackupManager, "valid_restore_starter", mock_valid_restore_starter
    )

    # End test setup

    backup_location = tmp_path / backup_file
    backup_config = {
        "backup_id": 1,
        "backup_type": backup_type,
        "backup_location": str(tmp_path),
        "known_test_value": "test_value",
    }

    mgr.restore_starter(backup_config, backup_location, MagicMock(), False)


@pytest.mark.parametrize(
    "test_case",
    [
        ("2024-01-02-03-04-05", "snapshot_backup"),  # too short (no extension)
        ("2024-01-02_03-04-05", "zip_vault"),  # too short (no extension)
        (
            "2024-01-02-03-04-05.manifest.disallowed",
            "snapshot_backup",
        ),  # too long (extra extension)
        (
            "2024-01-02_03-04-05.zip.disallowed",
            "zip_vault",
        ),  # too long (extra extension)
        ("2024.manifest", "snapshot_backup"),  # bad time format
        ("2024.zip", "zip_vault"),  # bad time format
        ("2024-01-02_03-04-05.manifest", "snapshot_backup"),  # Wrong format for type
        ("2024-01-02-03-04-05.manifest", "zip_vault"),  # Wrong format for type
        ("2024-01-02-03-04-05.incorrect", "snapshot_backup"),
        ("2024-01-02-03-04-05.incorrect", "zip_vault"),
    ],
)
def test_restore_starter_invalid_backup_file(
    monkeypatch, tmp_path, test_case: tuple[str, str]
):
    """Test various invalid backup files"""
    backup_file, backup_type = test_case

    # Test setup
    mgr = BackupManager(MagicMock(), MagicMock(), MagicMock())

    def mock_broadcast_rejected_restore(
        _unused_self, mock_backup_config, _unused_svr_obj
    ):
        assert mock_backup_config["backup_type"] == backup_type
        assert mock_backup_config["test_value"] == "known_test_value"

    monkeypatch.setattr(
        BackupManager, "broadcast_rejected_restore", mock_broadcast_rejected_restore
    )
    # End test setup

    backup_config = {
        "backup_type": backup_type,
        "backup_location": str(tmp_path),
        "test_value": "known_test_value",
    }

    backup_location = tmp_path / backup_file
    mgr.restore_starter(backup_config, backup_location, MagicMock(), False)


@pytest.mark.parametrize(
    "test_case",
    [
        (
            "app/servers/mockserver/",
            "app/backup/backuplocation/",
        ),  # backup to default location
        (
            "app/servers/mockserver/",
            "somewhere/on/computer",
        ),  # backup to other location on device
        ("app/servers/mockserver/", "app/backup/backuplocation/example"),
        # backup to other folder in crafty backup directory
    ],
)
def test_validate_backup_location_success(test_case: tuple[str, str]):
    """Test various valid backup locations"""
    mock_server_instance = Mock()
    mock_server_instance.server_path, backup_path = test_case
    mock_backup_config = {"backup_location": backup_path}

    mgr = BackupManager(MagicMock(), MagicMock(), MagicMock())

    assert (
        mgr.validate_backup_location(mock_server_instance, mock_backup_config) is True
    )


@pytest.mark.parametrize(
    "test_case",
    [
        (
            "app/servers/mockserver/",
            "app/servers/mockserver/",
        ),  # backing up to same server directory
        (
            "app/servers/mockserver",
            "app/servers/mockserver/example",
        ),  # backing up to parent
        ("app/servers/mockserver", "app/servers/mockserver/example/example"),
        # backing up to folder 2 levels in from parent
    ],
)
def test_validate_backup_location_failure(
    test_case: tuple[str, str],
):
    """Test various invalid backup locations"""
    mock_server_instance = Mock()
    mock_server_instance.server_path, backup_path = test_case
    mock_backup_config = {"backup_location": backup_path}

    mgr = BackupManager(MagicMock(), MagicMock(), MagicMock())

    assert (
        mgr.validate_backup_location(mock_server_instance, mock_backup_config) is False
    )
