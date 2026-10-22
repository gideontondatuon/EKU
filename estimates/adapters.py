"""Contract only: no source template or approved forecasting method has been supplied."""

from dataclasses import dataclass
from typing import Protocol

from django.core.exceptions import ValidationError


@dataclass(frozen=True)
class EstimateImportContract:
    schema_version: str
    approval_reference: str
    field_mapping: dict
    scope: str

    def validate(self):
        if (
            not self.schema_version
            or not self.approval_reference
            or not self.field_mapping
            or self.scope not in ("REGION", "BANK", "BOTH")
        ):
            raise ValidationError(
                "Kontrak estimasi memerlukan versi, mapping, scope, dan persetujuan resmi."
            )


class EstimateAdapter(Protocol):
    def parse(self, content: bytes, contract: EstimateImportContract) -> list[dict]: ...


class EstimateAdapterRegistry:
    def __init__(self):
        self._adapters = {}

    def register(self, schema_version: str, adapter: EstimateAdapter):
        if not schema_version or schema_version in self._adapters:
            raise ValidationError("Versi adapter harus unik dan terisi.")
        self._adapters[schema_version] = adapter

    def parse(self, content: bytes, contract: EstimateImportContract):
        contract.validate()
        adapter = self._adapters.get(contract.schema_version)
        if not adapter:
            raise ValidationError("UNCONFIGURED: template estimasi asli belum tersedia.")
        return adapter.parse(content, contract)


registry = EstimateAdapterRegistry()


def automatic_estimate(*args, **kwargs):
    raise ValidationError("Belum dikonfigurasi: metode estimasi otomatis belum disahkan.")
