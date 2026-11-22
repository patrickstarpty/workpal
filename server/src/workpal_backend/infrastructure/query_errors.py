"""Domain-neutral canonical query outcomes."""
class NoRows(LookupError):
    """A query found no row, distinct from database or decoding failure."""
