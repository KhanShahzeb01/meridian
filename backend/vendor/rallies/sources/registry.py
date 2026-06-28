import re

from ..ticker_identify import identify_query_tickers


class SourceResult:
    def __init__(self, source_name, data, error=None):
        self.source_name = source_name
        self.data = data
        self.error = error

    @property
    def success(self):
        return self.error is None

    def __bool__(self):
        return self.success

    def formatted(self):
        if self.error:
            return f"[red]{self.source_name} error:[/red] {self.error}"
        return self.data


# Backward-compatible alias used in a few legacy imports.
TICKER_RE = re.compile(r"\$?[A-Za-z]{1,6}(?:[.-][A-Za-z]{1,2})?")


def extract_tickers(text):
    """Identify tickers in a user query (delegates to ticker_identify)."""
    return identify_query_tickers(text)


class DataRegistry:
    def __init__(self):
        self._sources = []

    def register(self, source):
        self._sources.append(source)

    def get_source(self, name):
        for source in self._sources:
            if source.name == name:
                return source
        return None

    def resolve(self, text):
        tickers = extract_tickers(text)
        results = []
        for source in self._sources:
            if tickers:
                result = source.query(tickers, text)
                if result:
                    results.append(result)
        return results, tickers

    def resolve_first(self, text):
        results, tickers = self.resolve(text)
        return results[0] if results else None, tickers
