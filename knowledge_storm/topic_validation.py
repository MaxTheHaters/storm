"""Validation for topics used as directory names by the STORM runner."""
import re
import unicodedata


def validate_topic(topic):
    if not isinstance(topic, str) or not topic.strip():
        return "empty"
    if len(topic) > 125 or len(topic.encode("utf-8", errors="surrogatepass")) > 240 or len(topic.split()) > 20:
        return "too_long"
    # Reject path separators, control characters and Windows-invalid names on every OS.
    if (topic != topic.strip() or topic.endswith(".") or
        any(c in '<>:"/\\|?*' or unicodedata.category(c).startswith("C") for c in topic) or
        topic in {".", ".."} or
        re.match(r"^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)", topic, re.I)):
        return "invalid"
    return None
