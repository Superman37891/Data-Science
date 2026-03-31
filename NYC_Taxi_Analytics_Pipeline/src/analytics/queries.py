import src.config as config

# Base table
YELLOW_TAXI_PROCESSED_QUERY = f"""
CREATE EXTERNAL TABLE `yellow_taxi_processed`(
  `vendorid` int, 
  `tpep_pickup_datetime` timestamp, 
  `tpep_dropoff_datetime` timestamp, 
  `passenger_count` double, 
  `trip_distance` double, 
  `fare_amount` double, 
  `trip_duration_min` double, 
  `speed_mph` double,
   `payment_type` int
)
PARTITIONED BY ( 
  `year` int, 
  `month` string)
ROW FORMAT SERDE 
  'org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe' 
STORED AS INPUTFORMAT 
  'org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat' 
OUTPUTFORMAT 
  'org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat'
LOCATION
  's3://{config.BUCKET_NAME}/processed_data/yellow_taxi'
TBLPROPERTIES (
  'projection.enabled'='true', 
  'projection.month.type'='enum', 
  'projection.month.values'='01,02,03,04,05,06,07,08,09,10,11,12', 
  'projection.year.range'='2020,2040', 
  'projection.year.type'='integer', 
  'storage.location.template'='s3://{config.BUCKET_NAME}/processed_data/yellow_taxi/year=${{year}}/month=${{month}}/'
)

"""

# Create a view adding a month_date column
# to help with dates visualization software
YELLOW_TAXI_ENRICHED_QUERY = f"""
CREATE OR REPLACE VIEW yellow_taxi_enriched AS
SELECT
    *,
    DATE_PARSE(
        CONCAT(CAST(year AS VARCHAR), 
            '-', 
            LPAD(CAST(month AS VARCHAR), 2, '0'), 
            '-01'
        ),
        '%Y-%m-%d'
    ) AS month_date
FROM {config.TABLE_NAME};
"""

# Create a KPI for monthly revenue to help
# plot on BI software and to help
# other queries get monthly revenue quickly
KPI_MONTHLY_REVENUE_QUERY = f"""
CREATE OR REPLACE VIEW taxi_data.kpi_monthly_revenue AS
SELECT
  year, 
  month,
  month_date,
  CAST(SUM(fare_amount) AS DECIMAL(18, 2)) AS total_revenue
FROM
  {config.ENRICHED_TABLE_NAME}
GROUP BY year, month, month_date
"""

# Create a KPI for num. trips per month to help
# plot on BI software and to help
# other queries get monthly trips quickly
KPI_MONTHLY_TRIPS_QUERY = f"""
CREATE OR REPLACE VIEW taxi_data.kpi_monthly_trips AS
SELECT
  year,
  month,
  month_date,
  COUNT(*) total_trips
FROM
  {config.ENRICHED_TABLE_NAME}
GROUP BY year, month, month_date
"""

# Create a KPI for cumulative revenue to help
# plot on BI software and to help
# other queries get cumulative revenue quickly
KPI_CUMULATIVE_REVENUE_QUERY = """
CREATE OR REPLACE VIEW taxi_data.kpi_cumulative_revenue AS
SELECT
  month_date,
  SUM(total_revenue) OVER (ORDER BY month_date ASC ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) cumulative_revenue
FROM
  kpi_monthly_revenue

"""

# Create a KPI for monthly avg fare to help
# plot on BI software and to help
# other queries get monthly avg fare quickly
KPI_MONTHLY_AVG_FARE_QUERY = f"""
CREATE OR REPLACE VIEW taxi_data.kpi_monthly_avg_fare AS
SELECT
  year,
  month,
  month_date,
  ROUND((SUM(fare_amount) / COUNT(*)), 2) avg_fare
FROM
  {config.ENRICHED_TABLE_NAME}
GROUP BY year, month, month_date
"""

# Create a KPI for monthly avg speed to help
# plot on BI software and to help
# other queries get monthly avg speed quickly
KPI_MONTHLY_AVG_SPEED_QUERY = f"""
CREATE OR REPLACE VIEW taxi_data.kpi_monthly_avg_speed AS
SELECT
  year, 
  month, 
  month_date, 
  ROUND(AVG(speed_mph), 3) avg_speed
FROM
  {config.ENRICHED_TABLE_NAME}
GROUP BY year, month, month_date
"""

# Create a KPI for monthly summary
# to help plot on BI software
# and to help with other queries
# that want multiple monthly statistics
KPI_MONTHLY_SUMMARY_QUERY = f"""
CREATE OR REPLACE VIEW taxi_data.kpi_monthly_summary AS
SELECT
  year, 
  month, 
  month_date, 
  COUNT(*) total_trips, 
  SUM(fare_amount) total_revenue, 
  AVG(trip_distance) avg_distance, 
  AVG(speed_mph) avg_speed
FROM
  {config.ENRICHED_TABLE_NAME}
GROUP BY year, month, month_date
"""

