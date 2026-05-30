import sys
import os

# Adds the root directory to the python path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

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

year_selected = st.sidebar.selectbox("Select Year", [2024, 2025, 2026])

# Create dataframes through Athena queries
monthly_summary_df = run_query(queries.KPI_MONTHLY_SUMMARY_QUERY)
payment_summary_df = run_query(queries.PAYMENT_METHOD_STATS_QUERY)
payment_summary_df = payment_summary_df.set_index("payment_method")
hourly_df = run_query(queries.HOURLY_TRIPS_QUERY)
# ===================
# Derived Metrics
# ===================

monthly_summary_df["month_date"] = pd.to_datetime(monthly_summary_df["month_date"])
monthly_summary_df = monthly_summary_df.sort_values("month_date")
monthly_summary_df = monthly_summary_df.set_index("month_date")
monthly_summary_df = monthly_summary_df[monthly_summary_df["year"] == year_selected]
monthly_summary_df["month_num"] = monthly_summary_df["month_date"].dt.month
# this may have a compiler warning of unexpected type (str, property), but this is because type checkers don't know the exact typing of the data
# the month value (a categorical string key in the Athena dataset) as an int

monthly_summary_df = monthly_summary_df.sort_values("month_date")

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
total_revenue = monthly_summary_df["total_revenue"].sum()
if total_revenue >= 1_000_000_000:
    revenue_display = f"${total_revenue/1_000_000_000:.3f}B"
elif total_revenue >= 1_000_000:
    revenue_display = f"${total_revenue/1_000_000:.3f}M"
elif total_revenue >= 1_000:
    revenue_display = f"${total_revenue/1_000:.3f}K"
else:
    revenue_display = f"${total_revenue:.3f}"

col1.metric("Total Revenue (USD)", revenue_display)
col2.metric("Total Trips", f"{monthly_summary_df['total_trips'].sum():,}")
col3.metric("Avg Revenue (USD) / Trip", f"${monthly_summary_df['avg_fare'].mean():.2f}")

# ========================
# REVENUE TRENDS
# ========================

# Note that, since our df is already grouped by month_date, we don't need to
# make a separate df grouped by month

# Monthly Total Revenue
st.subheader("Monthly Total Revenue (USD)")
st.caption("X-axis: Month | Y-Axis: Total Monthly Revenue (USD)")
st.line_chart(monthly_summary_df["total_revenue"])

# Monthly Cumulative Revenue
st.subheader("Monthly Cumulative Revenue (USD)")
st.caption("X-axis: Month | Y-Axis: Monthly Cumulative Revenue (USD)")
st.line_chart(monthly_summary_df["cumulative_revenue"])

# Monthly Trips
st.subheader("Monthly Trips")
st.caption("X-axis: Month | Y-axis: Monthly Trips")
st.line_chart(monthly_summary_df["total_trips"])

# Monthly Avg Fare
st.subheader("Monthly Avg Revenue (USD) per Trip")
st.caption("X-axis: Month | Y-axis: Monthly Avg Revenue (USD) per Trip")
st.line_chart(monthly_summary_df["avg_fare"])

# Avg Speed by Hour
st.subheader("Hourly Avg Speed (MPH)")
st.caption("X-axis: Hour of Day | Y-axis: Avg Speed (MPH)")
st.line_chart(hourly_df.set_index("hour_of_day")["avg_speed_mph"])

# ==============================
# Stats by payment type
# ==============================

# Count of Trips by Payment Type
st.subheader("Number of trips by Payment Method")
st.table(payment_summary_df[["total_trips"]])

# Avg Distance by Payment Type
st.subheader("Avg Distance (Miles) by Payment Method")
st.caption("X-axis: Payment Method | Y-axis: Avg Distance (Miles) by Payment Method")
st.bar_chart(payment_summary_df[["avg_distance"]])

# Avg Fare by Payment Type
st.subheader("Avg Fare (USD) by Payment Method")
st.caption("X-axis: Payment Method | Y-axis: Avg Fare (USD) by Payment Method")
st.bar_chart(payment_summary_df[["avg_fare"]])

# Standard Deviation of Fare by Payment Type
st.subheader("Standard Deviation of Fare (USD) by Payment Method")
st.caption("X-axis: Payment Method | Y-axis: Fare Standard Deviation (USD) by Payment Method")
st.bar_chart(payment_summary_df[["stdev_fare"]])

# =============
# Data Preview
# =============
st.subheader("Data Preview (15 rows)")

preview_path = os.path.join(BASE_DIR, "preprocessed_preview_data", "nyc_taxi_preview_15.csv")
df_preview = pd.read_csv(preview_path)
st.dataframe(df_preview)

preview_csv = df_preview.to_csv(index=False).encode("utf-8")
st.caption("Download the Preview as a CSV")
st.download_button(
    label="Download Preview Data as CSV",
    data=preview_csv,
    file_name=f"nyc_taxi_preview.csv",
    mime="text/csv"
)

# Yearly download
st.subheader("Yearly Data Summary Download")

if st.button("Download Yearly Summary Data"):
    yearly_data_df = monthly_summary_df[monthly_summary_df["year"] == year_selected]
    st.download_button(
        label=f"Download {year_selected} Summary Data as CSV",
        data=yearly_data_df.to_csv(index=False).encode("utf-8"),
        file_name=f"nyc_taxi_year_{year_selected}.csv",
        mime="text/csv"
    )

# Monthly data download
st.subheader("📥 Download Monthly Summary Data")
st.caption("If you want the raw monthly data, get it from the NYC Taxi Dataset website / Yellow Taxi Dataset")
month_selected = st.number_input("Month", min_value=1, max_value=12, step=1)

if st.button("Download Monthly Summary Data"):
    selected_month_df = monthly_summary_df[
        (monthly_summary_df["month_num"] == month_selected) &
        (monthly_summary_df["year"] == year_selected)
    ]
    st.download_button(
        label=f"Download {year_selected}_{month_selected:02d} Summary Data as CSV",
        data=selected_month_df.to_csv(index=False).encode("utf-8"),
        file_name=f"nyc_taxi_{year_selected}/{month_selected:02d}.csv",
        mime="text/csv"
    )