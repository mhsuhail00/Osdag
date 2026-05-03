from PySide6.QtWidgets import (
    QApplication, 
    QDialog, 
    QVBoxLayout, 
    QPushButton, 
    QHBoxLayout, 
    QWidget, 
    QSizePolicy, 
    QLabel,
    QTextEdit,
    QScrollArea
)
from PySide6.QtCore import Qt , Signal, Slot
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtGui import QIcon
from osdag_gui.ui.components.dialogs.custom_titlebar import CustomTitleBar
from osdag_gui.data.ui_data import Data
from osdag_core.utils.plugin_manager import PluginManager, PluginMetaData
from osdag_gui.ui.components.dialogs.plugin_store_dialog import PluginStoreDialog

class StatusIndicator(QWidget):
    def __init__(self, plugin: PluginMetaData = None, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignCenter | Qt.AlignVCenter)
        layout.setSpacing(5)

        self.circle: QLabel = QLabel()
        self.circle.setFixedSize(12, 12)
        self.circle.setStyleSheet("border-radius: 6px; background-color: red;")

        self.text: QLabel = QLabel("Inactive")
        self.text.setStyleSheet(f"font-size: 9pt; font-weight: bold; color: red;")

        layout.addWidget(self.circle)
        layout.addWidget(self.text)

        self.update_status(plugin.status if plugin else False)

    def update_status(self, status: bool) -> None:
        if status:
            self.circle.setStyleSheet("border-radius: 6px; background-color: green;")
            self.text.setText("Active")
            self.text.setStyleSheet("color: green;")
        else:
            self.circle.setStyleSheet("border-radius: 6px; background-color: red;")
            self.text.setText("Inactive")
            self.text.setStyleSheet("color: red;")

