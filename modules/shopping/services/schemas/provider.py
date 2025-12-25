from dataclasses import dataclass
from typing import Optional

@dataclass
class Provider:
    """
    Representa un proveedor en el sistema.
    Valida la estructura de la tabla 'provider'.
    """
    code: str
    description: Optional[str] = None
    address: Optional[str] = None
    provider_id: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    contact: Optional[str] = None
    country: Optional[str] = None
    province: Optional[str] = None
    city: Optional[str] = None
    town: Optional[str] = None
    credit_days: Optional[int] = 0
    credit_limit: Optional[float] = 0.0
    provider_type: Optional[str] = None
    status: Optional[str] = None
    domiciled: Optional[int] = 0
    percent_tax_retention: Optional[float] = 0.0
    percent_municipal_retention: Optional[float] = 0.0
    retention_tax_agent: Optional[bool] = False
    retention_municipal_agent: Optional[bool] = False
    retention_islr_agent: Optional[bool] = False
    perception_igtf_agent: Optional[bool] = False

    @property
    def provider_code(self) -> str:
        """Alias para compatibilidad con frontend."""
        return self.code

    @property
    def provider_name(self) -> Optional[str]:
        """Alias para compatibilidad con frontend."""
        return self.description

    @property
    def provider_phone(self) -> Optional[str]:
        """Alias para compatibilidad con frontend."""
        return self.phone

    def to_dict(self) -> dict:
        """Convierte el objeto a diccionario incluyendo alias."""
        return {
            "code": self.code,
            "description": self.description,
            "address": self.address,
            "provider_id": self.provider_id,
            "email": self.email,
            "phone": self.phone,
            "contact": self.contact,
            "country": self.country,
            "province": self.province,
            "city": self.city,
            "town": self.town,
            "credit_days": self.credit_days,
            "credit_limit": self.credit_limit,
            "provider_type": self.provider_type,
            "status": self.status,
            "domiciled": self.domiciled,
            "percent_tax_retention": self.percent_tax_retention,
            "percent_municipal_retention": self.percent_municipal_retention,
            "retention_tax_agent": self.retention_tax_agent,
            "retention_municipal_agent": self.retention_municipal_agent,
            "retention_islr_agent": self.retention_islr_agent,
            "perception_igtf_agent": self.perception_igtf_agent,
            # Alias keys
            "provider_code": self.provider_code,
            "provider_name": self.provider_name,
            "provider_phone": self.provider_phone
        }
