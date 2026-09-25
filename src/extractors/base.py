"""Shared contracts for source-specific tierlist extractors."""

import dataclasses
import pathlib


@dataclasses.dataclass(frozen=True)
class ExtractionContext:
    avatar_dir: pathlib.Path
    brawler_spec_path: pathlib.Path
    tier_label_adapter: object
    logger: object


@dataclasses.dataclass(frozen=True)
class ExtractedTierlist:
    tiers: dict


class TierlistExtractor:
    """Base strategy whose subclasses own one image layout."""

    def __init__(self, context):
        self.context = context

    def extract(self, image_path):
        raise NotImplementedError