import json
from pathlib import Path

DEFAULT_CONFIG = {
    "esp_port": "COM5",
    "esp_baudrate": 115200,
    "debug_run": False,
}

def load_app_config() -> dict:
    config_path = Path(__file__).resolve().parent.parent / "app_config.json"

    if not config_path.exists():
        return DEFAULT_CONFIG.copy()

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, dict):
            return DEFAULT_CONFIG.copy()

        result = DEFAULT_CONFIG.copy()
        result.update(data)
        return result
    except Exception as exc:
        print(f"Failed to load config: {exc}")
        return DEFAULT_CONFIG.copy()