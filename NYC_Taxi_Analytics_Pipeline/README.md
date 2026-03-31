NYC Taxi Analytics Pipeline

**Project Overview**
This project is an end-to-end data engineering pipeline that ingests, cleans, and analyzes NYC Yellow Taxi trip data. Using AWS services and modern data stack tools, this project demonstrates the ability to handle millions of rows, optimize storage costs, and deliver actionable business insights via an interactive dashboard.

**Tech Stack**
* Cloud: AWS (S3, Athena)
* Language: Python (Pandas, PyArrow, boto3)
* SQL: Presto/Trino (via Amazon Athena)
* Dashboard: Streamlit

**Architecture**
* Storage: Amazon S3 (Free Tier, Raw and Processed Data)
* Processing: Python (Pandas/PyArrow) + AWS SDK (boto3)
* Analysis: AWS Athena
* Query Engine: Amazon Athena (Serverless SQL)

**Visualization: Streamlit**


**Key Engineering Decisions**

* Partition Projection & Metadata Optimization: I restructured the raw flat-file Parquet storage into a Hive-partitioned directory (year=/month=) in Amazon S3. This allowed Athena to use Partition Projection, skipping over millions of rows of irrelevant data based on the file path alone.

* Data Integrity and Quality Analysis
Created a function to document issues in data quality and combat them. At the same time, I did not go too aggressively into feature engineering to make sure not to lose potentially valuable information. For example, I removed rows with negative values for some columns like trip_duration_min but not others like fare_amount, as it is possible negative fare_amount signals something like a refund. For another example, I could have eliminated rows with extreme column values (such as fares in the hundreds of thousands of dollars), but in a real-life scenario, it would be helpful to have those rows in case those specific trips need to be looked into by the city.

* In practice, it would be more helpful to have a separate data file for issues that could be looked into by the city while not messing up my statistical analysis.

* Schema Enforcement & Casting: Even though the source was Parquet, I implemented a strict type-casting layer (e.g., ensuring passenger_count is float64 and payment_type is int64). This prevents "Schema Mismatch" errors in Athena when different raw files have slight metadata variations.

* Calculated Fields: To save on query-time compute costs, I added fields like trip_duration_min and speed_mph directly into the processed Parquet files. This gave me more control over the processed files and allowed me to avoid bottlenecks with using visual and paid interfaces like those on AWS to do the job for me.

**Key Analytical Insights**
All the queries can be found in my src/analytics/queries.py file

The top 5 months for total revenue are as follows:
Oct. 2025: %62.52M
May 2025: $63.16M
Sep. 2025: $60.7M
Dec. 2025: $60.3M
Nov. 2025: $60.0M

Monthly revenue increases/decreases were as follows:
Jan 2025 - Feb 2025: -7.64%
Feb 2025 - Mar 2025: +21.48%
Mar 2025 - Apr 2025: +0.62%
Apr 2025 - May 2025: +10.59%
May 2025 - June 2025: -8.93%
June 2025 - July 2025: -9.16%
July 2025 - Aug 2025: -4.35%
Aug 2025 - Sep 2025: +21.48%
Sep 2025 - Oct 2025: +7.92%
Oct 2025 - Nov 2025: -8.45%
Nov 2025 - Dec 2025: +0.59%
Dec 2025 - Jan 2026: -20.08%
Jan 2026 - Feb 2026: -8.22%

The average speed in miles per hour significantly decreases from 2:00 P.M. to 6:00 P.M. EST, and this likely indicates a traffic bottleneck such as due to rush hour

The average fare was $19.66 when paying with credit card versus $17.95 when paying with cash. There were also extremely high outliers in the hundreds of thousands of dollars for payments with cash, no charge, or disputed payments. These outliers alone caused the standard deviations for average fare for each of these payment types to be hundreds of dollars

This highlights a real data quality issue where manual entry or system errors create outliers that do not exist, unlike the automated credit card segment

**Analytics Highlights**
The dashboard answers critical business questions for stakeholders:

Monthly Revenue
Monthly Trips
Monthly Average Fare

**How to Run**
Python 3.11
Pip install streamlit, pandas, numpy, matplotlib, pyathena, python-dotenv, boto3, and botocore
* Step 1: Download the data from the yellow taxi section on the NYC Taxi Dataset website
* Step 2: Put the data into the data/raw folder
* Step 3: Run the upload_to_s3.py script from the root directory via "python -m src.data_ingestion.upload_to_s3". This will upload the raw data to S3
* Step 4: Run the process_taxi_data.py script from the root directory via "python -m src.etl.process_taxi_data". This will upload the processed data to S3
* Step 5: Create a database in AWS Athena and create the yellow_taxi_processed table with the YELLOW_TAXI_PROCESSED_QUERY from queries.py (run in Athena **WITH THE ACTUAL TABLE NAME replacing "{config.BUCKET_NAME}"**)
* Step 6: Run "MSCK REPAIR TABLE yellow_taxi_processed" so that Athena can find the partitions from our year=/month= folder structure
* Step 7: Create the yellow_taxi_enriched view via the YELLOW_TAXI_ENRICHED_QUERY in queries.py
* Step 8: Create the KPIs via the "KPI_...QUERY" queries in the queries.py file
* Step 9: Upload the files from your local machine (IE not including S3 or Athena) to GitHub
* Step 10: Connect the GitHub repository to Streamlit Community Cloud and deploy the app there
