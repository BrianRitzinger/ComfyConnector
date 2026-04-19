import bpy.utils.previews

_collection = None


def register():
    global _collection
    _collection = bpy.utils.previews.new()


def unregister():
    global _collection
    if _collection is not None:
        bpy.utils.previews.remove(_collection)
        _collection = None


def load_preview(filepath: str) -> int:
    """Load image from filepath and return its icon_value id (0 if failed)."""
    if not filepath or _collection is None:
        return 0
    if filepath not in _collection:
        try:
            _collection.load(filepath, filepath, "IMAGE")
        except Exception:
            return 0
    return _collection[filepath].icon_id
