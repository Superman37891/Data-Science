import src.config as config

# Available years query
AVAILABLE_YEARS_QUERY = f"""
SELECT DISTINCT year
FROM {config.TABLE_NAME}
ORDER BY year DESC
"""

# Base table
YELLOW_TAXI_PROCESSED_QUERY = f"""
CREATE EXTERNAL TABLE {config.TABLE_NAME} (
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
  's3://{config.BUCKET_NAME}/{config.PROCESSED_FOLDER}'
TBLPROPERTIES (
  'projection.enabled'='true', 
  'projection.month.type'='enum', 
  'projection.month.values'='01,02,03,04,05,06,07,08,09,10,11,12', 
  'projection.year.range'='2020,2040', 
  'projection.year.type'='integer', 
  'storage.location.template'='s3://{config.BUCKET_NAME}/{config.PROCESSED_FOLDER}/year=${{year}}/month=${{month}}/'
)

"""

# Create a view adding a month_date column
# to help with dates visualization software
YELLOW_TAXI_ENRICHED_CREATE_QUERY = f"""
CREATE OR REPLACE VIEW taxi_data.{config.ENRICHED_TABLE_NAME} AS
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


CREATE_KPI_MONTHLY_SUMMARY_QUERY = f"""
CREATE OR REPLACE VIEW taxi_data.kpi_monthly_summary AS
SELECT
  year, 
  month, 
  month_date,
  COUNT(*) total_trips,
  ROUND(SUM(fare_amount), 4) total_revenue,
  ROUND(AVG(fare_amount), 4) avg_fare,
  ROUND(AVG(trip_distance), 4) avg_distance,
  ROUND(AVG(speed_mph), 4) avg_speed_mph,
  ROUND(SUM(SUM(fare_amount)) OVER (ORDER BY month_date ASC), 4) cumulative_revenue
FROM
  {config.ENRICHED_TABLE_NAME}
GROUP BY year, month, month_date
"""
# Create a KPI for monthly summary
# to help plot on BI software
# and to help with other queries
# that want multiple monthly statistics

KPI_OVERALL_MONTHLY_SUMMARY_QUERY = f"""
    SELECT *
    FROM taxi_data.kpi_monthly_summary
    ORDER BY month_date
"""

def kpi_monthly_summary_query(year_selected):
    return f"""
    SELECT *
    FROM taxi_data.kpi_monthly_summary
    WHERE year={year_selected}
    ORDER BY month_date
"""

# Get the top 5 months by revenue
TOP_5_OVERALL_REVENUE_MONTHS_QUERY = """
SELECT year, month, total_revenue
FROM kpi_monthly_summary
ORDER BY total_revenue DESC
LIMIT 5
"""

# Get the growth percentage in revenue
# from the previous to current month
KPI_OVERALL_REVENUE_GROWTH_MONTHLY_QUERY = """
WITH growth_calc AS (
    SELECT
        year,
        month,
        month_date,
        total_trips,
        total_revenue,
        LAG(total_revenue) OVER (
            ORDER BY month_date
        ) AS prev_month_revenue,
        LAG(total_trips) OVER (
            ORDER BY month_date
        )
        AS prev_month_trips
    FROM kpi_monthly_summary
)
SELECT
    year,
    month,
    total_revenue,
    total_trips,
    CASE
    WHEN prev_month_revenue IS NULL THEN NULL
    ELSE ROUND(
    100*(total_revenue - prev_month_revenue) / NULLIF(CAST(prev_month_revenue AS DOUBLE), 0),
        4
    ) END AS revenue_growth_pct,
    CASE 
    WHEN prev_month_trips IS NULL THEN NULL
    ELSE ROUND(
        100.0 * (total_trips - prev_month_trips)
        / NULLIF(prev_month_trips, 0),
        4
    )
    END AS trip_growth_pct
FROM growth_calc
ORDER BY month_date
"""

def year_revenue_growth_monthly_query(year_selected):
    return f"""
    WITH growth_calc AS (
    SELECT
        year,
        month,
        month_date,
        total_trips,
        total_revenue,
        LAG(total_revenue) OVER (
            ORDER BY month_date
        ) AS prev_month_revenue,
        LAG(total_trips) OVER (
            ORDER BY month_date
        )
        AS prev_month_trips
    FROM kpi_monthly_summary
)
SELECT
    year,
    month,
    total_revenue,
    total_trips,
    CASE
    WHEN prev_month_revenue IS NULL THEN NULL
    ELSE ROUND(
    100*(total_revenue - prev_month_revenue) / NULLIF(CAST(prev_month_revenue AS DOUBLE), 0),
        4
    ) END AS revenue_growth_pct,
    CASE 
    WHEN prev_month_trips IS NULL THEN NULL
    ELSE ROUND(
        100.0 * (total_trips - prev_month_trips)
        / NULLIF(prev_month_trips, 0),
        4
    )
    END AS trip_growth_pct
FROM growth_calc
WHERE year={year_selected}
ORDER BY month_date
"""

# Get the avg speed per hour of the day
# to help identify when traffic gridlock happens
OVERALL_HOURLY_TRIPS_QUERY = f"""
SELECT 
    EXTRACT(HOUR FROM tpep_pickup_datetime) AS hour_of_day,
    COUNT(*) AS total_trips,
    ROUND(SUM(fare_amount), 4) AS total_revenue,
    ROUND(AVG(fare_amount), 4) AS avg_fare,
    ROUND(AVG(trip_distance), 4) AS avg_distance,
    ROUND(AVG(passenger_count), 4) AS avg_passenger_count,
    ROUND(AVG(trip_duration_min), 4) AS avg_trip_duration_min,
    ROUND(AVG(trip_distance / (NULLIF(trip_duration_min, 0) / 60.0)), 4) AS avg_speed_mph
    
