from typing import Any

from retrieval.channels.exceptions import SearchResponseError


def hits_of(response: Any, index_name: str) -> list[dict]:
    """Read the hit list out of an OpenSearch response.

    A response without a hits envelope means the request never ran as a search
    (a shard failure, an error body, a missing index). Defaulting to an empty
    list there makes a broken index look like a query nothing matched.
    """
    try:
        return response["hits"]["hits"]
    except (KeyError, TypeError) as exc:
        raise SearchResponseError(f"search on {index_name} returned no hits envelope: {response!r}") from exc
