import logging
import os

from .registry import SourceResult

logger = logging.getLogger(__name__)


class RedditSource:
    name = "reddit"

    def __init__(self):
        self.client_id = os.environ.get("REDDIT_CLIENT_ID", "")
        self.client_secret = os.environ.get("REDDIT_CLIENT_SECRET", "")

    @property
    def available(self):
        return bool(self.client_id) and bool(self.client_secret)

    def query(self, tickers, context=""):
        if not self.available:
            return SourceResult(self.name, None, error="Reddit API not configured. Set REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET")
        return None

    def get_trending_tickers(self):
        if not self.available:
            return None
        return None  # TODO: implement when Reddit API key is added
