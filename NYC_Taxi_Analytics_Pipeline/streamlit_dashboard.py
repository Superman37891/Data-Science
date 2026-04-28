import sys
import os

# Adds the root directory to the python path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, BASE_DIR)

import src.analytics.queries as queries # Now this should work

from pyathena import connect
import pandas as pd
import streamlit as st
import src.config as config

connection = connect(
    s3_staging_dir=config.S3_STAGING_DIR,
    region_name=config.AWS_REGION,
    aws_access_key_id=st.secrets["AWS_ACCESS_KEY_ID"],
    aws_secret_access_key=st.secrets["AWS_SECRET_ACCESS_KEY"],
    schema_name=config.DATABASE
)

@st.cache_data(ttl=3600)
def run_query(query):
    return pd.read_sql(query, connection)


# ========================
# 🎛Sidebar Filters
# ========================
st.sidebar.header("Filters")

year_selected = st.sidebar.selectbox("Select Year", [2025, 2026])

# Run the query once through Athena
# To utilize drastic speed increase with Partition Projection
MAIN_QUERY = f"""
SELECT 
    month_date, 
    COUNT(*) AS total_trips, 
    AVG(speed_mph) AS avg_speed_mph,
    AVG(fare_amount) AS avg_fare, 
    SUM(fare_amount) AS total_revenue
FROM {config.ENRICHED_TABLE_NAME}
WHERE year = {year_selected}
"""

monthly_df = run_query(queries.KPI_MONTHLY_SUMMARY_QUERY)
payment_df = run_query(queries.PAYMENT_METHOD_STATS_QUERY)
payment_df = payment_df.set_index("payment_method")
hourly_df = run_query(queries.HOURLY_TRIPS_QUERY)

st.write(payment_df.columns)
st.cache_data.clear()
# ===================
# Derived Metrics
# ===================

monthly_df["month_date"] = pd.to_datetime(monthly_df["month_date"])
monthly_df["month_num"] = monthly_df["month_date"].dt.month
# this may have a compiler warning of unexpected type (str, property), but this is because type checkers don't know the exact typing of the data
# the month value (a categorical string key in the Athena dataset) as an int

monthly_df = monthly_df.sort_values("month_date")

# ==========
# Indexed DFs for reusability

# Note that our df is already grouped by month_date, so no need for a separate monthly-indexed DF

# =================
# Streamlit Title
# =================
st.title("NYC Taxi Analytics Dashboard")
st.caption("Interactive dashboard analyzing NYC taxi revenue, trips, fares, and rider behavior.")

# ========================
# KPI SUMMARY
# ========================
st.subheader("Overview")

col1, col2, col3 = st.columns(3)

# Make the revenue fit on the screen
total_revenue = monthly_df["total_revenue"].sum()
if total_revenue >= 1_000_000_000:
    revenue_display = f"${total_revenue/1_000_000_000:.3f}B"
elif total_revenue >= 1_000_000:
    revenue_display = f"${total_revenue/1_000_000:.3f}M"
elif total_revenue >= 1_000:
    revenue_display = f"${total_revenue/1_000:.3f}K"
else:
    revenue_display = f"${total_revenue:.3f}"

col1.metric("Total Revenue (USD)", revenue_display)
col2.metric("Total Trips", f"{monthly_df['total_trips'].sum():,}")
col3.metric("Avg Revenue (USD) / Trip", f"${monthly_df['avg_fare'].mean():.2f}")

# ========================
# REVENUE TRENDS
# ========================

# Note that, since our df is already grouped by month_date, we don't need to
# make a separate df grouped by month

# Monthly Total Revenue
st.subheader("Monthly Total Revenue (USD)")
st.caption("X-axis: Month | Y-Axis: Total Monthly Revenue (USD)")
st.bar_chart(monthly_df["total_revenue"])

# Monthly Cumulative Revenue
st.subheader("Monthly Cumulative Revenue (USD)")
st.caption("X-axis: Month | Y-Axis: Monthly Cumulative Revenue (USD)")
st.bar_chart(monthly_df["cumulative_revenue"])

# Monthly Trips
st.subheader("Monthly Trips")
st.caption("X-axis: Month | Y-axis: Monthly Trips")
st.bar_chart(monthly_df["total_trips"])

# Monthly Avg Fare
st.subheader("Monthly Avg Revenue (USD) per Trip")
st.caption("X-axis: Month | Y-axis: Monthly Avg Revenue (USD) per Trip")
st.bar_chart(monthly_df["avg_fare"])

# Avg Speed by Hour
st.subheader("Hourly Avg Speed (MPH)")
st.caption("X-axis: Hour of Day | Y-axis: Avg Speed (MPH)")
st.line_chart(hourly_df.set_index("hour_of_day")["avg_speed_mph"])

# ==============================
# Stats by payment type
# ==============================

# Count of Trips by Payment Type
st.subheader("Number of trips by Payment Method")
st.table(payment_df[["payment_method", "total_trips"]])

# Avg Distance by Payment Type
st.subheader("Avg Distance (Miles) by Payment Method")
st.caption("X-axis: Payment Method | Y-axis: Avg Distance (Miles) by Payment Method")
st.bar_chart(payment_df["avg_distance"])

# Avg Fare by Payment Type
st.subheader("Avg Fare (USD) by Payment Method")
st.caption("X-axis: Payment Method | Y-axis: Avg Fare (USD) by Payment Method")
st.bar_chart(payment_df["avg_fare"])

# Standard Deviation of Fare by Payment Type
st.subheader("Standard Deviation of Fare (USD) by Payment Method")
st.caption("X-axis: Payment Method | Y-axis: Fare Standard Deviation (USD) by Payment Method")
st.bar_chart(payment_df["stdev_fare"])

# =============
# Data Preview
# =============
st.subheader("🔍 Data Preview")

df_preview = monthly_df.head(100)
st.dataframe(df_preview)


preview_csv = df_preview.to_csv(index=False).encode("utf-8")
st.caption("Download the Preview as a CSV")
st.download_button(
    label="Download Preview Data as CSV",
    data=preview_csv,
    file_name=f"nyc_taxi_preview_{year_selected}.csv",
    mime="text/csv"
)

# Yearly download
st.subheader("Yearly Data Download")
st.caption("WARNING: *VERY* Big File. Download the Full Year as a CSV.")

if st.button("Download Yearly Data"):
    yearly_data = monthly_df
    st.download_button(
        label=f"Download {year_selected} Data as CSV",
        data=yearly_data.to_csv(index=False).encode("utf-8"),
        file_name=f"nyc_taxi_year_{year_selected}.csv",
        mime="text/csv"
    )

# Monthly data download
st.subheader("📥 Download Data by Month")

month_selected = st.number_input("Month", min_value=1, max_value=12, step=1)

if st.button("Download Monthly Data"):

    selected_month_df = monthly_df[monthly_df["month_num"] == month_selected]
    st.caption(f"WARNING: Big File. Download Data for Selected Month and Year")
    st.download_button(
        label=f"Download {year_selected}_{month_selected} Data as CSV",
        data=selected_month_df.to_csv(index=False).encode("utf-8"),
        file_name=f"nyc_taxi_{year_selected}/{month_selected:02d}.csv",
        mime="text/csv"
    )