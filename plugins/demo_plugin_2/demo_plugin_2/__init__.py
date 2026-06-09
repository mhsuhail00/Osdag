import uuid

IS_OSDAG_PLUGIN = True
META = {
    "name": "demo_plugin_2",
    "description": "A demonstration plugin for Osdag.",
    # List of <str>
    "authors": ["FOSSEE Team"],
    "version": "1.0.0",
    "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, f"demo_plugin_2:1.0.0")),
}

# --- Entry point: the class Osdag will instantiate on activation ---
ENTRY_POINT = "demo_plugin.DemoPlugin"
