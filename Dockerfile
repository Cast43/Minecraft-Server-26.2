FROM ubuntu:24.04

ENV DEBIAN_FRONTEND="noninteractive"

# Security Patch for CVE-2021-44228
ENV LOG4J_FORMAT_MSG_NO_LOOKUPS=true

# Remove shipped sudoer user (Required for Ubuntu 24.04 base) MR !826
# Create non-root user & required dirs
# Install required system packages
RUN touch /var/mail/ubuntu \
    && chown ubuntu /var/mail/ubuntu \
    && userdel -r ubuntu \
    && useradd -g root -M crafty \
    && mkdir /crafty \
    && chown -R crafty:root /crafty \
    && apt-get update \
    && apt-get -y --no-install-recommends install \
        sudo \
        gcc \
        libcurl4 \
        python3 \
        python3-dev \
        python3-pip \
        python3-venv \
        libmariadb-dev \
        default-jre \
        openjdk-8-jre-headless \
        openjdk-11-jre-headless \
        openjdk-17-jre-headless \
        openjdk-21-jre-headless \
        openjdk-25-jre-headless \
        tzdata \
    && if [ "$TARGETARCH" = "amd64" ]; then \
         apt-get -y --no-install-recommends install lib32gcc-s1; \
       else \
         echo "Skipping SteamCMD 32-bit deps on $TARGETARCH (no native support)."; \
       fi \
    && apt-get autoremove \
    && apt-get clean

# Switch to service user for installing crafty deps
USER crafty
WORKDIR /crafty
COPY --chown=crafty:root requirements.txt ./
RUN python3 -m venv ./.venv \
    && . .venv/bin/activate \
    && pip3 install --no-cache-dir --upgrade setuptools pip \
    && pip3 install --no-cache-dir -r requirements.txt \
    && deactivate
USER root

# Copy Source w/ perms & prepare default config from example
COPY --chown=crafty:root ./ ./
RUN mv ./app/config ./app/config_original \
    && mv ./app/config_original/default.json.example ./app/config_original/default.json \
    && chmod +x ./docker_launcher.sh

# Expose Web Interface port & Server port range
EXPOSE 5520-5550
EXPOSE 8000
EXPOSE 8123
EXPOSE 8443
EXPOSE 19132
EXPOSE 25500-25600

# Start Crafty through wrapper
ENTRYPOINT ["/crafty/docker_launcher.sh"]
CMD ["-d", "-i"]

# Add meta labels
ARG BUILD_DATE
ARG BUILD_REF
ARG CRAFTY_VER
LABEL \
    maintainer="Zedifus <https://gitlab.com/zedifus>" \
    org.opencontainers.image.created=${BUILD_DATE} \
    org.opencontainers.image.revision=${BUILD_REF} \
    org.opencontainers.image.version=${CRAFTY_VER} \
    org.opencontainers.image.title="Crafty Controller" \
    org.opencontainers.image.description="A Game Server Control Panel / Launcher" \
    org.opencontainers.image.url="https://craftycontrol.com/" \
    org.opencontainers.image.documentation="https://docs.craftycontrol.com" \
    org.opencontainers.image.source="https://gitlab.com/crafty-controller/crafty-4" \
    org.opencontainers.image.vendor="Arcadia Technology, LLC." \
    org.opencontainers.image.licenses="GPL-3.0"
