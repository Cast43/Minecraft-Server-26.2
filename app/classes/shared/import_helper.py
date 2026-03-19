import re
import os
import glob
import uuid
import json
import time
import shlex
import pathlib
import logging
import threading
import subprocess
from pathlib import PurePosixPath, Path

from app.classes.big_bucket.bigbucket import BigBucket
from app.classes.big_bucket.hytale import HytaleJSON
from app.classes.controllers.server_perms_controller import (
    PermissionsServers,
    EnumPermissionsServer,
)
from app.classes.controllers.servers_controller import ServersController
from app.classes.helpers.helpers import Helpers
from app.classes.helpers.file_helpers import FileHelpers
from app.classes.shared.websocket_manager import WebSocketManager
from app.classes.steamcmd.steamcmd import SteamCMD
from app.classes.models.servers import HelperServers


logger = logging.getLogger(__name__)

HYTALE_0UTPUT_NAME = "hytale.zip"


class ImportHelpers:
    allowed_quotes = ['"', "'", "`"]

    def __init__(self, helper, file_helper):
        self.file_helper: FileHelpers = file_helper
        self.helper: Helpers = helper
        self.big_bucket = BigBucket(helper)

    def import_zipped_server(
        self,
        archive_path,
        new_server_dir,
        base_include_path,
        port,
        new_id,
        server_type,
        full_exe_path=None,
    ):
        import_thread = threading.Thread(
            target=self.import_threaded_zipped_server,
            daemon=True,
            args=(
                archive_path,
                new_server_dir,
                base_include_path,
                port,
                new_id,
                server_type,
                full_exe_path,
            ),
            name=f"{new_id}_import",
        )
        import_thread.start()

    def import_threaded_zipped_server(
        self,
        archive_path,
        new_server_dir,
        base_include_path,
        port,
        new_id,
        server_type,
        full_exe_path,
    ):
        self.file_helper.unzip_file(
            archive_path,
            new_server_dir,
            new_id,
            False,
            base_include_path=base_include_path,
        )

        time.sleep(2)
        if (
            not self.helper.is_os_windows() and full_exe_path
        ):  # we only expect full jar path for bedrock
            if Helpers.check_file_exists(full_exe_path):
                os.chmod(full_exe_path, 0o2760)  # apply execute permissions

        self.file_helper.del_file(archive_path)

        has_properties = False
        for item in os.listdir(new_server_dir):
            if str(item) == "server.properties":
                has_properties = True
        if not has_properties and "minecraft" in server_type:
            logger.info(
                f"No server.properties found on zip file import. "
                f"Creating one with port selection of {str(port)}"
            )
            with open(
                os.path.join(new_server_dir, "server.properties"), "w", encoding="utf-8"
            ) as file:
                file.write(f"server-port={port}")
                file.close()
        time.sleep(5)
        ServersController.finish_import(new_id)
        server_users = PermissionsServers.get_server_user_list(new_id)
        for user in server_users:
            WebSocketManager().broadcast_user(user, "send_start_reload", {})

    def download_steam_server(self, app_id, server_id, server_dir, server_exe):
        download_thread = threading.Thread(
            target=self._create_steam_server,
            daemon=True,
            args=(app_id, server_id, server_dir, server_exe),
            name=f"{server_id}_download",
        )
        download_thread.start()

    def _create_steam_server(self, app_id, server_id, server_dir, server_exe):
        if not server_exe:
            server_exe = "game.exe"  # replace with actual exe eventually

        # Initiate SteamCMD & game installing status.
        ServersController.set_import(server_id)

        # Set our storage locations
        steamcmd_path = os.path.join(server_dir, "steamcmd_files")
        gamefiles_path = os.path.join(server_dir, "gameserver_files")

        # Ensure game and steam directories exist in server directory.
        self.helper.ensure_dir_exists(steamcmd_path)
        self.helper.ensure_dir_exists(gamefiles_path)

        # Initialize SteamCMD
        self.steam = SteamCMD(steamcmd_path)

        # Install SteamCMD for managing game server files.
        self.steam.install()

        # Install the game server files.
        self.steam.app_update(app_id, gamefiles_path)

        # Set the server execuion command. TODO brainstorm how to approach.
        full_exe_path = os.path.join(steamcmd_path, server_exe)
        if Helpers.is_os_windows():
            server_command = f'"{full_exe_path}"'
        else:
            server_command = f"./{server_exe}"
        logger.debug("command: " + server_command)

        # Finalise SteamCMD & game installing status.
        ServersController.finish_import(server_id)
        server_users = PermissionsServers.get_server_user_list(server_id)
        for user in server_users:
            WebSocketManager().broadcast_user(user, "send_start_reload", {})

    def download_threaded_bedrock_server(self, path, new_id):
        bedrock_url = Helpers.get_latest_bedrock_url()
        download_thread = threading.Thread(
            target=self._download_bedrock_server,
            daemon=True,
            args=(path, new_id, bedrock_url),
            name=f"{new_id}_download",
        )
        download_thread.start()

    def _download_bedrock_server(self, path, new_id, bedrock_url, server_update=False):
        """
        Downloads the latest Bedrock server, unzips it, sets necessary permissions.

        Parameters:
            path (str): The directory path to download and unzip the Bedrock server.
            new_id (str): The identifier for the new server import operation.

        This method handles exceptions and logs errors for each step of the process.
        """
        try:
            if bedrock_url:
                file_path = os.path.join(path, "bedrock_server.zip")
                success = FileHelpers.ssl_get_file(
                    bedrock_url, path, "bedrock_server.zip"
                )
                if not success:
                    logger.error("Failed to download the Bedrock server zip.")
                    return

                unzip_path = self.helper.wtol_path(file_path)
                destination_path = pathlib.Path(unzip_path).parents[0]
                # unzips archive that was downloaded.
                self.file_helper.unzip_file(
                    unzip_path, destination_path, new_id, server_update=server_update
                )
                # adjusts permissions for execution if os is not windows

                if not self.helper.is_os_windows():
                    os.chmod(os.path.join(path, "bedrock_server"), 0o0744)

                # we'll delete the zip we downloaded now
                os.remove(file_path)
            else:
                logger.error("Bedrock download URL issue!")
        except Exception as e:
            logger.critical(
                f"Failed to download bedrock executable during server creation! \n{e}"
            )
            raise e

        ServersController.finish_import(new_id)
        server_users = PermissionsServers.get_server_user_list(new_id)
        for user in server_users:
            WebSocketManager().broadcast_user(user, "send_start_reload", {})

    def download_install_threaded_hytale(self, path, new_id):
        download_thread = threading.Thread(
            target=self._download_install_hytale,
            daemon=True,
            args=(path, new_id),
            name=f"{new_id}_download",
        )
        download_thread.start()

    def _download_install_hytale(self, server_path: str | Path, new_id: uuid.UUID):
        server_users = PermissionsServers.get_server_user_list(new_id)

        bb_cache = self.big_bucket.get_bucket_data(self.helper.big_bucket_hytale_cache)
        try:
            hytale_json = HytaleJSON(bb_cache)
            unix_exe = PurePosixPath(hytale_json.linux_installer_url).name
            windows_exe = PurePosixPath(hytale_json.windows_installer_url).name
        except KeyError:
            logger.error("Failed to create Hytale server with keyerror")
            ServersController.finish_import(new_id)
            return
        install_command = (
            f"./{unix_exe} "
            f"{hytale_json.commands.download_path_command} {HYTALE_0UTPUT_NAME}"
        )
        if self.helper.is_os_windows():
            install_command = (
                f"{server_path}/{windows_exe} "
                f"{hytale_json.commands.download_path_command} {HYTALE_0UTPUT_NAME}"
            )
            self.file_helper.ssl_get_file(
                hytale_json.windows_installer_url, server_path, windows_exe
            )
        else:
            self.file_helper.ssl_get_file(
                hytale_json.linux_installer_url, server_path, unix_exe
            )
            os.chmod(Path(server_path, unix_exe), 0o2760)  # set executable permissions
            install_command = shlex.split(install_command)
        process = subprocess.Popen(
            install_command,
            cwd=server_path,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        url_line = ""
        while process.poll() is None:
            line = process.stdout.readline().strip()
            if not line:
                continue

            line = line.strip()
            # TODO: Do not send data to clients who do not have permission to view
            # this server's console
            if len(WebSocketManager().clients) > 0:
                WebSocketManager().broadcast_page_params(
                    "/panel/server_detail",
                    {"id": new_id},
                    "vterm_new_line",
                    {"line": line + "<br />"},
                )
            if (
                line.startswith(hytale_json.parsing_lines.url_line_start)
                and url_line == ""
            ):
                url_line = line
                with open(
                    Path(server_path, "hytale_install_auth_url.txt"),
                    "w",
                    encoding="utf-8",
                ) as auth_file:
                    auth_file.write(url_line)
                for user in server_users:
                    WebSocketManager().broadcast_user(
                        user,
                        "hytale_auth",
                        {"link": line, "server_id": new_id},
                    )

        # Unzip downloaded archive.
        self.file_helper.unzip_file(
            Path(server_path, HYTALE_0UTPUT_NAME),
            server_path,
        )
        self.install_or_update_monitoring_plugins(new_id, server_path)
        ServersController.finish_import(new_id)
        for user in server_users:
            WebSocketManager().broadcast_user(user, "send_start_reload", {})

    def install_or_update_monitoring_plugins(
        self, server_id: uuid.UUID, server_path: str | Path
    ):
        bb_cache = self.big_bucket.get_bucket_data(self.helper.big_bucket_hytale_cache)
        try:
            hytale_json = HytaleJSON(bb_cache)
        except KeyError:
            logger.error("Failed to download hytale plugins with keyerror")
            return
        logger.info("Installing Nitrado Webserver Plugin to server %s", server_id)
        # make sure our mods dir exists before doing anything
        # Download webserver plugin required for query plugin
        self.helper.ensure_dir_exists(Path(server_path, "mods"))
        self.file_helper.ssl_get_file(
            hytale_json.plugins.webserver_plugin_url,
            Path(server_path, "mods"),
            "nitrado-webserver.jar",
        )
        # Download query plugin
        logger.info("Installing Nitrado Query Plugin to server %s", server_id)
        self.file_helper.ssl_get_file(
            hytale_json.plugins.query_plugin_url,
            Path(server_path, "mods"),
            "nitrado-query.jar",
        )
        self.modify_permissions_json(server_path)

    def modify_permissions_json(self, server_path: str | Path):
        # Make sure we do not overwrite user data
        if not Helpers.check_file_exists(str(Path(server_path, "permissions.json"))):
            with open(
                Path(server_path, "permissions.json"), "w", encoding="utf-8"
            ) as perms_file:
                decoded = {
                    "groups": {
                        "ANONYMOUS": [
                            "nitrado.query.web.read.server",
                            "nitrado.query.web.read.universe",
                            "nitrado.query.web.read.players",
                        ]
                    }
                }
                perms_file.write(json.dumps(decoded, indent=4))

    def _install_type_forge(self, server_path: str | Path, new_id: uuid.UUID):
        server_obj = HelperServers.get_server_obj(new_id)
        process = subprocess.Popen(
            server_obj.execution_command,
            cwd=server_path,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        while process.poll() is None:
            line = process.stdout.readline().strip()
            if not line:
                continue

            line = line.strip()
            if len(WebSocketManager().clients) > 0:
                WebSocketManager().broadcast_page_params(
                    "/panel/server_detail",
                    {"id": new_id},
                    "vterm_new_line",
                    {"line": line + "<br />"},
                    required_permission=EnumPermissionsServer.TERMINAL,
                )
        try:
            # Getting the forge version from the executable command
            version = re.findall(
                r"(?:forge|neoforge)-installer-([0-9\.]+)((?:)|"
                r"(?:-([0-9\.]+)-[a-zA-Z]+)).jar",
                server_obj.execution_command,
            )
            version_info = re.findall(
                r"(forge|neoforge)-installer-([0-9\.]+)((?:)|"
                r"(?:-([0-9\.]+)-[a-zA-Z]+)).jar",
                server_obj.execution_command,
            )
            version_param = version_info[0][1].split(".")
            version_major = int(version_param[0])
            version_minor = int(version_param[1])
            if len(version_param) > 2:
                version_sub = int(version_param[2])
            else:
                version_sub = 0

            # Checking which version we are with
            if version_major <= 1 and version_minor < 17:
                # OLD VERSION < 1.17

                # Retrieving the executable jar filename
                file_path = glob.glob(
                    f"{server_obj.path}/" f"{version_info[0][0]}-{version[0][1]}*.jar"
                )[0]
                file_name = re.findall(
                    r"(forge[-0-9.]+.jar)",
                    file_path,
                )[0]

                # Let's set the proper server executable
                server_obj.executable = os.path.join(file_name)

                # Get memory values
                memory_values = re.findall(
                    r"-Xms([A-Z0-9\.]+) -Xmx([A-Z0-9\.]+)",
                    server_obj.execution_command,
                )

                # Now lets set up the new run command.
                # This is based off the run.sh/bat that
                # Forge uses in 1.17 and <
                execution_command = (
                    f"java -Xms{memory_values[0][0]} -Xmx{memory_values[0][1]}"
                    f' -jar "{file_name}" nogui'
                )
                server_obj.execution_command = execution_command

            elif (
                version_major <= 1 and version_minor <= 20 and version_sub < 3
            ) or version_info[0][0] == "neoforge":
                # NEW VERSION >= 1.17 and <= 1.20.2
                # (no jar file in server dir, only run.bat and run.sh)

                run_file_path = ""
                if self.helper.is_os_windows():
                    run_file_path = os.path.join(server_obj.path, "run.bat")
                else:
                    run_file_path = os.path.join(server_obj.path, "run.sh")

                if Helpers.check_file_perms(run_file_path) and os.path.isfile(
                    run_file_path
                ):
                    run_file = open(run_file_path, "r", encoding="utf-8")
                    run_file_text = run_file.read()
                else:
                    logger.error(
                        "ERROR ! Forge install can't read the scripts files."
                        " Aborting ..."
                    )
                    return

                # We get the server command parameters from forge script
                server_command = re.findall(
                    r"java @([a-zA-Z0-9_\.]+)"
                    r" @([a-z./\-]+)"
                    r"([0-9.\-]+(?:-[a-zA-Z0-9]+)?)"
                    r"\/\b([a-z_0-9]+\.txt)\b"
                    r"( .{2,4})?",
                    run_file_text,
                )[0]

                version = server_command[2]
                executable_path = f"{server_command[1]}{server_command[2]}/"
                # Let's set the proper server executable
                server_obj.executable = os.path.join(
                    f"{executable_path}{version_info[0][0]}-{version}" "-server.jar"
                )
                # Now lets set up the new run command.
                # This is based off the run.sh/bat that
                # Forge uses in 1.17 and <
                execution_command = (
                    f"java @{server_command[0]}"
                    f" @{executable_path}{server_command[3]} nogui"
                    f" {server_command[4]}"
                )
                server_obj.execution_command = execution_command
            else:
                # NEW VERSION >= 1.20.3
                # (executable jar is back in server dir)

                # Retrieving the executable jar filename
                file_path = glob.glob(f"{server_obj.path}/forge-{version[0][0]}*.jar")[
                    0
                ]
                file_name = re.findall(
                    r"(forge-[\-0-9.]+-shim.jar)",
                    file_path,
                )[0]

                # Let's set the proper server executable
                server_obj.executable = os.path.join(file_name)

                # Get memory values
                memory_values = re.findall(
                    r"-Xms([A-Z0-9\.]+) -Xmx([A-Z0-9\.]+)",
                    server_obj.execution_command,
                )

                # Now lets set up the new run command.
                # This is based off the run.sh/bat that
                # Forge uses in 1.17 and <
                execution_command = (
                    f"java -Xms{memory_values[0][0]} -Xmx{memory_values[0][1]}"
                    f' -jar "{file_name}" nogui'
                )
                server_obj.execution_command = execution_command
        except:
            logger.debug("Could not find run file.")
        HelperServers.update_server(server_obj)

    def download_threaded_exe(self, jar, server, version, path, server_id):
        update_thread = threading.Thread(
            name=f"server_download-{server_id}-{server}-{version}",
            target=self._download_exe,
            daemon=True,
            args=(jar, server, version, path, server_id),
        )
        update_thread.start()

    def _download_exe(self, jar, server, version, path, server_id):
        """
        Downloads a server JAR file and performs post-download actions including
        notifying users and setting import status.

        This method waits for the server registration to complete, retrieves the
        download URL for the specified server JAR file.

        Upon successful download, it either runs the installer for
        Forge servers or simply finishes the import process for other types. It
        notifies server users about the completion of the download.

        Parameters:
            - jar (str): The category of the JAR file to download.
            - server (str): The type of server software (e.g., 'forge', 'paper').
            - version (str): The version of the server software.
            - path (str): The local filesystem path where the JAR file will be saved.
            - server_id (str): The unique identifier for the server being updated or
                imported, used for notifying users and setting the import status.

        Returns:
            - bool: True if the JAR file was successfully downloaded and saved;
                False otherwise.

        The method ensures that the server is properly registered before proceeding
        with the download and handles exceptions by logging errors and reverting
        the import status if necessary.
        """
        # delaying download for server register to finish
        time.sleep(3)

        fetch_url = self.big_bucket.get_fetch_url(jar, server, version)
        if not fetch_url:
            return False

        server_users = PermissionsServers.get_server_user_list(server_id)

        # Make sure the server is registered before updating its stats
        while True:
            try:
                ServersController.set_import(server_id)
                for user in server_users:
                    WebSocketManager().broadcast_user(user, "send_start_reload", {})
                break
            except Exception as ex:
                logger.debug(f"Server not registered yet. Delaying download - {ex}")

        # Initiate Download
        jar_dir = os.path.dirname(path)
        jar_name = os.path.basename(path)
        logger.info(fetch_url)
        success = FileHelpers.ssl_get_file(fetch_url, jar_dir, jar_name)

        # Post-download actions
        if success:
            if server in ("forge-installer", "neoforge-installer"):
                # If this is the newer Forge version, run the installer
                return self._install_type_forge(jar_dir, server_id)
            ServersController.finish_import(server_id)

            # Notify users
            for user in server_users:
                WebSocketManager().broadcast_user(
                    user, "notification", "Executable download finished"
                )
                time.sleep(3)  # Delay for user notification
                WebSocketManager().broadcast_user(user, "send_start_reload", {})
        else:
            logger.error(f"Unable to save jar to {path} due to download failure.")
            ServersController.finish_import(server_id)

        return success
