"""Provider registry: lists available providers and resolves the active one.

This is the single lookup point for the rest of the app. The GUI dialog
writes credentials via credential_store; the registry reads them back
and hands out configured provider instances.
"""

from __future__ import annotations

import logging
from typing import Any

from shared.ai.credential_store import (
    get_active_provider_id,
    get_provider_credentials,
    load_credentials,
    set_active_provider_id,
)
from shared.ai.providers.base import BaseProvider, ProviderInfo

_logger = logging.getLogger("ai_provider_registry")

# Lazy-loaded provider instances (one per provider id)
_providers: dict[str, BaseProvider] = {}


def _ensure_providers() -> dict[str, BaseProvider]:
    """Lazy-init all known provider classes."""
    if _providers:
        return _providers

    from shared.ai.providers.claude_provider import ClaudeProvider
    from shared.ai.providers.gemini_provider import GeminiProvider
    from shared.ai.providers.local_provider import LocalProvider
    from shared.ai.providers.openai_provider import OpenAIProvider

    _providers["claude"] = ClaudeProvider()
    _providers["openai"] = OpenAIProvider()
    _providers["gemini"] = GeminiProvider()
    _providers["local"] = LocalProvider()
    return _providers


def list_providers() -> list[ProviderInfo]:
    """Return metadata for all known providers (cloud first, then local)."""
    providers = _ensure_providers()
    cloud = [p.info() for p in providers.values() if p.info().category == "cloud"]
    local = [p.info() for p in providers.values() if p.info().category == "local"]
    return cloud + local


def get_provider(provider_id: str) -> BaseProvider | None:
    """Get a provider instance by id. Returns None if unknown."""
    providers = _ensure_providers()
    return providers.get(provider_id)


def get_configured_provider(provider_id: str) -> BaseProvider | None:
    """Get a provider instance with saved credentials applied."""
    provider = get_provider(provider_id)
    if provider is None:
        return None
    creds = get_provider_credentials(provider_id)
    if creds:
        provider.configure(**creds)
    return provider


def resolve_active_cloud_provider() -> BaseProvider | None:
    """Return the user's chosen cloud provider, fully configured.

    Falls back through providers if the active one is not available:
    1. Explicit active provider (from credential_store)
    2. First cloud provider that has saved credentials
    3. None
    """
    active_id = get_active_provider_id()
    if active_id:
        provider = get_configured_provider(active_id)
        if provider and provider.is_available():
            return provider

    # Fallback: find any cloud provider with credentials
    all_creds = load_credentials()
    providers = _ensure_providers()
    for pid, p in providers.items():
        if p.info().category != "cloud":
            continue
        creds = all_creds.get(pid, {})
        if creds.get("api_key"):
            p.configure(**creds)
            if p.is_available():
                set_active_provider_id(pid)
                return p

    return None


def resolve_local_provider() -> BaseProvider | None:
    """Return the local provider, fully configured."""
    return get_configured_provider("local")


def resolve_provider_for_mode(mode: str) -> BaseProvider | None:
    """Given an AI mode ('off'/'cloud'/'local'), return the right provider.

    For 'cloud' mode, returns the active cloud provider.
    For 'local' mode, returns the local provider.
    For 'off', returns None.
    """
    if mode == "off":
        return None
    if mode == "local":
        return resolve_local_provider()
    if mode == "cloud":
        return resolve_active_cloud_provider()
    return None


def get_connection_summary() -> dict[str, dict[str, Any]]:
    """Return a summary of all providers and their connection state.

    Used by the AI provider dialog to show current status.
    """
    providers = _ensure_providers()
    all_creds = load_credentials()
    active_id = get_active_provider_id()
    summary: dict[str, dict[str, Any]] = {}

    for pid, provider in providers.items():
        info = provider.info()
        creds = all_creds.get(pid, {})
        has_key = bool(creds.get("api_key")) if info.requires_api_key else True
        model = creds.get("model", info.default_model)

        summary[pid] = {
            "display_name": info.display_name,
            "category": info.category,
            "has_credentials": has_key,
            "model": model,
            "is_active": pid == active_id,
            "help_url": info.help_url,
        }

    return summary
