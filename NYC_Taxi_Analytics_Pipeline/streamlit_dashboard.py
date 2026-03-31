import sys
import os

# Adds the root directory to the python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

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
# 📋 Preview Query (CACHED)
# ========================
@st.cache_data(ttl=3600)
def load_preview(year):
    query = f"""
    SELECT *
    FROM {config.ENRICHED_TABLE_NAME}
    WHERE year = {year}
    LIMIT 100
    """
    return pd.read_sql(query, connection)

# ========================
# 🎛️ Sidebar Filters
# ========================
st.sidebar.header("Filters")

year_selected = st.sidebar.selectbox("Select Year", [2025, 2026])

# =========================
# Single Query to Create DF
# =========================
MAIN_QUERY = f"""
SELECT 
    month_date, 
    COUNT(*) AS total_trips, 
    AVG(speed_mph) AS avg_speed_mph,
    AVG(fare_amount) AS avg_fare, 
    SUM(fare_amount) AS total_revenue
FROM {config.ENRICHED_TABLE_NAME}
WHERE year = {year_selected}
GROUP BY month_date
ORDER BY month_date
"""

df = run_query(MAIN_QUERY)

# ===================
# Derived Metrics
# ===================
df["month_date"] = pd.to_datetime(df["month_date"])
df = df.sort_values("month_date")

df["cumulative_revenue"] = df["total_revenue"].cumsum()

# =================
# Streamlit Title
# =================
st.title("NYC Taxi Analytics Dashboard")

# ========================
# KPI SUMMARY
# ========================
st.subheader("Overview")

col1, col2, col3 = st.columns(3)

col1.metric("Total Revenue (USD)", f"${df['total_revenue'].sum():,.2f}")
col2.metric("Total Trips", f"{df['total_trips'].sum():,}")
col3.metric("Avg Revenue (USD) / Trip", f"${df['avg_fare'].mean():.2f}")

# ========================
# REVENUE TRENDS
# ========================
st.subheader("Monthly Revenue (USD) Trends")

# Prepare a tidy dataframe for Streamlit
chart_data = df.set_index("month_date")[["total_revenue", "cumulative_revenue"]]

# This handles the x-axis spacing and formatting automatically
st.bar_chart(chart_data)

# ========================
# Trips
# ========================
st.subheader("Monthly Trips")
st.bar_chart(df.set_index("month_date")["total_trips"])

# ========================
# Avg Fare
# ========================
st.subheader("Monthly Avg Revenue (USD) per Trip")
st.bar_chart(df.set_index("month_date")["avg_fare"])

# ===============
# Avg Speed by Hour
df_speed = run_query(queries.AVG_SPEED_HOURLY_QUERY)
st.subheader("Hourly Avg Speed (MPH)")
st.line_chart(df_speed.set_index("hour_of_day")["avg_speed_mph"])
# ===============

# =================
# Avg Distance and Fare by Payment Type
df_payment_type = run_query(queries.PAYMENT_METHOD_STATS_QUERY)
st.subheader("Avg Distance (Miles) By Payment Method")
st.bar_chart(df_payment_type.set_index("payment_method")["avg_distance"])

st.subheader("Avg Fare (USD) By Payment Method")
st.bar_chart(df_payment_type.set_index("payment_method")["avg_fare"])
# =================

# =============
# Data Preview
# =============
st.subheader("🔍 Data Preview")

df_preview = load_preview(year_selected)
st.dataframe(df_preview)