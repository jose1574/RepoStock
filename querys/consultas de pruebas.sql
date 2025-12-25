-- SELECT 
--     p.code,
--     p.description,
--     pu.unit AS unit_code,
--     u.description AS unit_description,
--     ps.stock,
--     ps.store AS store_code,
--     s.description AS store_description,
--     pf.minimal_stock,
--     pf.maximum_stock
--     FROM products AS p 
--     LEFT JOIN products_stock AS ps ON p.code = ps.product_code
--     JOIN store AS s ON s.code = ps.store
--     LEFT JOIN products_units pu ON (pu.product_code = p.code) 
--     LEFT JOIN units AS u ON u.code = pu.unit 
--     LEFT JOIN products_failures pf ON (pf.product_code = p.code AND ps.store = pf.store_code)
--     LEFT JOIN products_codes pc ON (pc.main_code = p.code)
--     WHERE pc.other_code = '19-074'
--     GROUP BY 
--     p.code, p.description, pu.unit, u.description, 
--     ps.stock, ps.store, s.description, 
--     pf.minimal_stock, pf.maximum_stock, pf.location;


-- select 
-- p.*
-- from products as p 
-- left join products_codes pc on (pc.main_code = p.code )
-- where pc.other_code = '0419074'
-- 

-- 	 SELECT 
-- 	    ps.*,
-- 	    s.description as store_description
-- 	    FROM products_stock AS ps    
-- 	    LEFT JOIN products_codes pc ON (pc.main_code = ps.product_code)
-- 	    LEFT JOIN store s ON (s.code = ps.store)
-- 	    WHERE pc.other_code = '0419074'



--  SELECT 
--                 ps.product_code,
--                 ps.store,
--                 ps.stock,
--                 s.description as store_description,
--                 pf.*
--             FROM products_stock AS ps    
--             LEFT JOIN products_codes pc ON (pc.main_code = ps.product_code)
--             LEFT JOIN store s ON (s.code = ps.store)
--             LEFT JOIN products_failures pf ON (pf.product_code = ps.product_code and pf.store_Code = ps.store)
--             WHERE pc.other_code = '0419074'

SELECT 
pu.product_code,
pu.conversion_factor,
pu.main_unit,
u.code as unit_code,
u.description as unit_description
FROM products_units AS pu 
LEFT JOIN units AS u ON  (pu.unit = u.code )
where pu.product_code = '19-074'
