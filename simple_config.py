import yaml
import os
from types import SimpleNamespace
from utils.logger import logger


def to_simple_namespace(data):
    if isinstance(data, dict):
        for key, value in data.items():
            data[key] = to_simple_namespace(value)
        return SimpleNamespace(**data)
    return data


def read_yaml_config(file_path):
    try:
        if os.path.exists(file_path):
            with open(file_path, 'r') as file:
                data = yaml.safe_load(file) or {}
                return to_simple_namespace(data)
            
    except yaml.YAMLError as e:
        logger.error(f"Error parsing Yaml file '{file_path}': {e}")
    except Exception as e:
        logger.error(f"Error loading YAML file '{file_path}': {e}")

    return SimpleNamespace()