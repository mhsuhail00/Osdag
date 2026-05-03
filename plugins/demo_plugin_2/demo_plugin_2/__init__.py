from importlib.metadata import metadata
import uuid

_meta = metadata("demo_plugin_2")
IS_OSDAG_PLUGIN = True
META = {
    "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{_meta['name']}:{_meta['version']}")),
    "name": _meta["name"],
    "description": _meta["Summary"],
    "authors": [a.strip() for a in _meta["Author"].split(",")], # List of <str>
    "version": _meta["version"],
}

# --- Entry point: the class Osdag will instantiate on activation ---
ENTRY_POINT = "demo_plugin.DemoPlugin"