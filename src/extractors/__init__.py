"""Source-specific tierlist extraction strategies."""

from .base import ExtractionContext, ExtractedTierlist
from .deepdraft import DeepDraftExtractor
from .tiermaker import TierMakerExtractor


_EXTRACTORS = {
    'deepdraft': DeepDraftExtractor,
    'tiermaker': TierMakerExtractor,
}


def create_extractor(source, context):
    """Create the strategy for a supported image source."""
    try:
        extractor_type = _EXTRACTORS[source]
    except KeyError as exc:
        raise ValueError(f'Unsupported tierlist source: {source!r}') from exc
    return extractor_type(context)


__all__ = [
    'ExtractionContext',
    'ExtractedTierlist',
    'DeepDraftExtractor',
    'TierMakerExtractor',
    'create_extractor',
]