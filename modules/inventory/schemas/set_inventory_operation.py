from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional


@dataclass
class SetInventoryOperationData:
    correlative: Optional[int]
    operation_type: str
    document_no: str
    emission_date: date
    wait: bool
    description: str
    user_code: str
    station: str
    store: str
    locations: str
    destination_store: Optional[str]
    destination_location: str
    operation_comments: str
    total_amount: float
    total_net: float
    total_tax: float
    total: float
    coin_code: str
    internal_use: bool
