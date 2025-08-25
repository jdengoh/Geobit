import logging.config
from pathlib import Path

import yaml


def setup_logging():
    """Load logging configuration from YAML file."""
    config_path = Path(__file__).resolve().parents[1] / "config" / "logging.yaml"
    with open(config_path) as f:
        config = yaml.safe_load(f)

    logging.config.dictConfig(config)