FROM {config.TABLE_NAME}
GROUP BY 1
ORDER BY hour_of_day;
"""
def year_hourly_trips_query(year_selected):
    return f"""
    SELECT 
        EXTRACT(HOUR FROM tpep_pickup_datetime) AS hour_of_day,
        COUNT(*) AS total_trips,
        ROUND(SUM(fare_amount), 4) AS total_revenue,
        ROUND(AVG(fare_amount), 4) AS avg_fare,
        ROUND(AVG(trip_distance), 4) AS avg_distance,
        ROUND(AVG(passenger_count), 4) AS avg_passenger_count,
        ROUND(AVG(trip_duration_min), 4) AS avg_trip_duration_min,
        ROUND(AVG(trip_distance / (NULLIF(trip_duration_min, 0) / 60.0)), 4) AS avg_speed_mph
        
    FROM {config.TABLE_NAME}
    WHERE year={year_selected}
    GROUP BY 1
    ORDER BY hour_of_day;
"""

CREATE_KPI_OVERALL_PAYMENT_TYPE_SUMMARY_QUERY = f"""
CREATE OR REPLACE VIEW taxi_data.kpi_overall_payment_type_summary AS
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
    SUM(fare_amount) AS total_revenue,
    ROUND(AVG(fare_amount), 4) AS avg_fare,
    ROUND(STDDEV(fare_amount), 4) AS stddev_fare,
    ROUND(AVG(trip_distance), 4) AS avg_distance,
    ROUND(AVG(speed_mph), 4) AS avg_speed_mph

FROM {config.ENRICHED_TABLE_NAME}

GROUP BY 
    CASE 
        WHEN payment_type = 0 THEN 'Flex Fare Trip'
        WHEN payment_type = 1 THEN 'Credit Card'
        WHEN payment_type = 2 THEN 'Cash'
        WHEN payment_type = 3 THEN 'No Charge'
        WHEN payment_type = 4 THEN 'Dispute'
        WHEN payment_type = 5 THEN 'Unknown'
        WHEN payment_type = 6 THEN 'Voided trip'
        ELSE 'Other'
    END
"""

KPI_OVERALL_PAYMENT_TYPE_SUMMARY_QUERY = f"""
SELECT * 
FROM taxi_data.kpi_overall_payment_type_summary
"""

CREATE_KPI_YEARLY_PAYMENT_TYPE_SUMMARY_QUERY = """
CREATE OR REPLACE VIEW taxi_data.kpi_yearly_payment_type_summary AS
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
    year,
    COUNT(*) AS total_trips,
    SUM(fare_amount) AS total_revenue,
    ROUND(AVG(fare_amount), 4) AS avg_fare,
    ROUND(STDDEV(fare_amount), 4) AS stddev_fare,
    ROUND(AVG(trip_distance), 4) AS avg_distance,
    ROUND(AVG(speed_mph), 4) AS avg_speed_mph

FROM {config.ENRICHED_TABLE_NAME}

GROUP BY 
    CASE 
        WHEN payment_type = 0 THEN 'Flex Fare Trip'
        WHEN payment_type = 1 THEN 'Credit Card'
        WHEN payment_type = 2 THEN 'Cash'
        WHEN payment_type = 3 THEN 'No Charge'
        WHEN payment_type = 4 THEN 'Dispute'
        WHEN payment_type = 5 THEN 'Unknown'
        WHEN payment_type = 6 THEN 'Voided trip'
        ELSE 'Other'
    END, year
"""

# For Streamlit plotting purposes by year
def year_payment_type_summary_query(year_selected):
    return f"""
    SELECT *
    FROM taxi_data.kpi_yearly_payment_type_summary
    WHERE year={year_selected}
"""

CREATE_KPI_MONTHLY_PAYMENT_TYPE_SUMMARY_QUERY = f"""
CREATE OR REPLACE VIEW taxi_data.kpi_monthly_payment_type_summary AS
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
    year,
    month,
    COUNT(*) AS total_trips,
    SUM(fare_amount) AS total_revenue,
    ROUND(AVG(fare_amount), 4) AS avg_fare,
    ROUND(STDDEV(fare_amount), 4) AS stddev_fare,
    ROUND(AVG(trip_distance), 4) AS avg_distance,
    ROUND(AVG(speed_mph), 4) AS avg_speed_mph

FROM {config.ENRICHED_TABLE_NAME}

GROUP BY 
    CASE 
        WHEN payment_type = 0 THEN 'Flex Fare Trip'
        WHEN payment_type = 1 THEN 'Credit Card'
        WHEN payment_type = 2 THEN 'Cash'
        WHEN payment_type = 3 THEN 'No Charge'
        WHEN payment_type = 4 THEN 'Dispute'
        WHEN payment_type = 5 THEN 'Unknown'
        WHEN payment_type = 6 THEN 'Voided trip'
        ELSE 'Other'
    END, year, month
"""

KPI_MONTHLY_PAYMENT_TYPE_SUMMARY_QUERY = f"""
SELECT * 
FROM taxi_data.kpi_monthly_payment_type_summary
ORDER BY year, month
"""

def year_monthly_payment_type_summary_query(year_selected):
    return f"""
    SELECT *
    FROM taxi_data.kpi_monthly_payment_type_summary
    WHERE year={year_selected}
    ORDER BY year, month 
"""