# Get the top 5 months by revenue
TOP_5_REVENUE_MONTHS_QUERY = """
SELECT year, month, total_revenue
FROM kpi_monthly_revenue
ORDER BY total_revenue DESC
LIMIT 5
"""

# Get the growth percentage in revenue
# from the previous to current month
REVENUE_GROWTH_MONTHLY_QUERY = """
WITH growth_calc AS (
    SELECT 
        month_date,
        total_revenue,
        LAG(total_revenue) OVER (ORDER BY month_date) AS prev_month_revenue,
        total_trips,
        LAG(total_trips) OVER (ORDER BY month_date) AS prev_month_trips
    FROM kpi_monthly_summary
)
SELECT 
    month_date,
    total_revenue,
    total_trips,
    ROUND(((total_revenue - prev_month_revenue) / prev_month_revenue) * 100, 2) AS revenue_growth_pct,
    ROUND(((total_trips - prev_month_trips) / prev_month_trips) * 100, 2) AS trip_growth_pct
FROM growth_calc
ORDER BY month_date;
"""

# Get the avg speed per hour of the day
# to help identify when traffic gridlock happens
AVG_SPEED_HOURLY_QUERY = f"""
SELECT 
    EXTRACT(HOUR FROM tpep_pickup_datetime) AS hour_of_day,
    COUNT(*) AS total_trips,
    -- Distance is in miles, duration is in minutes. 
    -- Convert minutes to hours (min / 60) to get MPH.
    ROUND(AVG(trip_distance / (NULLIF(trip_duration_min, 0) / 60.0)), 2) AS avg_speed_mph
FROM {config.TABLE_NAME}
GROUP BY 1
ORDER BY hour_of_day;
"""

# Get the stats of trips by different payment methods
PAYMENT_METHOD_STATS_QUERY = f"""
SELECT 
    CASE 
    	WHEN payment_type = 0 THEN 'Flex Fare Trip'
        WHEN payment_type = 1 THEN 'Credit Card'
        WHEN payment_type = 2 THEN 'Cash'
    	WHEN payment_type = 3 THEN 'No Charge'
    	WHEN payment_type = 4 THEN 'Dispute'
    	WHEN payment_type = 5 THEN 'Unknown'
    	WHEN payment_type = 6 THEN 'Voided trip'
        ELSE 'Other'
    END AS payment_method,
    COUNT(*) AS total_trips,
    ROUND(AVG(trip_distance), 2) AS avg_distance,
    ROUND(AVG(fare_amount), 2) AS avg_fare,
    ROUND(STDDEV(fare_amount), 2) AS fare_standard_deviation
FROM {config.TABLE_NAME}
GROUP BY payment_type
ORDER BY payment_type
"""

# Get specific stats of fare amounts
# by payment types
FARE_STATS_BY_PAYMENT_TYPE_QUERY = f"""
SELECT 
    CASE 
    	WHEN payment_type = 0 THEN 'Flex Fare Trip'
        WHEN payment_type = 1 THEN 'Credit Card'
        WHEN payment_type = 2 THEN 'Cash'
    	WHEN payment_type = 3 THEN 'No Charge'
    	WHEN payment_type = 4 THEN 'Dispute'
    	WHEN payment_type = 5 THEN 'Unknown'
    	WHEN payment_type = 6 THEN 'Voided trip'
        ELSE 'Other'
    END AS payment_method,
    MIN(fare_amount) AS min_fare,
    MAX(fare_amount) AS max_fare,
    AVG(fare_amount) AS avg_fare,
    STDDEV(fare_amount) AS stdev_fare,
    COUNT(*) AS trip_count
FROM {config.TABLE_NAME}
GROUP BY 1
ORDER BY 1
"""

MONTHLY_TRIPS_QUERY = """
SELECT month_date, total_trips
FROM kpi_monthly_trips
ORDER BY month_date
"""

MONTHLY_AVG_SPEED_QUERY = """
SELECT month_date, avg_speed
FROM kpi_monthly_avg_speed
ORDER BY month_date
"""

MONTHLY_AVG_FARE_QUERY = """
SELECT month_date, avg_fare
FROM kpi_monthly_avg_fare
ORDER BY month_date
"""

MONTHLY_REVENUE_QUERY = """
SELECT month_date, revenue
FROM kpi_monthly_revenue
ORDER BY month_date
"""

CUMULATIVE_REVENUE_QUERY = """
SELECT month_date, cumulative_revenue
FROM kpi_cumulative_revenue
ORDER BY month_date
"""


