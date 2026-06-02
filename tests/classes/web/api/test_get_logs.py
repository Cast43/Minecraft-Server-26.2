from unittest.mock import MagicMock as Mock

from app.classes.models.server_permissions import EnumPermissionsServer
from app.classes.shared.translation import Translation
from app.classes.web.routes.api.servers.server.logs import ApiServersServerLogsHandler


def mock_get_query_argument(key):
    if key == "file":
        return True


def test_log_file_terminal_perms() -> None:
    auth_data = (
        [],
        [],
        [],
        False,
        {"user_id": 1, "superuser": False, "lang": "en_EN"},
        "",
    )

    controller = Mock()
    controller.server_perms = Mock()
    controller.crafty_perms.get_crafty_permissions_list.return_value = [
        EnumPermissionsServer.LOGS
    ]
    handler = ApiServersServerLogsHandler.__new__(ApiServersServerLogsHandler)
    handler.request = Mock()
    handler.get_query_argument = Mock(side_effect=mock_get_query_argument)
    handler.controller = controller
    handler.helper = Mock()
    handler.helper.translation = Translation(handler.helper)
    handler.authenticate_user = Mock(return_value=auth_data)
    handler.finish_json = Mock()

    handler.get()

    handler.finish_json.assert_called_once_with(
        200,
        {
            "status": "ok",
            "data": {
                "top": True,
                "request_path": "",
                "dir": {"path": "dir/", "dir": True},
            },
        },
    )
