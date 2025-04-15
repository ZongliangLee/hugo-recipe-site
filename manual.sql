select * from seasonal_ingredients where  name like "%甘藍%";
select * from product_transactions;

SELECT DISTINCT crop_name FROM product_transactions where crop_name like "%甘藍%";
SELECT DISTINCT name FROM seasonal_ingredients where name like "%甘藍%";



WITH duplicates AS (
  SELECT id
  FROM (
    SELECT id,
           ROW_NUMBER() OVER (PARTITION BY trans_date, crop_name, trans_quantity ORDER BY id) AS rn
    FROM product_transactions
  )
  WHERE rn > 1
)
DELETE FROM product_transactions
WHERE id IN (SELECT id FROM duplicates);
