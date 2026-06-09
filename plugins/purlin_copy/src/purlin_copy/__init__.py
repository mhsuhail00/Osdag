from importlib.metadata import metadata
import uuid

_meta = metadata("purlin_copy")
IS_OSDAG_PLUGIN = True
META = {
    "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{_meta['name']}:{_meta['version']}")),
    "name": _meta["name"],
    "version": _meta["version"],
}

# --- Entry point: the class Osdag will instantiate on activation ---
ENTRY_POINT = "flexure_purlin.Flexure_Purlin"
