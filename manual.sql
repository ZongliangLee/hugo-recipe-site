select * from seasonal_ingredients where name like "%蕹菜-水蕹菜%";
select * from product_transactions where crop_name like "%苦瓜-其他%";

SELECT DISTINCT crop_name FROM product_transactions where crop_name like "%甘藍%";
SELECT DISTINCT name FROM seasonal_ingredients where name like "%甘藍%";

	
SELECT DISTINCT crop_name FROM product_transactions;

SELECT name FROM seasonal_ingredients where name like "%甘藍-初秋%";