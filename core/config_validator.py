import logging
import re
from pathlib import Path

logger = logging.getLogger("shantyBot")

# Standard Discord Bot Token Structure:
# [Base64 ID].[Timestamp/Random].[HMAC Signature]
DISCORD_TOKEN_REGEX = re.compile(r"^[A-Za-z0-9_-]{24,32}\.[A-Za-z0-9_-]{6}\.[A-Za-z0-9_-]{27,38}$")

def validate_preflight_config(config: dict) -> bool:
    """
    Validates bot configuration prior to network or library initialization.
    Returns True if valid; logs an explicit diagnostic banner and returns False if invalid.
    """
    token = config.get("bot", {}).get("token", "").strip()
    placeholder_tokens = [
        "YOUR_DISCORD_BOT_TOKEN_HERE",
        "YOUR_BOT_TOKEN",
        "CHANGEME",
        ""
    ]

    # Check 1: Placeholder or empty string detection
    if token in placeholder_tokens or not token:
        _log_banner(
            title="CONFIGURATION ERROR: MISSING DISCORD BOT TOKEN",
            message=(
                "Your bot token in 'config.yaml' is currently set to a placeholder or empty string.\n\n"
                "REMEDIATION STEPS:\n"
                "1. Open 'config.yaml' on your host machine.\n"
                "2. Retrieve your Bot Token from the Discord Developer Portal:\n"
                "   https://discord.com/developers/applications\n"
                "3. Replace 'YOUR_DISCORD_BOT_TOKEN_HERE' with your real token.\n"
                "4. Restart the container / service."
            )
        )
        return False

    # Check 2: Basic structural regex validation
    if not DISCORD_TOKEN_REGEX.match(token):
        _log_banner(
            title="CONFIGURATION ERROR: MALFORMED DISCORD BOT TOKEN",
            message=(
                f"The token provided in 'config.yaml' ('{token[:6]}...') does not match the standard Discord token format.\n\n"
                "REMEDIATION STEPS:\n"
                "1. Verify that there are no accidental spaces, quotes, or line breaks surrounding the token.\n"
                "2. Ensure you copied the 'Bot Token' and NOT the 'Application ID' or 'Client Secret'.\n"
                "3. Reset the token in the Discord Developer Portal if necessary."
            )
        )
        return False

    return True

def _log_banner(title: str, message: str):
    """Outputs a clean, highly visible diagnostic banner to stderr/logs."""
    border = "=" * 70
    banner = f"\n{border}\n 🏴‍☠️ shantyBot Pre-Flight Diagnostic\n{border}\n[{title}]\n\n{message}\n{border}\n"
    logger.error(banner)
