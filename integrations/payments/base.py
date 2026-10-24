"""Provider-neutral contract for a future payment integration."""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal

@dataclass(frozen=True, slots=True)
class PaymentRequest:
    reference: str
    amount: Decimal
    description: str

@dataclass(frozen=True, slots=True)
class PaymentResult:
    provider_reference: str
    status: str

class PaymentGateway(ABC):
    @abstractmethod
    def create_payment(self, request: PaymentRequest) -> PaymentResult:
        """Create payment through a trusted backend integration."""
        raise NotImplementedError
