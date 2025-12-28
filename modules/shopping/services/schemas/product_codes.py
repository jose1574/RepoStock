from dataclasses import dataclass
from typing import Optional

@dataclass
class ProductCodes:
    main_code: str
    other_code: str
    code_type: str