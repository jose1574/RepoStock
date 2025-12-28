
from dataclasses import dataclass
from typing import Optional

@dataclass
class Product:
    """
    Clase que representa los parámetros para la función set_product en la base de datos.
    """
    code: str
    description: Optional[str] = None
    short_name: Optional[str] = None
    mark: Optional[str] = None
    model: Optional[str] = None
    referenc: Optional[str] = None
    department: Optional[str] = "00"
    days_warranty: Optional[int] = 0
    sale_tax: Optional[str] = "01"
    buy_tax: Optional[str] = "01"
    rounding_type: Optional[int] = 0
    costing_type: Optional[int] = 0
    discount: Optional[float] = 0.0
    max_discount: Optional[float] = 0.0
    minimal_sale: Optional[float] = 0.0
    maximal_sale: Optional[float] = 0.0
    status: Optional[str] = "01"
    origin: Optional[str] = "01"
    take_department_utility: Optional[bool] = True
    allow_decimal: Optional[bool] = True
    edit_name: Optional[bool] = False
    sale_price: Optional[int] = 0
    product_type: Optional[str] = "T"
    technician: Optional[str] = "00"
    request_technician: Optional[bool] = False
    serialized: Optional[bool] = False
    request_details: Optional[bool] = False
    request_amount: Optional[bool] = False
    coin: Optional[str] = "02"
    allow_negative_stock: Optional[bool] = False
    use_scale: Optional[bool] = False
    add_unit_description: Optional[bool] = False
    use_lots: Optional[bool] = False
    lots_order: Optional[int] = 0
    minimal_stock: Optional[float] = 0.0
    notify_minimal_stock: Optional[bool] = False
    size: Optional[str] = None
    color: Optional[str] = None
    extract_net_from_unit_cost_plus_tax: Optional[bool] = True
    extract_net_from_unit_price_plus_tax: Optional[bool] = True
    maximum_stock: Optional[float] = 0.0
    action: Optional[str] = "I"




    