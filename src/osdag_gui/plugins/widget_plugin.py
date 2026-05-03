from abc import abstractmethod
from PySide6.QtWidgets import (
    QVBoxLayout,  
    QWidget, 
    QLabel,
)
from osdag_gui.plugins.plugin_base import PluginBase

class WidgetPlugin(PluginBase, QWidget):
    """Base class for widget-based plugins."""

    def __init__(self, parent: QWidget = None, title: str = "Default Title") -> None:
        super().__init__(parent)
        self.title = title

    def setupUI(self) -> None:
        """Override in subclass to create your plugin's UI."""
        self.layout = QVBoxLayout(self)
        label = QLabel(f"Default UI for {self.title}")
        self.layout.addWidget(label)