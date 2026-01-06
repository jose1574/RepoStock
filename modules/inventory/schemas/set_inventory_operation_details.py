from dataclasses import dataclass
from typing import Optional


@dataclass
class SetInventoryOperationDetailsData:
    main_correlative: int
    line: Optional[int]
    code_product: str
    description_product: str
    referenc: str
    mark: str
    model: str
    amount: float
    store: str
    locations: str
    destination_store: str
    destination_location: str
    unit: int
    conversion_factor: float
    unit_type: int
    unitary_cost: float
    buy_tax: str
    aliquot: float
    total_cost: float
    total_tax: float
    total: float
    coin_code: str
    change_price: bool
