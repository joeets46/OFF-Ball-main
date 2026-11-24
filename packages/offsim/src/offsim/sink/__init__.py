"""Where generated rows go: PostgreSQL, or vendor-style files on disk."""

from .files import FileSink
from .postgres import PostgresSink

__all__ = ["FileSink", "PostgresSink"]
