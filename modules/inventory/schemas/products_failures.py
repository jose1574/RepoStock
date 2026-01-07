from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional


@dataclass
class ProductsFailuresData:
    correlative: Optional[int]
    product_code: str
    store_code: str
    minimal_stock: int
    maximum_stock: int
    location: Optional[str] = None