from dataclasses import dataclass
from typing import Optional

@dataclass
class ProductUnits:
    correlative: int
    unit: str
    producto_codigo: str
    main_unit: Optional[bool] = False
    conversion_factor: Optional[float] = 0.0
    unit_type: Optional[int] = 0
    show_in_screen: Optional[bool] = False
    is_for_buy: Optional[bool] = False
    is_for_sale: Optional[bool] = False
    unitary_cost: Optional[float] = 0.0
    calculated_cost: Optional[float] = 0.0
    average_cost: Optional[float] = 0.0
    perc_waste_cost: Optional[float] = 0.0
    perc_handling_cost: Optional[float] = 0.0
    perc_operating_cost: Optional[float] = 0.0
    perc_additional_cost: Optional[float] = 0.0
    maximum_price: Optional[float] = 0.0
    offer_price: Optional[float] = 0.0
    higher_price: Optional[float] = 0.0
    minimum_price: Optional[float] = 0.0
    perc_maximum_price: Optional[float] = 0.0
    perc_offer_price: Optional[float] = 0.0
    perc_higher_price: Optional[float] = 0.0
    perc_minimum_price: Optional[float] = 0.0
    perc_freight_cost: Optional[float] = 0.0
    perc_discount_provider: Optional[float] = 0.0
    lenght: Optional[float] = 0.0
    height: Optional[float] = 0.0
    width: Optional[float] = 0.0
    weight: Optional[float] = 0.0
    capacitance: Optional[float] = 0.0