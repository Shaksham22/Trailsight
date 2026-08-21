"""FastAPI integration for the deterministic Trailsight backend."""

from trailsight.api.app import create_app, create_investigation_service

__all__ = ["create_app", "create_investigation_service"]
