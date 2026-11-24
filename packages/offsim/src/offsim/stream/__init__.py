"""Behave like a live tracking vendor: deliver, re-deliver, re-detect, over time."""

from .deliveries import Event, next_event, run_stream

__all__ = ["Event", "next_event", "run_stream"]
