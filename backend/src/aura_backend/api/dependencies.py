from functools import lru_cache

from aura_backend.ai.openai_compatible import (
    OpenAICompatibleEmbeddingProvider,
    OpenAICompatibleVisionAnalyzer,
)
from aura_backend.application.item_analysis import ItemAnalysisService
from aura_backend.application.candidate_items import CandidateItemService
from aura_backend.application.feedback import FeedbackService
from aura_backend.application.matching import CandidateMatcher
from aura_backend.application.owned_items import OwnedItemService
from aura_backend.application.profiles import AestheticProfileBuilder, ProfileService
from aura_backend.core.config import get_settings
from aura_backend.core.supabase import get_supabase_client
from aura_backend.media.images import ImageValidator
from aura_backend.media.storage import SupabaseImageStorage
from aura_backend.repositories.supabase import AuraRepository, FeaturePipelineVersion


def _pipeline(settings) -> FeaturePipelineVersion:
    return FeaturePipelineVersion(
        vision_provider="ai_lodge",
        vision_model=settings.vision_model,
        vision_prompt_version=1,
        feature_schema_version=1,
        embedding_provider="ai_lodge",
        embedding_model=settings.embedding_model,
        embedding_dimensions=settings.embedding_dimensions,
        embedding_schema_version=1,
    )


@lru_cache
def get_owned_item_service() -> OwnedItemService:
    """Build the application service used by frontend adapters."""
    settings = get_settings()
    client = get_supabase_client()
    repository = AuraRepository(client)
    item_analysis = ItemAnalysisService(
        repository=repository,
        vision_analyzer=OpenAICompatibleVisionAnalyzer.from_settings(settings),
        embedding_provider=OpenAICompatibleEmbeddingProvider.from_settings(settings),
    )
    pipeline = _pipeline(settings)
    profile_service = ProfileService(
        repository=repository,
        builder=AestheticProfileBuilder(),
        pipeline=pipeline,
    )
    return OwnedItemService(
        repository=repository,
        storage=SupabaseImageStorage(client),
        image_validator=ImageValidator(
            max_bytes=settings.max_image_bytes,
            min_dimension=settings.min_image_dimension,
        ),
        item_analysis=item_analysis,
        profile_service=profile_service,
        pipeline=pipeline,
    )


@lru_cache
def get_candidate_item_service() -> CandidateItemService:
    """Build the candidate evaluation service used by frontend adapters."""
    settings = get_settings()
    client = get_supabase_client()
    repository = AuraRepository(client)
    pipeline = _pipeline(settings)
    return CandidateItemService(
        repository=repository,
        storage=SupabaseImageStorage(client),
        image_validator=ImageValidator(
            max_bytes=settings.max_image_bytes,
            min_dimension=settings.min_image_dimension,
        ),
        item_analysis=ItemAnalysisService(
            repository=repository,
            vision_analyzer=OpenAICompatibleVisionAnalyzer.from_settings(settings),
            embedding_provider=OpenAICompatibleEmbeddingProvider.from_settings(settings),
        ),
        matcher=CandidateMatcher(),
        pipeline=pipeline,
    )


@lru_cache
def get_feedback_service() -> FeedbackService:
    """Build the feedback service used by frontend adapters."""
    return FeedbackService(AuraRepository(get_supabase_client()))
