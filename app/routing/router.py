"""Intelligent, deterministic model routing engine."""

import os
from typing import Callable, Dict, Optional

import yaml

from app.api.schemas import ChatCompletionRequest
from app.core.exceptions import ModelNotFoundError
from app.core.logging import logger
from app.routing.policies import ModelCatalogEntry, RoutingDecision


class ModelRouter:
    """Evaluates request attributes and resolves models to primary and fallback providers."""

    def __init__(self, config_path: str = "config/models.yaml"):
        self.config_path = config_path
        self.models: Dict[str, ModelCatalogEntry] = {}
        self.aliases: Dict[str, str] = {}
        self.task_routing: Dict[str, str] = {}
        self._load_config()

    def _load_config(self) -> None:
        """Loads configuration from YAML file with resilient defaults."""
        data = {}
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
            except Exception as e:
                logger.error(f"Failed to read models config from {self.config_path}: {e}")

        raw_models = data.get("models", {})
        if not raw_models:
            # Fallback default models if YAML missing
            raw_models = {
                "mock-model": {
                    "description": "Default mock model",
                    "tier": "cheap",
                    "max_tokens": 4096,
                    "capabilities": ["chat", "mock"],
                    "input_cost_per_1k": 0.0001,
                    "output_cost_per_1k": 0.0002,
                    "providers": {"primary": "mock-primary", "fallbacks": ["mock-secondary"]},
                },
                "gpt-4o-mini": {
                    "description": "Default fast model",
                    "tier": "balanced",
                    "max_tokens": 16384,
                    "capabilities": ["chat", "code"],
                    "input_cost_per_1k": 0.00015,
                    "output_cost_per_1k": 0.0006,
                    "providers": {
                        "primary": "mock-primary",
                        "fallbacks": ["mock-secondary", "openai-main"],
                    },
                },
            }

        for model_id, item in raw_models.items():
            providers = item.get("providers", {})
            self.models[model_id] = ModelCatalogEntry(
                name=model_id,
                description=item.get("description", ""),
                tier=item.get("tier", "balanced"),
                max_tokens=item.get("max_tokens", 4096),
                capabilities=item.get("capabilities", []),
                input_cost_per_1k=item.get("input_cost_per_1k", 0.001),
                output_cost_per_1k=item.get("output_cost_per_1k", 0.002),
                primary_provider=providers.get("primary", "mock-primary"),
                fallback_providers=providers.get("fallbacks", []),
            )

        self.aliases = data.get(
            "aliases",
            {
                "cheap": "mock-model",
                "balanced": "gpt-4o-mini",
                "powerful": "gpt-4o-mini",
                "default": "mock-model",
            },
        )
        self.task_routing = data.get(
            "task_routing",
            {
                "summarization": "cheap",
                "coding": "powerful",
                "chat": "balanced",
                "extraction": "cheap",
            },
        )

    def route(
        self,
        request: ChatCompletionRequest,
        circuit_open_checker: Optional[Callable[[str], bool]] = None,
        provider_enabled_checker: Optional[Callable[[str], bool]] = None,
    ) -> RoutingDecision:
        """Determines target model, primary provider, and ordered fallback chain."""
        requested = request.model.strip()
        reason = "direct_model_selection"

        # 1. Check task_type hint if present and model is 'default' or matches an alias
        target_model_name = requested
        if request.task_type and request.task_type.lower() in self.task_routing:
            suggested_alias = self.task_routing[request.task_type.lower()]
            if requested in ("default", "auto", "") or requested in self.aliases:
                target_model_name = self.aliases.get(suggested_alias, suggested_alias)
                reason = (
                    f"task_hint:{request.task_type}->alias:{suggested_alias}->{target_model_name}"
                )

        # 2. Check alias mapping
        if target_model_name in self.aliases:
            resolved = self.aliases[target_model_name]
            reason = f"alias:{target_model_name}->{resolved}"
            target_model_name = resolved

        # 3. Check prompt length rule: if prompt > 2000 words and using cheap model, escalate if balanced available
        total_words = sum(len(m.content.split()) for m in request.messages)
        if total_words > 2000 and target_model_name == self.aliases.get("cheap"):
            balanced = self.aliases.get("balanced")
            if balanced and balanced in self.models:
                target_model_name = balanced
                reason = f"long_prompt({total_words}_words)->escalated_to_{target_model_name}"

        # 4. Lookup model in catalog
        if target_model_name not in self.models:
            # If not in catalog, check if any catalog model contains requested name
            matched = next(
                (m for m in self.models if m in target_model_name or target_model_name in m), None
            )
            if matched:
                target_model_name = matched
                reason += f";fallback_substring_match->{target_model_name}"
            else:
                # If still not found, check if "default" alias exists
                default_model = self.aliases.get("default")
                if default_model and default_model in self.models:
                    reason = f"unknown_model:{requested}->default:{default_model}"
                    target_model_name = default_model
                else:
                    raise ModelNotFoundError(requested)

        model_entry = self.models[target_model_name]

        # 5. Build candidate provider chain
        candidate_providers = [model_entry.primary_provider] + [
            p for p in model_entry.fallback_providers if p != model_entry.primary_provider
        ]

        # 6. Filter by enabled status and circuit breaker state
        eligible_providers = []
        for provider_name in candidate_providers:
            if provider_enabled_checker and not provider_enabled_checker(provider_name):
                continue
            if circuit_open_checker and circuit_open_checker(provider_name):
                logger.info(
                    f"Router skipping provider '{provider_name}' because circuit breaker is OPEN"
                )
                continue
            eligible_providers.append(provider_name)

        if not eligible_providers:
            # If all circuit breakers are open or disabled, include primary provider anyway
            # so the circuit breaker error / attempt can be officially tracked
            eligible_providers = candidate_providers[:1]
            reason += ";all_candidates_degraded"

        primary = eligible_providers[0]
        fallbacks = eligible_providers[1:]

        logger.info(
            f"Routing decision: requested='{requested}', target='{target_model_name}', "
            f"primary='{primary}', fallbacks={fallbacks}, reason='{reason}'"
        )

        return RoutingDecision(
            requested_model=requested,
            target_model=target_model_name,
            primary_provider=primary,
            fallback_providers=fallbacks,
            routing_reason=reason,
            cost_tier=model_entry.tier,
            input_cost_per_1k=model_entry.input_cost_per_1k,
            output_cost_per_1k=model_entry.output_cost_per_1k,
        )

    def get_catalog(self) -> Dict[str, ModelCatalogEntry]:
        """Returns the active model catalog."""
        return self.models
