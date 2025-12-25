from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional

@dataclass
class SetShoppingOperationData:
    correlative: int
    operation_type: str
    document_no: str
    control_no: str
    emission_date: date
    reception_date: date
    provider_code: str
    provider_name: str
    provider_id: str
    provider_address: str
    provider_phone: str
    credit_days: int
    expiration_date: date
    wait: bool
    description: str
    store: Optional[str]
    locations: Optional[str]
    user_code: Optional[str]
    station: Optional[str]
    percent_discount: float
    discount: float
    percent_freight: float
    freight: float
    freight_tax: str
    freight_aliquot: float
    credit: float
    cash: float
    operation_comments: str
    pending: bool
    buyer: str
    total_amount: float
    total_net_details: float
    total_tax_details: float
    total_details: float
    total_net: float
    total_tax: float
    total: float
    total_retention_tax: float
    total_retention_municipal: float
    total_retention_islr: float
    total_operation: float
    retention_tax_prorration: float
    retention_islr_prorration: float
    retention_municipal_prorration: float
    coin_code: Optional[str]
    free_tax: bool
    total_exempt: float
    secondary_coin: str
    base_igtf: float
    percent_igtf: float
    igtf: float
