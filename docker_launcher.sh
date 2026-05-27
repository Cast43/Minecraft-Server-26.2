#!/bin/sh

repair_permissions () {
    printf "\033[36mWrapper | \033[35m📋 (1/3) Ensuring root group ownership...\033[0m\n"
    find . ! -group root -print0 | xargs -0 -r chgrp root
    printf "\033[36mWrapper | \033[35m📋 (2/3) Ensuring group read-write is present on files...\033[0m\n"
    find . ! -perm g+rw -print0 | xargs -0 -r chmod g+rw
    printf "\033[36mWrapper | \033[35m📋 (3/3) Ensuring sticky bit is present on directories...\033[0m\n"
    find . -type d ! -perm g+s -print0 | xargs -0 -r chmod g+s
}

# Notify SteamCMD platform availability based on architecture
case "$(uname -m)" in
  x86_64|amd64)
    printf "\033[36mWrapper | \033[32m🚂✅ SteamCMD dependencies are available in this image!\033[0m\n"
    ;;
  *)
    printf "\033[36mWrapper | \033[33m⚠️ SteamCMD is only available on amd64/x86_64 images.\033[0m\n"
    printf "\033[36mWrapper | \033[33m    Detected architecture: %s. SteamCMD features are disabled.\033[0m\n" "$(uname -m)"
    ;;
esac

# Check if config exists taking one from image if needed.
if [ ! "$(ls -A --ignore=.gitkeep ./app/config)" ]; then
    printf "\033[36mWrapper | \033[33m🏗️  Config not found, pulling defaults...\033[0m\n"
    mkdir ./app/config/ 2> /dev/null
    cp -r ./app/config_original/* ./app/config/

    if [ $(id -u) -eq 0 ]; then
        # We're running as root;

        # Look for files & dirs that require group permissions to be fixed
        # This will do the full /crafty dir, so will take a miniute.
        printf "\033[36mWrapper | \033[35m📋 Looking for problem bind mount permissions globally...\033[0m\n"

        repair_permissions

        printf "\033[36mWrapper | \033[32m✅ Initialization complete!\033[0m\n"
    fi
else
    # Keep version file up to date with image
    cp -f ./app/config_original/version.json ./app/config/version.json
fi


if [ $(id -u) -eq 0 ]; then
    # We're running as root

    # If we find files in import directory, we need to ensure all dirs are owned by the root group,
    # This fixes bind mounts that may have incorrect perms.
    if [ "$(find ./import -type f ! -name '.gitkeep')" ]; then
        printf "\033[36mWrapper | \033[35m📋 Files present in import directory, checking/fixing permissions...\033[0m\n"
        printf "\033[36mWrapper | \033[33m⏳ Please be patient for larger servers...\033[0m\n"

        repair_permissions

        printf "\033[36mWrapper | \033[32m✅ Permissions Fixed! (This will happen every boot until /import is empty!)\033[0m\n"
    fi

    # Switch user, activate our prepared venv and launch crafty
    args="$@"
    printf "\033[36mWrapper | \033[32m🚀 Launching crafty with [\033[34m%s\033[32m]\033[0m\n" "$args"
    exec sudo -u crafty bash -c "source ./.venv/bin/activate && exec python3 main.py $args"
else
    # Activate our prepared venv
    printf "\033[36mWrapper | \033[32m🚀 Non-root host detected, using normal exec\033[0m\n"
    . ./.venv/bin/activate
    # Use exec as our perms are already correct
    # This is likely if using Kubernetes/OpenShift etc
    exec python3 main.py "$@"
fi
