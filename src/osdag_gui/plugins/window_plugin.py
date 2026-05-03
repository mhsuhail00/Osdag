from PySide6.QtWidgets import (
    QApplication, 
    QDialog, 
    QVBoxLayout, 
    QPushButton, 
    QHBoxLayout, 
    QWidget, 
    QMainWindow,
    QSizePolicy, 
    QLabel,
    QTextEdit,
    QScrollArea
)
from osdag_gui.plugins.plugin_base import PluginBase

class WindowPlugin(PluginBase, QMainWindow):
    """Plugin that provides a Window."""
    def __init__(self, parent=None, title="Osdag Plugin"):
        super().__init__(parent)

    def setupUI(self, parent=None) -> None:
        """Setup UI of the Window."""
        super().setupUI()
        self.window = QMainWindow(parent=parent)

        return