"""In-memory fake of ``ObjectStorageClient`` keyed by (bucket, key)."""

from src.app.exceptions.storage import ObjectNotFoundError
from src.app.interfaces.storage.object_storage_client import ObjectStorageClient, StorageBucket

RealBucket = tuple[str, str]


class FakeObjectStorageClient(ObjectStorageClient):
    """Stores objects in a dict; optionally raises a configured error.

    Mirrors the fake of faq-assistant: besides plain storage it records
    every call so unit tests can assert on interactions, and can turn
    every operation into an ``ObjectStorageError`` to test error paths.
    """

    def __init__(
        self,
        *,
        objects: dict[RealBucket, bytes] | None = None,
        error: Exception | None = None,
    ) -> None:
        self._objects = dict(objects or {})
        self._error = error
        self.put_object_calls: list[tuple[StorageBucket, str, bytes, str]] = []
        self.get_object_calls: list[tuple[StorageBucket, str]] = []
        self.delete_object_calls: list[tuple[StorageBucket, str]] = []
        self.presign_get_url_calls: list[tuple[StorageBucket, str, int | None]] = []
        self.ping_calls: list[int] = []

    async def put_object(self, *, bucket: StorageBucket, key: str, data: bytes, content_type: str) -> None:
        self._raise_if_configured()
        self.put_object_calls.append((bucket, key, data, content_type))
        self._objects[(bucket, key)] = data

    async def get_object(self, *, bucket: StorageBucket, key: str) -> bytes:
        self._raise_if_configured()
        self.get_object_calls.append((bucket, key))
        try:
            return self._objects[(bucket, key)]
        except KeyError as exc:
            raise ObjectNotFoundError(f"Object not found: {key}") from exc

    async def delete_object(self, *, bucket: StorageBucket, key: str) -> None:
        self._raise_if_configured()
        self.delete_object_calls.append((bucket, key))
        self._objects.pop((bucket, key), None)

    def presign_get_url(
        self,
        *,
        bucket: StorageBucket,
        key: str,
        expires_seconds: int | None = None,
    ) -> str:
        self._raise_if_configured()
        self.presign_get_url_calls.append((bucket, key, expires_seconds))
        ttl = expires_seconds if expires_seconds is not None else 3600
        return f"http://storage.local/{bucket}/{key}?expires={ttl}"

    async def ping(self) -> bool:
        self._raise_if_configured()
        self.ping_calls.append(1)
        return True

    def _raise_if_configured(self) -> None:
        if self._error is not None:
            raise self._error
