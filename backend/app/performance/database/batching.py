from __future__ import annotations


def chunks(items: list, size: int):
    for index in range(0, len(items), size):
        yield items[index:index + size]
