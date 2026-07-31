import contextlib
from collections.abc import Callable


def run_batched[T, R](
    items: list[T],
    batch_fn: Callable[[list[T]], list[R]],
    item_fn: Callable[[T], R],
    on_error: Callable[[T, Exception], None],
) -> tuple[list[R], list[T]]:
    if not items:
        return [], []

    with contextlib.suppress(Exception):
        return list(batch_fn(items)), []

    successes: list[R] = []
    failures: list[T] = []
    for item in items:
        try:
            successes.append(item_fn(item))
        except Exception as exc:  # noqa: BLE001 - generic per-item boundary, reported via on_error
            on_error(item, exc)
            failures.append(item)
    return successes, failures