class PluginWidget(QWidget):
    activate = Signal(PluginMetaData)
    deactivate = Signal(PluginMetaData)
    delete = Signal(PluginMetaData)

    def __init__(self, plugin: PluginMetaData, parent=None):
        super().__init__(parent)
        self.plugin = plugin
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)
    
        self.setStyleSheet("""
            PluginWidget {
                border: 1px solid #d0d0d0;
                border-radius: 6px;
                background-color: #ffffff;
            }
        """)

        # --- HEADER ROW ---
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(2, 2, 2, 2)
        header_layout.setSpacing(5)

        self.name_label = QLabel(f"{'<b>'+plugin.name+'</b> (Dev Plugin)' if plugin.is_dev else '<b>'+plugin.name+'</b>'}")
        self.name_label.setStyleSheet("font-weight: bold; font-size: 12pt; color: #90AF13;")
        self.status_indicator = StatusIndicator(plugin)

        header_layout.addWidget(self.name_label, alignment=Qt.AlignLeft)
        header_layout.addStretch()
        header_layout.addWidget(self.status_indicator, alignment=Qt.AlignRight)

        layout.addWidget(header)

        # --- CONTENT ROW ---
        content = QWidget()
        content_layout = QHBoxLayout(content)
        content_layout.setContentsMargins(10, 10, 10, 10)
        content_layout.setSpacing(15)

        # LEFT SIDE (description)
        self.content = QTextEdit()
        self.content.setReadOnly(True)
        content_text = f"{'<b>Author</b>' if len(self.plugin.authors) == 1 else '<b>Authors</b>'}: ({', '.join(author for author in self.plugin.authors)})"
        content_text += f"<br><b>Description</b>: {self.plugin.description}"
        self.content.setText(content_text)
        self.content.setMinimumHeight(100)
        self.content.setMaximumHeight(200)
        self.content.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.content.setStyleSheet("""
            QTextEdit {
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                font-size: 9.5pt;
                color: #444;
                background: #fafafa;
            }
        """)
        content_layout.addWidget(self.content, stretch=3)
 


       # RIGHT SIDE (buttons)
        btn_layout = QVBoxLayout()
        btn_layout.setContentsMargins(4, 4, 4, 4)
        btn_layout.setSpacing(10)

        self.btnActivate = QPushButton("Activate")
        self.btnDeactivate = QPushButton("Deactivate")
        self.btnDelete = QPushButton("Delete")

        for btn in (self.btnActivate, self.btnDeactivate, self.btnDelete):
            btn.setMinimumHeight(30)
            btn.setMinimumWidth(100)
            btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #90AF13;
                    color: white;
                    border: none;
                    border-radius: 5px;
                    font-size: 9pt;
                    font-weight: bold;
                    margin: 4px;
                }
                QPushButton:hover { background-color: #7A9611; }
                QPushButton:pressed { background-color: #6B850F; }
            """)
            btn_layout.addWidget(btn, 0, Qt.AlignRight) 

        content_layout.addLayout(btn_layout, stretch=1)

        layout.addWidget(content)

        # --- Button Callbacks ---
        self.btnActivate.clicked.connect(self._emit_activate)
        self.btnDeactivate.clicked.connect(self._emit_deactivate)
        self.btnDelete.clicked.connect(self._emit_delete)

        content_min_width = self.content.sizeHint().width() + 150 
        self.setMinimumWidth(content_min_width)
            
    def _emit_activate(self):
        if not self.plugin.status:
            self.plugin.status = not self.plugin.status
            self.status_indicator.update_status(self.plugin.status)
            self.activate.emit(self.plugin)

    def _emit_deactivate(self):
        if self.plugin.status:
            self.plugin.status = not self.plugin.status
            self.status_indicator.update_status(self.plugin.status)
            self.deactivate.emit(self.plugin)

    def _emit_delete(self):
        self.delete.emit(self.plugin)


class PluginManagerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.plugin_manager: PluginManager = QApplication.instance().plugin_manager
        self.plugins: list[PluginMetaData] = self.plugin_manager.discover_local_plugins()
        self.active_plugins: list[tuple[str, str]] = Data.MODULES["Add-Ons"]
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setObjectName("PluginManagerDialog")
        self.setWindowIcon(QIcon(":/images/osdag_logo.png"))
        self.setFixedSize(720, 600)

        # Layout and style
        self.setStyleSheet("""
            QDialog#PluginManagerDialog { background-color: #ffffff; border: 1px solid #90AF13; }
            QWidget#ContentWidget { background-color: #ffffff; }
            QPushButton { background-color: #90AF13; color: white; border: none; border-radius: 5px;
                          padding: 5px 20px; font-size: 12px; font-weight: bold; }
            QPushButton:hover { background-color: #7A9611; }
            QPushButton:pressed { background-color: #6B850F; }
        """)

        mainLayout = QVBoxLayout(self)
        mainLayout.setContentsMargins(1, 1, 1, 1)
        mainLayout.setSpacing(0)

        # Title bar
        self.titleBar = CustomTitleBar()
        self.titleBar.setTitle("Plugin Manager")
        mainLayout.addWidget(self.titleBar)

        # Content
        contentWidget = QWidget(self)
        contentWidget.setObjectName("ContentWidget")
        contentLayout = QVBoxLayout(contentWidget)
        contentLayout.setContentsMargins(10, 10, 10, 10)
        contentLayout.setSpacing(10)

        # Logo
        self.logoLabel = QSvgWidget(":/vectors/Osdag_light.svg", self)
        self.logoLabel.setMaximumHeight(100)
        self.logoLabel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        contentLayout.addWidget(self.logoLabel, 0, Qt.AlignLeft)

        # Scroll area for plugins
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: 0.5px solid black; background-color: #F0F0F0; }")
        contentLayout.addWidget(scroll)

        # Container for plugin widgets
        self.pluginContainer = QWidget()
        self.pluginLayout = QVBoxLayout(self.pluginContainer)
        self.pluginLayout.setAlignment(Qt.AlignTop)
        scroll.setWidget(self.pluginContainer)

        if len(self.plugins) > 0:
            print("\n===========Loaded Plugins===========\n")
            for plugin in self.plugins:
                print(f"    {plugin.name} by {', '.join(author for author in plugin.authors)}")
                if plugin.status:
                    print("     [INFO] Status: Active")
                    self.activate_plugin(plugin)
                else:
                    print("     [INFO] Status: Inactive")
                pw = PluginWidget(plugin=plugin, parent=self)
                pw.activate.connect(self.plugin_manager.activate)
                pw.activate.connect(self.activate_plugin)
                pw.deactivate.connect(self.plugin_manager.deactivate)
                pw.deactivate.connect(self.deactivate_plugin)
                pw.delete.connect(self.plugin_manager.delete_plugin)
                pw.setFixedHeight(120)
                pw.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                self.pluginLayout.addWidget(pw)
            print("\n=====================================\n")

        # Plugin Store button
        self.storeButton = QPushButton("Store", self)
        self.storeButton.setFixedHeight(30)
        self.storeButton.setStyleSheet("""
            QPushButton {
                background-color: #0078D7; color: white; border: none; border-radius: 5px;
                padding: 5px 20px; font-size: 12px; font-weight: bold;
            }
            QPushButton:hover { background-color: #0063B1; }
            QPushButton:pressed { background-color: #004E8C; }
        """)
        self.storeButton.clicked.connect(self.open_store_dialog)
        

        # OK button
        buttonLayout = QHBoxLayout()
        buttonLayout.addWidget(self.storeButton)
        buttonLayout.addStretch()
        self.okButton = QPushButton("OK", self)
        self.okButton.setFixedHeight(30)
        self.okButton.setStyleSheet("""
            QPushButton { background-color: #90AF13; color: white; border: none; border-radius: 5px;
                           padding: 5px 20px; font-size: 12px; font-weight: bold; }
            QPushButton:hover { background-color: #7A9611; }
            QPushButton:pressed { background-color: #6B850F; }
        """)
        self.okButton.clicked.connect(self.okClicked)
        buttonLayout.addWidget(self.okButton)

        contentLayout.addLayout(buttonLayout)
        mainLayout.addWidget(contentWidget)

    

    def activate_plugin(self, plugin: PluginMetaData):
        plugin = self.plugin_manager.get_plugin(plugin.id)
        if plugin and (plugin.name, ":/vectors/IITB_logo.svg") not in self.active_plugins:
            self.active_plugins.append((plugin.name, ":/vectors/IITB_logo.svg"))
    def deactivate_plugin(self, plugin: PluginMetaData):
        self.active_plugins[:] = [
            p for p in self.active_plugins if p[0] != plugin.name
        ]

    def delete_plugin(self, plugin: PluginMetaData):
        self.deactivate_plugin(plugin)
        self.plugin_manager.delete_plugin(plugin)
        self.refresh_plugin()
    
    def open_store_dialog(self):
        # print("[PLUGIN STORE] Opening Plugin Store Dialog...")
        store_dialog = PluginStoreDialog()
        store_dialog.exec() 


    def refresh_plugins(self):
        self.plugins = self.plugin_manager.discover_local_plugins()
        # Clear old plugin widgets
        for i in reversed(range(self.pluginLayout.count())):
            widget = self.pluginLayout.itemAt(i).widget()
            if widget:
                widget.setParent(None)

        # Re-add plugin widgets
        if len(self.plugins) > 0:
            for plugin in self.plugins:
                pw = PluginWidget(plugin=plugin, parent=self)
                pw.activate.connect(self.plugin_manager.activate)
                pw.activate.connect(self.activate_plugin)
                pw.deactivate.connect(self.plugin_manager.deactivate)
                pw.deactivate.connect(self.deactivate_plugin)
                pw.delete.connect(self.plugin_manager.delete_plugin)
                pw.setFixedHeight(120)
                pw.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                self.pluginLayout.addWidget(pw)

    def closeEvent(self, event):
        self.plugin_manager.state_manager.flush()
        super().closeEvent(event)           
    
    def okClicked(self):
        self.plugin_manager.state_manager.flush()
        self.accept()

# # Test the dialog
# if __name__ == "__main__":
#     app = QApplication(sys.argv)
#     dialog = PluginManagerDialog()
#     dialog.exec()
#     sys.exit(app.exec())