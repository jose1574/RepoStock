--creation de la tabla products_failures

CREATE TABLE products_failures
(
  correlative serial NOT NULL,
  product_code character varying(50) NOT NULL,
  store_code character varying(50) NOT NULL,
  minimal_stock integer NOT NULL,
  maximum_stock integer NOT NULL,
  location character varying(100),
  CONSTRAINT products_failures_pkey PRIMARY KEY (correlative ),
  CONSTRAINT fk_product FOREIGN KEY (product_code)
      REFERENCES products (code) MATCH SIMPLE
      ON UPDATE NO ACTION ON DELETE NO ACTION,
  CONSTRAINT fk_store FOREIGN KEY (store_code)
      REFERENCES store (code) MATCH SIMPLE
      ON UPDATE NO ACTION ON DELETE NO ACTION,
  CONSTRAINT unique_product_store UNIQUE (product_code , store_code )
)
WITH (
  OIDS=FALSE
);
ALTER TABLE products_failures
  OWNER TO postgres;




--- Población inicial de la tabla products_failures
-- Este script inserta combinaciones de productos y tiendas en la tabla products_failures
-- con valores iniciales para minimal_stock y maximum_stock.
INSERT INTO products_failures (product_code, store_code, minimal_stock, maximum_stock)
SELECT
    p.code AS product_code,
    s.code AS store_code,
    p.minimal_stock AS minimal_stock,      -- Valor inicial por defecto
    p.maximum_stock AS maximum_stock       -- Valor inicial por defecto
FROM
    products p
CROSS JOIN
    store s  -- Asumiendo que 'store' es la tabla de tiendas
LEFT JOIN
    products_failures pf ON p.code = pf.product_code AND s.code = pf.store_code
WHERE
    pf.product_code IS NULL; -- Inserta solo donde la combinación no exista



-- Segunda inserción con valores fijos en caso de que los productos no tengan definidos mínimos y máximos
INSERT INTO products_failures (product_code, store_code, minimal_stock, maximum_stock)
SELECT
    p.code AS product_code,
    s.code AS store_code,
    5 AS minimal_stock,      -- Valor inicial por defecto
    20 AS maximum_stock       -- Valor inicial por defecto
FROM
    products p
CROSS JOIN
    store s  -- Asumiendo que 'store' es la tabla de tiendas
LEFT JOIN
    products_failures pf ON p.code = pf.product_code AND s.code = pf.store_code
WHERE
    pf.product_code IS NULL; -- Inserta solo donde la combinación no exista

-- consutla para rellenar los campos de location con el valor de modelo de productos
UPDATE products_failures AS pf
SET location = p.model
FROM products AS p
WHERE pf.product_code = p.code
  AND pf.store_code = '01';