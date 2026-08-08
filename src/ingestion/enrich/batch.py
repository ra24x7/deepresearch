from collections.abc import Callable


def run_batched[T, R](
    items: list[T],
    batch_fn: Callable[[list[T]], list[R]],
    item_fn: Callable[[T], R],
    on_error: Callable[[T, Exception], None],
    on_batch_error: Callable[[Exception], None] | None = None,
) -> tuple[list[R], list[T]]:
    if not items:
        return [], []

    try:
        return list(batch_fn(items)), []
    except Exception as exc:  # noqa: BLE001 - batch boundary; reported, then retried per item
        # The batch error is the only evidence of a systemic fault (bad
        # credentials, rejected mapping): per-item retries that all fail report
        # N symptoms and never the cause.
        if on_batch_error is not None:
            on_batch_error(exc)

    successes: list[R] = []
    failures: list[T] = []
    for item in items:
        try:
            successes.append(item_fn(item))
        except Exception as exc:  # noqa: BLE001 - generic per-item boundary, reported via on_error
            on_error(item, exc)
            failures.append(item)
    return successes, failures
