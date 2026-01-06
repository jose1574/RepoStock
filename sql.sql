SELECT 
    p.code,
    p.description,
    u.code as unit_code,
    u.description unit_description,
    m.code as mark_code,
    m.description as mark_description,
    d.code as department_code,
    d.description as department_description,
    SUM(ps_org.stock) as stock_store_origin,
    SUM(ps_dst.stock) as stock_store_destination
    
    
    
FROM products AS p
LEFT JOIN department as d on p.department = d.code  
LEFT JOIN products_failures AS pf ON pf.product_code = p.code AND pf.store_code = '00'
LEFT JOIN products_units pu ON p.code = pu.product_code AND pu.main_unit = true
LEFT JOIN units u ON pu.unit = u.code 
LEFT JOIN products_stock ps_org ON ps_org.product_code = p.code AND ps_org.store IN ('01')
LEFT JOIN products_stock ps_dst ON ps_dst.product_code = p.code AND ps_dst.store IN ('00')

LEFT JOIN marks m ON m.code = p.mark 
WHERE p.status = '01'
GROUP BY 
    p.code, 
    p.description,
    u.code,
    u.description,
    m.code,
    m.description,
    d.code,
    d.description

      
ORDER BY p.code;