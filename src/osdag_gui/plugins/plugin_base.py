class PluginBase:
    """Base class for all Osdag plugins."""
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    def setupUI(self) -> None:
        """Setup UI for the Plugin"""
        pass