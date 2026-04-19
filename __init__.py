from . import properties, operators, panels, previews


def register():
    previews.register()
    properties.register()
    operators.register()
    panels.register()


def unregister():
    panels.unregister()
    operators.unregister()
    properties.unregister()
    previews.unregister()


if __name__ == "__main__":
    register()
