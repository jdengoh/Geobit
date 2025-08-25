import logging
import os

from dotenv import load_dotenv

logger = logging.getLogger("scripts")


def load_app_env():
    """Load environment variables from .env file."""
    # Check if running in Docker and skip loading .env if true
    logger.info("Loading environment variables...")
    if os.getenv("RUNNING_IN_DOCKER") == "true":
        logger.info("Skipping `load_app_env`, Docker environment detected.")
        return

    # Load .env file from the specified paths
    try:
        paths = [".env"]  # Add more paths if needed
        for path in paths:
            if os.path.exists(path):
                load_dotenv(path, override=True)
                logger.info(f"✅ Loading .env from: {os.path.abspath(path)}")
                return
        logger.warning("❌ No .env file found")
        load_dotenv(override=True)
        logger.info("Environment variables loaded successfully.")

    except Exception as e:
        logger.error(f"Failed to load environment variables: {e}")
        raise


# TODO: Function is not working, needs to be awaited.
# def _running_in_docker() -> bool:
#     """
#     Returns True when we are inside a Docker container.
#     """
#     return Path("/.dockerenv").exists()  # present in every Linux container
