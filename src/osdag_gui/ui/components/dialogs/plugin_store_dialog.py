from packaging import version
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
from PySide6.QtCore import Qt, Signal, Slot, QObject, QThread, QTimer, QMetaObject
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtGui import QIcon
from osdag_gui.ui.components.dialogs.custom_titlebar import CustomTitleBar
from osdag_core.utils.plugin_manager import PluginMetaData


class Worker(QObject):
    finished = Signal(bool)

    def __init__(self, func, *args, **kwargs):
        super().__init__()
        self.func = func
        self.args = args
        self.kwargs = kwargs

    @Slot()
    def run(self):
        import threading
        try:
            result = self.func(*self.args, **self.kwargs)
            self.finished.emit(bool(result))
        except Exception as e:
            print(f"[WORKER] Exception: {e}")
            self.finished.emit(False)


class PluginWidget(QWidget):
    download = Signal(PluginMetaData)
    delete = Signal(PluginMetaData)
    update = Signal(PluginMetaData)

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

        self.name_label = QLabel(f"{'<b>'+plugin.name+'</b>'}")
        self.name_label.setStyleSheet(
            "font-weight: bold; font-size: 12pt; color: #90AF13;")
        # self.status_indicator = StatusIndicator(plugin)

        header_layout.addWidget(self.name_label, alignment=Qt.AlignLeft)
        # header_layout.addStretch()
        # header_layout.addWidget(self.status_indicator, alignment=Qt.AlignRight)

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
        self.content.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Expanding)
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

        self.btnDownload = QPushButton("Download")
        self.btnDelete = QPushButton("Delete")
        self.btnUpdate = QPushButton("Update")

        for btn in (self.btnDownload, self.btnDelete, self.btnUpdate):
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
        self.btnDelete.clicked.connect(self._emit_delete)
        self.btnDownload.clicked.connect(self._emit_download)
        self.btnUpdate.clicked.connect(self._emit_update)

        content_min_width = self.content.sizeHint().width() + 150
        self.setMinimumWidth(content_min_width)

    def _emit_download(self):
        self.download.emit(self.plugin)

    def _emit_delete(self):
        self.delete.emit(self.plugin)

    def _emit_update(self):
        self.update.emit(self.plugin)


class PluginStoreDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.plugin_manager = QApplication.instance().plugin_manager
        self.plugins: list[PluginMetaData] = self.plugin_manager.discover_online_plugins(
            channel="zehen-249")
        self.local_plugins: list[PluginMetaData] = self.plugin_manager.discover_local_plugins(
        )
        self.updates_available = self._check_for_updates()
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setObjectName("PluginManagerDialog")
        self.setWindowIcon(QIcon(":/images/osdag_logo.png"))

        mainLayout = QVBoxLayout(self)
        mainLayout.setContentsMargins(1, 1, 1, 1)
        mainLayout.setSpacing(0)

        # Title bar
        self.titleBar = CustomTitleBar()
        self.titleBar.setTitle("Plugin Store")
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
        scroll.setStyleSheet(
            "QScrollArea { border: 0.5px solid black; background-color: #F0F0F0; }")
        contentLayout.addWidget(scroll)

        # Container for plugin widgets
        self.pluginContainer = QWidget()
        self.pluginLayout = QVBoxLayout(self.pluginContainer)
        self.pluginLayout.setAlignment(Qt.AlignTop)
        scroll.setWidget(self.pluginContainer)

        # Populate plugins in the scroll area
        self._populate_plugins()

        # OK button
        buttonLayout = QHBoxLayout()
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

    def delete_plugin(self, plugin: PluginMetaData, widget: PluginWidget):
        widget.btnDelete.setEnabled(False)
        widget.name_label.setText(f"<b>{plugin.name} (Deleting...)</b>")
        QApplication.processEvents()  # ensures repaint before thread starts

        thread = QThread()
        worker = Worker(self.plugin_manager.delete_plugin, plugin)
        worker.moveToThread(thread)

        # Connect signals
        thread.started.connect(lambda: self.start_worker(worker))
        worker.finished.connect(
            lambda success: self._on_delete_finished(success, widget, plugin))
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)

        # Keep a reference so thread isn’t Garbagecollected
        if not hasattr(self, "plugin_store_threads"):
            self.plugin_store_threads = []
        self.plugin_store_threads.append(thread)
        thread.finished.connect(
            lambda: self.plugin_store_threads.remove(thread))
        thread.start()

    def _on_delete_finished(self, success, widget, plugin):
        if success:
            print(f"[INFO] Successfully deleted plugin: {plugin.name}")
            widget.btnDelete.setVisible(False)
            widget.btnDownload.setVisible(True)
            widget.btnDownload.setEnabled(True)
            widget.name_label.setText(f"<b>{plugin.name}</b>")
        else:
            print(f"[INFO] Failed to delete plugin: {plugin.name}")
            widget.name_label.setText(f"<b>{plugin.name} (Downloaded)</b>")
            widget.btnDelete.setEnabled(True)

    def download_plugin(self, plugin: PluginMetaData, widget: PluginWidget):
        widget.btnDownload.setEnabled(False)
        widget.name_label.setText(f"<b>{plugin.name} (Downloading...)</b>")
        QApplication.processEvents()  # ensures repaint before thread starts

        thread = QThread()
        worker = Worker(self.plugin_manager.download_plugin, plugin)
        worker.moveToThread(thread)

        # Connect signals
        thread.started.connect(lambda: self.start_worker(worker))
        worker.finished.connect(
            lambda success: self._on_download_finished(success, widget, plugin))
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)

        # Keep a reference so thread isn’t Garbagecollected
        if not hasattr(self, "plugin_store_threads"):
            self.plugin_store_threads = []
        self.plugin_store_threads.append(thread)
        thread.finished.connect(
            lambda: self.plugin_store_threads.remove(thread))
        thread.start()

    def _on_download_finished(self, success, widget, plugin):
        if success:
            print(f"[INFO] Successfully downloaded plugin: {plugin.name}")
            widget.btnDownload.setVisible(False)
            widget.btnDelete.setVisible(True)
            widget.btnDelete.setEnabled(True)
            widget.name_label.setText(f"<b>{plugin.name} (Downloaded)</b>")
        else:
            print(f"[INFO] Failed to download plugin: {plugin.name}")
            widget.name_label.setText(f"<b>{plugin.name}</b>")
            widget.btnDownload.setEnabled(True)

    def update_plugin(self, plugin: PluginMetaData, widget: PluginWidget):
        widget.btnUpdate.setEnabled(False)
        widget.name_label.setText(f"<b>{plugin.name} (Updating...)</b>")
        QApplication.processEvents()  # ensures repaint before thread starts

        thread = QThread()
        worker = Worker(self.plugin_manager.update_plugin, plugin)
        worker.moveToThread(thread)

        # Connect signals
        thread.started.connect(lambda: self.start_worker(worker))
        worker.finished.connect(
            lambda success: self._on_update_finished(success, widget, plugin))
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)

        # Keep a reference so thread isn’t Garbagecollected
        if not hasattr(self, "plugin_store_threads"):
            self.plugin_store_threads = []
        self.plugin_store_threads.append(thread)
        thread.finished.connect(
            lambda: self.plugin_store_threads.remove(thread))
        thread.start()

    def _on_update_finished(self, success, widget, plugin):
        if success:
            print(f"[INFO] Successfully updated plugin: {plugin.name}")
            widget.btnUpdate.setVisible(False)
            widget.btnDownload.setVisible(False)
            widget.btnDelete.setVisible(True)
            widget.btnDelete.setEnabled(True)
            widget.name_label.setText(f"<b>{plugin.name} (Downloaded)</b>")
        else:
            print(f"[INFO] Failed to update plugin: {plugin.name}")
            widget.name_label.setText(
                f"<b>{plugin.name} (Update Available)</b>")
            widget.btnUpdate.setEnabled(True)

    def start_worker(self, worker):
        QMetaObject.invokeMethod(worker, "run", Qt.QueuedConnection)

    def refresh_plugins(self):
        # Re-discover both local and online plugins
        self.plugins = self.plugin_manager.discover_online_plugins()
        self.local_plugins = self.plugin_manager.discover_local_plugins()

        # Clear all plugin widgets from the layout
        for i in reversed(range(self.pluginLayout.count())):
            widget = self.pluginLayout.itemAt(i).widget()
            if widget:
                widget.setParent(None)

        # Rebuild plugin list widgets
        self._populate_plugins()

    def _populate_plugins(self):

        def safe_parse_version(ver_string):
            """Safely parse version, returning 0.0.0 for invalid versions."""
            try:
                return version.parse(ver_string)
            except Exception:
                return version.parse("0.0.0")

        latest = {}
        for plugin in self.plugins:
            if plugin.name not in latest:
                latest[plugin.name] = plugin
            else:
                if safe_parse_version(plugin.version) > safe_parse_version(latest[plugin.name].version):
                    latest[plugin.name] = plugin

        self.plugins = list(latest.values())

        for plugin in self.plugins:
            pw = PluginWidget(plugin=plugin, parent=self)

            pw.download.connect(
                lambda plugin, w=pw: self.download_plugin(plugin, w))
            pw.delete.connect(
                lambda plugin, w=pw: self.delete_plugin(plugin, w))
            pw.update.connect(
                lambda plugin, w=pw: self.update_plugin(plugin, w))

            pw.setFixedHeight(120)
            pw.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

            is_downloaded = any(
                lp.name == plugin.name for lp in self.local_plugins)

            if is_downloaded:
                is_update_available = any(
                    up.name == plugin.name for up in self.updates_available)

                if is_update_available:
                    pw.name_label.setText(
                        f"<b>{plugin.name} (Update Available)</b>")
                    pw.btnDownload.setVisible(False)
                    pw.btnUpdate.setVisible(True)
                    pw.btnUpdate.setEnabled(True)
                    pw.btnDelete.setVisible(True)
                    pw.btnDelete.setEnabled(True)
                else:
                    pw.name_label.setText(f"<b>{plugin.name} (Downloaded)</b>")
                    pw.btnDownload.setVisible(False)
                    pw.btnUpdate.setVisible(False)
                    pw.btnDelete.setVisible(True)
                    pw.btnDelete.setEnabled(True)

            else:
                pw.name_label.setText(f"<b>{plugin.name}</b>")
                pw.btnDownload.setVisible(True)
                pw.btnDownload.setEnabled(True)
                pw.btnUpdate.setVisible(False)
                pw.btnDelete.setVisible(False)

            self.pluginLayout.addWidget(pw)

    def _check_for_updates(self):
        installed_plugins = self.plugin_manager.discover_local_plugins()
        online_plugins = self.plugin_manager.discover_online_plugins(
            channel="zehen-249")
        updates_available = []
        for installed in installed_plugins:
            for online in online_plugins:
                if online.name != installed.name:
                    continue

                try:
                    if version.parse(online.version) > version.parse(installed.version):
                        updates_available.append(online)
                except Exception:
                    # If version parsing fails, skip this comparison
                    pass

        return updates_available

    def closeEvent(self, event):
        self.plugin_manager.state_manager.flush()
        self._refreshManager()
        super().closeEvent(event)

    def okClicked(self):
        self.plugin_manager.state_manager.flush()
        self._refreshManager()
        self.accept()

    def _refreshManager(self):
        self.plugin_manager_dialog = QApplication.instance().plugin_manager_dialog
        self.plugin_manager_dialog.refresh_plugins()
