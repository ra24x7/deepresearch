from ingestion.enrich.batch import run_batched


class TestRunBatched:
    def test_empty_items_returns_empty_successes_and_failures(self):
        successes, failures = run_batched([], lambda items: items, lambda item: item, lambda item, exc: None)

        assert successes == []
        assert failures == []

    def test_batch_success_returns_batch_results_directly(self):
        def batch_fn(items):
            return [i * 2 for i in items]

        successes, failures = run_batched([1, 2, 3], batch_fn, lambda item: item, lambda item, exc: None)

        assert successes == [2, 4, 6]
        assert failures == []

    def test_batch_failure_falls_back_to_per_item_processing(self):
        def batch_fn(items):
            raise RuntimeError("batch endpoint down")

        successes, failures = run_batched([1, 2, 3], batch_fn, lambda item: item * 10, lambda item, exc: None)

        assert successes == [10, 20, 30]
        assert failures == []

    def test_one_item_failure_in_fallback_is_recorded_and_others_continue(self):
        def batch_fn(items):
            raise RuntimeError("batch endpoint down")

        def item_fn(item):
            if item == 2:
                raise ValueError("bad item")
            return item * 10

        errors = []

        def on_error(item, exc):
            errors.append((item, str(exc)))

        successes, failures = run_batched([1, 2, 3], batch_fn, item_fn, on_error)

        assert successes == [10, 30]
        assert failures == [2]
        assert errors == [(2, "bad item")]

    def test_all_items_failing_in_fallback_returns_all_as_failures_without_raising(self):
        def batch_fn(items):
            raise RuntimeError("batch endpoint down")

        def item_fn(item):
            raise ValueError(f"fail {item}")

        errors = []
        successes, failures = run_batched([1, 2], batch_fn, item_fn, lambda item, exc: errors.append((item, exc)))

        assert successes == []
        assert failures == [1, 2]
        assert len(errors) == 2

    def test_batch_failure_is_reported_before_the_per_item_fallback(self):
        def batch_fn(items):
            raise RuntimeError("batch endpoint down")

        seen = []
        run_batched([1, 2], batch_fn, lambda item: item, lambda item, exc: None, on_batch_error=seen.append)

        assert [str(exc) for exc in seen] == ["batch endpoint down"]

    def test_no_batch_error_is_reported_when_the_batch_succeeds(self):
        seen = []
        run_batched([1], lambda items: items, lambda item: item, lambda item, exc: None, on_batch_error=seen.append)

        assert seen == []
