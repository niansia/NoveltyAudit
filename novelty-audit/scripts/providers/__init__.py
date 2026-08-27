"""Scholarly provider adapters."""

from .arxiv import ArxivProvider
from .crossref import CrossrefProvider
from .openalex import OpenAlexProvider
from .semantic_scholar import SemanticScholarProvider

PROVIDERS = {
    "openalex": OpenAlexProvider,
    "semantic-scholar": SemanticScholarProvider,
    "semantic_scholar": SemanticScholarProvider,
    "arxiv": ArxivProvider,
    "crossref": CrossrefProvider,
}

# Crossref is reserved for DOI and metadata verification, not primary semantic retrieval.
SEARCH_PROVIDERS = {name: provider for name, provider in PROVIDERS.items() if name != "crossref"}
