# Base image with the official Hermes runtime.
FROM nousresearch/hermes-agent:stable

# Run as root so the wrapper script can be installed and made executable.
USER root

# Copy the Render bootstrap so the container can open the health port before Hermes starts.
COPY start.sh /opt/hermes-start.sh

# Make the bootstrap executable for the container entrypoint.
RUN chmod 0755 /opt/hermes-start.sh

# Render requires a listening port; this wrapper starts the health server and then hands off to Hermes.
ENTRYPOINT ["/opt/hermes-start.sh"]

# Default Hermes command for the official image entrypoint.
CMD ["gateway", "run"]
