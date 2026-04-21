from __future__ import annotations

from abc import ABC, abstractmethod

from requests import Session

from sf_apartment_aggregator.config import SourceConfig
from sf_apartment_aggregator.models import NormalizedListing


class AdapterError(RuntimeError):
    pass


class SourceAdapter(ABC):
    def __init__(self, source: SourceConfig, session: Session):
        self.source = source
        self.session = session

    @abstractmethod
    def fetch(self) -> list[NormalizedListing]:
        raise NotImplementedError
