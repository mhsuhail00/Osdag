import json
import os, subprocess, sys, requests, platform
import tempfile
from dataclasses import dataclass, field
from threading import Lock
from importlib import metadata
from pathlib import Path
import pkgutil
import importlib, uuid
from types import ModuleType


@dataclass
class PluginMetaData:
    id: str
    name: str
    description: str = field(
        default_factory=lambda: "No description available.")
    authors: list[str] = field(default_factory=lambda: ["Unknown"])
    version: str = field(default_factory=lambda: "1.0.0")
    status: bool = field(default_factory=lambda: False)
    module: object = field(default_factory=lambda: None)
    entry_class: object = field(default_factory=lambda: None)
    is_dev: bool = field(default_factory=lambda: False)


class PluginManager:
    def __init__(self):
        self.state_manager = StateManager()
        self.plugins: list[PluginMetaData] = []
        self.dev_plugins_path = Path(
            __file__).resolve().parent.parent.parent / "plugins"
        self.plugins_entry_point = None
        print(f"[INFO] PluginManager initialized.")

    # ---------------------------
    # Plugin Discovery (Local Under Development & Installed Plugins)
    # ---------------------------
    def discover_local_plugins(self) -> list[PluginMetaData]:
        self.plugins.clear()

        self._load_entry_point_plugins()
        self._load_dev_plugins()

        for plugin in self.plugins:
            plugin.status = self.state_manager.get_status(plugin)

        return self.plugins

    def _load_entry_point_plugins(self) -> None:
        try:
            self.plugins_entry_point = metadata.entry_points().select(group="osdag.plugins")
            for ep in self.plugins_entry_point:
                module = ep.load()
                if not getattr(module, "IS_OSDAG_PLUGIN", False):
                    print(
                        f"[WARN] Entry point '{ep.name}' is not a valid OSDAG plugin.")
                    continue
                meta = getattr(module, "META", {})
                name = meta.get("name")
                if name is None:
                    print(f"[WARN] Entry point '{ep.name}' is missing 'name'.")
                    continue
                if "osdag_plugin_" in name:
                    name = name[len("osdag_plugin_"):]
                    meta["name"] = name

                entry_point = getattr(module, "ENTRY_POINT", None)
                entry_class = self._resolve_entry_class(
                    module, name, entry_point)
                if entry_class:
                    self.plugins.append(PluginMetaData(
                        **meta, status=False, module=module, entry_class=entry_class))
                else:
                    print(
                        f"[WARN] Entry point '{ep.name}' could not resolve entry class.")
                    continue
        except Exception as e:
            print(f"[WARN] Entry point loading failed: {e}")

    def _load_dev_plugins(self) -> None:
        if not self.dev_plugins_path.exists():
            return
        for _, name, ispkg in pkgutil.iter_modules([str(self.dev_plugins_path)]):
            if not ispkg:
                continue
            if name in [p.name for p in self.plugins]:
                print(
                    f"[WARN] Dev plugin '{name}' is already loaded from osdag.plugins entry point.")
                continue
            try:
                module = importlib.import_module(f"plugins.{name}")
                if not getattr(module, "IS_OSDAG_PLUGIN", False):
                    print(
                        f"[WARN] Dev plugin '{name}' is not a valid OSDAG plugin.")
                    continue
                meta = getattr(module, "META", {})
                name = meta.get("name")
                if name is None:
                    print(f"[WARN] Dev plugin '{name}' is missing 'name'.")
                    continue
                entry_class = self._resolve_entry_class(
                    module, name, getattr(module, "ENTRY_POINT", None))
                if entry_class:
                    self.plugins.append(PluginMetaData(
                        **meta, module=module, entry_class=entry_class, is_dev=True))
                else:
                    print(
                        f"[WARN] Dev plugin '{name}' could not resolve entry class.")
            except Exception as e:
                print(f"[WARN] Could not load dev plugins: {e}")

    def _resolve_entry_class(self, module: ModuleType, name: str, entry_path: str) -> object | None:
        if not entry_path:
            print(f"[WARN] Plugin '{name}' missing 'ENTRY_POINT'.")
            return None
        try:
            parts = entry_path.split(".")
            submodule_name = ".".join(parts[:-1])
            class_name = parts[-1]
            entry_module = importlib.import_module(
                f"{module.__name__}" + (f".{submodule_name}" if submodule_name else ""))
            return getattr(entry_module, class_name)
        except Exception as e:
            print(
                f"[WARN] Could not resolve entry class '{entry_path}' for plugin '{name}': {e}")
            return None


    def discover_online_plugins(self, channel: str) -> list[PluginMetaData]:
        # Simulate discovering online plugins[sys.executable, "-m", "conda", "search", "--json", "-c", channel]
        url = f"https://conda.anaconda.org/{channel}/label/main/noarch/repodata.json"
        pkgs = self._fetch_channel_pkgs(url=url)
        online_plugins = []
        for pkg_filename, info in pkgs.items():
            meta = {
                "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{info.get('name', '')}:{info.get('version', '')}")),
                "name": info.get("name", ""),
                "description": info.get("summary", "No description available."),
                "authors": [info.get("author", "Unknown")],
                "version": info.get("version", "1.0.0"),
            }
            online_plugins.append(PluginMetaData(**meta))
        return online_plugins

    def _fetch_channel_pkgs(self, url:str):
        """Fetch and parse repodata.json from a conda channel and return packages."""
        resp = requests.get(url, timeout=20)
        resp.raise_for_status()
        repo_data = resp.json()
        pkgs = {}
        pkgs.update(repo_data.get("packages", {}))
        pkgs.update(repo_data.get("packages.conda", {}))
        return pkgs

    # ---------------------------
    # State Management
    # ---------------------------
    def activate(self, plugin: PluginMetaData):
        print(f"[INFO] Activating plugin: {plugin.name}")
        if plugin:
            plugin.status = True
            self.state_manager.update_state(plugin, plugin.status)

    def deactivate(self, plugin: PluginMetaData):
        print(f"[INFO] Deactivating plugin: {plugin.name}")
        if plugin:
            plugin.status = False
            self.state_manager.update_state(plugin, plugin.status)

    def download_plugin(self, plugin: PluginMetaData) -> bool:
        print(f"[INFO] Downloading plugin: {plugin.name}")

        if not hasattr(self, 'conda_exe'):
            self.conda_exe = os.environ["CONDA_EXE"]

        cmd = [
            self.conda_exe,
            "install",
            "--prefix", os.environ["CONDA_PREFIX"],
            f"zehen-249::{plugin.name}",
            "-y"
        ]
        result = subprocess.run(cmd,capture_output=True, text=True)
        # print(result.stdout)
        # print(result.stderr)
        if result.returncode == 0:
            self.plugins.append(plugin)
            return True
        return False

    def delete_plugin(self, plugin: PluginMetaData) -> bool:
        print(f"[INFO] Deleting plugin: {plugin.name}")

        if not hasattr(self, 'conda_exe'):
            self.conda_exe = os.environ["CONDA_EXE"]

        cmd = [
            self.conda_exe,
            "remove",
            "--prefix", os.environ["CONDA_PREFIX"],
            f"{plugin.name}",
            "-y"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        # print(result.stdout)
        # print(result.stderr)
        if result.returncode == 0:
            self.plugins = [p for p in self.plugins if p.id != plugin.id]
            self.state_manager.delete_state(plugin)
            return True
        return False

    def update_plugin(self, plugin: PluginMetaData) -> bool:
        print(f"[INFO] Updating plugin: {plugin.name}")
        
        if not hasattr(self, 'conda_exe'):
            self.conda_exe = os.environ["CONDA_EXE"]

        cmd = [
            self.conda_exe,
            "update",
            "--prefix", os.environ["CONDA_PREFIX"],
            f"{plugin.name}",
            "-y"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        # print(result.stdout)
        # print(result.stderr)
        if result.returncode == 0:
            return True
        return False


    def get_plugin(self, plugin_id: str) -> PluginMetaData | None:
        for p in self.plugins:
            if p.id == plugin_id:
                return p
        return None

    def get_plugin_by_name(self, plugin_name: str) -> PluginMetaData | None:
        for p in self.plugins:
            if p.name == plugin_name:
                return p
        return None


class StateManager:
    def __init__(self):
        self.state_file = Path(__file__).resolve(
        ).parent.parent / "data" / "ResourceFiles" / "plugins" / "plugin_state.json"
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self.states: dict[str, bool] = self._load_states()
        self._dirty = False
        print(f"[INFO] StateManager initialized")

    def _load_states(self):
        if not os.path.exists(self.state_file):
            return {}
        with self._lock:
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                print(
                    f"[WARN] Could not load state file {self.state_file}: {e}")
                return {}

    def get_status(self, plugin: PluginMetaData) -> bool:
        with self._lock:
            return self.states.get(plugin.id, False)

    def update_state(self, plugin: PluginMetaData, status: bool) -> None:
        with self._lock:
            prev = self.states.get(plugin.id)
            if prev != status:
                self.states[plugin.id] = status
                self._dirty = True

    def delete_state(self, plugin: PluginMetaData) -> None:
        with self._lock:
            if plugin.id in self.states:
                del self.states[plugin.id]
                self._dirty = True

    def flush(self):
        with self._lock:
            if not self._dirty:
                return
            self._atomic_save(self.states)
            self._dirty = False

    def _atomic_save(self, data: dict[str, bool]):
        dir_name = os.path.dirname(self.state_file)
        if not dir_name:
            dir_name = "."
        try:
            with tempfile.NamedTemporaryFile("w", dir=dir_name, delete=False, encoding="utf-8") as tmp:
                json.dump(data, tmp, indent=4)
                tmp.flush()
                os.fsync(tmp.fileno())
                temp_name = tmp.name
            os.replace(temp_name, self.state_file)
        except Exception as e:
            print(
                f"[ERROR] Failed to save state file {self.state_file}: {e}")