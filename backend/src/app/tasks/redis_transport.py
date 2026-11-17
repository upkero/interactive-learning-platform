"""Preserve worker queue order when Kombu selects Redis priority queues.

Kombu's Redis channel exposes active_queues as a set, so its ``priority``
cycle otherwise receives an arbitrary order instead of the worker's -Q order.
"""

from kombu.transport.redis import Channel, Transport


class OrderedChannel(Channel):  # type: ignore[misc]
    @property
    def active_queues(self) -> list[str]:
        return list(dict.fromkeys(queue for queue in self._active_queues if queue not in self.active_fanout_queues))


class OrderedRedisTransport(Transport):  # type: ignore[misc]
    Channel = OrderedChannel
