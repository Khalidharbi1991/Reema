"""Snafi step 6: Ahmad's memory of Khalid and his family (facts, family, key dates, the interview).

Importing this package registers its adapters: memory "store" (StoreMemoryBook) and memory_search
"keyword" (KeywordSearch), chosen in worker.yaml under memory.
"""

from . import search, store_book  # noqa: F401 (registers the adapters)
