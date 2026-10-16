"""Auto-discovery service for local engines (Ollama, LM Studio)."""

import httpx

from app.core.config import Settings
from app.core.logging import logger
from app.routing.policies import ModelCatalogEntry
from app.routing.router import ModelRouter


async def discover_local_models(router: ModelRouter, settings: Settings) -> int:
    """Discovers installed models from local engines (Ollama/LM Studio) and registers them into the router catalog."""
    if not settings.local_enabled or not settings.ollama_auto_discover:
        return 0

    base_url = settings.local_base_url.rstrip("/")
    detected_models = []

    async with httpx.AsyncClient(timeout=1.0) as client:
        # 1. Try native Ollama /api/tags
        if "11434" in base_url:
            ollama_tags_url = base_url.replace("/v1", "") + "/api/tags"
            try:
                res = await client.get(ollama_tags_url)
                if res.status_code == 200:
                    models_info = res.json().get("models", [])
                    for item in models_info:
                        name = item.get("name")
                        if name:
                            detected_models.append(name)
                            # Also register base tag e.g. "llama3.2" from "llama3.2:latest"
                            if ":" in name:
                                detected_models.append(name.split(":")[0])
            except Exception as e:
                logger.debug(f"Ollama tags discovery probe failed ({ollama_tags_url}): {e}")

        # 2. Try standard OpenAI /models endpoint
        if not detected_models:
            openai_models_url = f"{base_url}/models"
            try:
                res = await client.get(openai_models_url)
                if res.status_code == 200:
                    data = res.json().get("data", [])
                    for item in data:
                        m_id = item.get("id")
                        if m_id:
                            detected_models.append(m_id)
            except Exception as e:
                logger.debug(f"OpenAI local models discovery probe failed ({openai_models_url}): {e}")

    # Deduplicate while preserving order
    unique_models = []
    seen = set()
    for m in detected_models:
        if m not in seen:
            seen.add(m)
            unique_models.append(m)

    count = 0
    for model_name in unique_models:
        if model_name not in router.models:
            router.register_model(
                ModelCatalogEntry(
                    name=model_name,
                    description=f"Auto-discovered local model from {base_url}",
                    tier="cheap",
                    max_tokens=8192,
                    capabilities=["chat", "code", "local", "offline"],
                    input_cost_per_1k=0.0,
                    output_cost_per_1k=0.0,
                    primary_provider="local",
                    fallback_providers=["mock-primary", "mock-secondary"],
                )
            )
            count += 1

    if unique_models:
        logger.info(
            f"Ollama auto-discovery detected {len(unique_models)} local model(s): {unique_models}. "
            f"Added {count} new entries to model catalog."
        )
    else:
        logger.info("Ollama auto-discovery: no active local engine detected at startup.")

    return count
