from osdag_gui.plugins.widget_plugin import WidgetPlugin
from PySide6.QtWidgets import QLabel, QPushButton, QLineEdit, QHBoxLayout, QDialog, QVBoxLayout

class DemoPlugin(WidgetPlugin):

    def __init__(self, parent=None, title="Demo Plugin"):
        super().__init__(parent, title)
        self.show_default_ui_message()
        
    def setupUI(self):
        super().setupUI()
        # Add simple form-like UI
        label = QLabel("Enter your name:")
        input_box = QLineEdit()
        input_box.setPlaceholderText("Type something...")
        button = QPushButton("Submit")

        row_layout = QHBoxLayout()
        row_layout.addWidget(label)
        row_layout.addWidget(input_box)
        row_layout.addWidget(button)

        self.layout.addLayout(row_layout)
        self.layout.addWidget(QLabel("This is a demo plugin UI!"))

    def show_default_ui_message(self):
        """Custom window/dialog to show default plugin UI info."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Osdag Plugin Info")

        dialog_layout = QVBoxLayout(dialog)
        message = QLabel(
            "<b>This is the default UI for an Osdag Plugin.</b><br>"
            "You can customize it by modifying the DemoPlugin class."
        )
        message.setWordWrap(True)
        ok_button = QPushButton("OK")
        ok_button.clicked.connect(dialog.accept)

        dialog_layout.addWidget(message)
        dialog_layout.addWidget(ok_button)

        dialog.exec()