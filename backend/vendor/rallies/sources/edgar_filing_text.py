"""Human-readable text for EDGAR filing rows (8-K items, etc.)."""

from __future__ import annotations

# Common 8-K item codes → short label (SEC Form 8-K item numbers)
ITEM_8K_LABELS: dict[str, str] = {
    "1.01": "Material definitive agreement",
    "1.02": "Termination of material agreement",
    "2.01": "Completion of acquisition/disposition",
    "2.02": "Results of operations / financial condition",
    "2.03": "Creation of direct financial obligation",
    "2.04": "Triggering events (obligations)",
    "2.05": "Costs from exit/disposal activities",
    "2.06": "Material impairments",
    "3.01": "Delisting / failure to satisfy listing",
    "3.02": "Unregistered sales of equity securities",
    "3.03": "Material modification to shareholder rights",
    "4.01": "Change in accountant",
    "4.02": "Non-reliance on prior financial statements",
    "5.01": "Changes in control of registrant",
    "5.02": "Departure/election of directors or officers",
    "5.03": "Amendments to articles/bylaws",
    "5.04": "Temporary suspension of trading",
    "5.05": "Amendments to code of ethics",
    "5.06": "Change in shell company status",
    "5.07": "Submission of matters to vote",
    "5.08": "Shareholder director nominations",
    "7.01": "Regulation FD disclosure",
    "8.01": "Other events",
    "9.01": "Financial statements and exhibits",
}


def label_8k_item(code: str) -> str:
    c = code.strip().lstrip("Item ").strip()
    if c in ITEM_8K_LABELS:
        return ITEM_8K_LABELS[c]
    return f"Item {c}" if c else ""


def format_items_string(items: str | None) -> str:
    if not items or not str(items).strip():
        return ""
    parts = []
    for raw in str(items).replace(";", ",").split(","):
        code = raw.strip().lstrip("Item ").strip()
        if code:
            parts.append(label_8k_item(code))
    return "; ".join(parts)


def format_items_list(items: list | None) -> str:
    if not items:
        return ""
    codes = []
    for entry in items:
        text = str(entry).strip()
        if text.startswith("Item "):
            text = text[5:].strip()
        if text:
            codes.append(label_8k_item(text))
    return "; ".join(codes)


def extract_filing_description(filing) -> str:
    """Best-effort label for a filing row (edgartools often omits .description)."""
    desc = getattr(filing, "description", None)
    if isinstance(desc, str) and desc.strip():
        return desc.strip()

    items_text = format_items_string(getattr(filing, "items", None))
    if items_text:
        return items_text

    try:
        obj = filing.obj() if callable(getattr(filing, "obj", None)) else None
    except Exception:
        obj = None

    if obj is not None:
        for attr in ("description", "summary"):
            val = getattr(obj, attr, None)
            if isinstance(val, str) and val.strip():
                return val.strip()
        obj_items = format_items_list(getattr(obj, "items", None))
        if obj_items:
            return obj_items

    primary = getattr(filing, "primary_document", None)
    if isinstance(primary, str) and primary.strip():
        return primary.strip()

    accession = getattr(filing, "accession_no", None)
    if isinstance(accession, str) and accession.strip():
        return accession.strip()

    return ""
