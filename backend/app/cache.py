from datetime import datetime, timedelta


class DataCache:
    def __init__(self, ttl_seconds: int = 300):
        self.ttl = timedelta(seconds=ttl_seconds)
        self._items: dict[str, tuple[datetime, object]] = {}

    def get(self, key: str):
        item = self._items.get(key)
        if item and datetime.utcnow() - item[0] < self.ttl:
            return item[1]
        return None

    def set(self, key: str, value: object):
        self._items[key] = (datetime.utcnow(), value)

    def clear(self):
        self._items.clear()
