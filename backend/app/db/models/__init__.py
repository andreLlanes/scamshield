"""ORM models. Importing this package registers every table on ``Base``."""

from app.db.models.analysis import Analysis

__all__ = ["Analysis"]
