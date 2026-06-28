"""SEC filing section reader (edgartools, not Financial Datasets)."""

from .nl_router import FilingRoute, infer_form, route_filing_section
from .section_fetch import fetch_filing_section, format_filing_section

__all__ = [
    "FilingRoute",
    "infer_form",
    "route_filing_section",
    "fetch_filing_section",
    "format_filing_section",
]
