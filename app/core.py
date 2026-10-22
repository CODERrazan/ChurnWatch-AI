"""Compatibility imports for earlier ChurnWatch versions. No model is trained here."""
from .banking import DATA_DIR, DataBundle, assess, dashboard, groq_analysis, load_bundle

__all__ = ["DATA_DIR", "DataBundle", "assess", "dashboard", "groq_analysis", "load_bundle"]
