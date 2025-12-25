from dataclasses import dataclass
from typing import Optional

@dataclass
class SetShoppingOperationDetailData:
    main_correlative: int
    line: int
    code_product: str
    description_product: str
    referenc: str
    mark: str
    model: str
    amount: float
    store: str
    locations: str
    unit: int
    conversion_factor: float
    unit_type: int
    unitary_cost: float
    sale_tax: str
    sale_aliquot: float
    buy_tax: str
    buy_aliquot: float
    price: float
    type_price: int
    percent_discount: float
    discount: float
    product_type: str
    total_net_cost: float
    total_tax_cost: float
    total_cost: float
    total_net_gross: float
    total_tax_gross: float
    total_gross: float
    total_net: float
    total_tax: float
    total: float
    description: str
    technician: str
    coin_code: str
    total_weight: float