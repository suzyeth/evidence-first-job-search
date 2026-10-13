import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(HERE, "..", "scripts")
FIXTURES = os.path.join(HERE, "fixtures")
EXAMPLE_SWEEP_CONFIG = os.path.join(SCRIPTS, "sweep_config.example.json")


def load_script(name):
    """Import scripts/<name>.py once and cache it in sys.modules (dataclasses need that)."""
    if name in sys.modules:
        return sys.modules[name]
    saved = sys.argv
    if name == "sweep":  # sweep.py reads its config at import time
        sys.argv = ["sweep.py", "--config", EXAMPLE_SWEEP_CONFIG]
    try:
        spec = importlib.util.spec_from_file_location(name, os.path.join(SCRIPTS, f"{name}.py"))
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    finally:
        sys.argv = saved
    return module
