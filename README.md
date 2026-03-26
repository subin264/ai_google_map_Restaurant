# ai_google_map_Restaurant

- Project name is Restaurant ReviewFlash Berlin.
Reviews are grouped by star rating and representative sentences are extracted
using TextRank and MMR.
Users can understand key reasons for each star rating without reading hundreds of reviews."

1. While Google Maps presents a single aggregated rating such as 4.2 stars,it does not explain the reasons behind this score.
This project addresses the problem of spending more than 30 minutes reading hundreds of reviews in an unfamiliar language, or ultimately defaulting to familiar chain restaurants. The system presents core content and keywords extracted from reviews across each star rating group from 1 to 5 stars.

2.  Project Structure
  1. Code Files
      1. 1_scraping: Collection of restaurant metadata via the Google Maps API, combined with Playwright-based review scraping
      2. 2_eda_experiment_tuning: EDA, pipeline experimentation, parameter tuning, and evaluation metric analysis
      3. 3_pipeline: Final pipeline integrating preprocessing, TextRank, and MMR
      4. 4_app_ui: Streamlit demo application (UI design: Figma)
   2. Data Files
      1. Data1_Restaurant_Raw_Original: Raw restaurant data covering 6 districts and 6,229 restaurants
      2. Data2_Review_Raw_Original: Raw review data totaling 969,360 entries
      3. Data_1_raw_restaurant_Pipeline: Merged CSV from 6 districts with basic missing value handling, restaurant data
      4. Data_2_raw_review_Pipeline: Merged CSV from 6 districts with basic missing value handling,review data"
