# ai_google_map_Restaurant

- Project name is Restaurant ReviewFlash Berlin.
Reviews are grouped by star rating and representative sentences are extracted
using TextRank and MMR.
Users can understand key reasons for each star rating without reading hundreds of reviews."

## Video

[Code walkthrough playlist (YouTube)](https://www.youtube.com/playlist?list=PLI0Ags0Mk8JzyMsOGdbPhZM0Miw76f4sU)

### YouTube code walkthrough playlist (7 videos)

**Playlist name:** `Restaurant ReviewFlash Berlin – Code walkthrough (7 steps)`  
Shorter: `RRF Berlin – code walkthrough 01–07`

In **YouTube Studio > Content** (or the playlist), open each video > **Title** and paste the **New title** below. Use **Length** (and thumbnail) to tell two different clips that were both saved as `2 5` on the phone.

| # | New title (paste this) | Old name (what you see now) | Length (reference) |
|---|------------------------|-----------------------------|--------------------|
| 1 | `01 – Web code run: reviews (first)` | 2 리뷰 | ~2:56 |
| 2 | `02 – EDA 2_2` | eda2 2 | ~4:48 |
| 3 | `03 – EDA 2_4` | eda 2 4 | ~5:32 |
| 4 | `04 – EDA 2_5 (part 1)` | 2 5 (first of two) | ~4:39 |
| 5 | `05 – EDA 2_5 (part 2)` | 2 5 (second of two) | ~4:39 |
| 6 | `06 – Part 3: final pipeline execution` | 3코드실행 파이프랑니 | ~1:47 |
| 7 | `07 – Part 3: final UI walkthrough` | 3최종 | (varies) |

**Playlist order:** drag videos in the playlist so the order is **1 > 2 > 3 > 4 > 5 > 6 > 7** as in the table.

If your two `2 5` files are **not** both for `2_5`, swap rows 4–5 titles after you check the thumbnails; the table still gives you seven distinct names.


## 1.motive

: While Google Maps presents a single aggregated rating such as 4.2 stars, it does not explain the reasons behind this score.
This project addresses the problem of spending more than 30 minutes reading hundreds of reviews in an unfamiliar language, or ultimately defaulting to familiar chain restaurants. The system presents core content and keywords extracted from reviews across each star rating group from 1 to 5 stars.

## 3. Project Structure

**1. Code Files**

1. 1_scraping: Collection of restaurant metadata via the Google Maps API, combined with Playwright-based review scraping
2. 2_eda_experiment_tuning: EDA, pipeline experimentation, parameter tuning, and evaluation metric analysis
3. 3_pipeline: Final pipeline integrating preprocessing, TextRank, and MMR
4. 4_app_ui: Streamlit demo application (UI design: Figma)

**2. Data Files**

1. Data1_Restaurant_Raw_Original: Raw restaurant data covering 6 districts and 6,229 restaurants
2. Data2_Review_Raw_Original: Raw review data totaling 969,360 entries
3. Data_1_raw_restaurant_Pipeline: Merged CSV from 6 districts with basic missing value handling, restaurant data
4. Data_2_raw_review_Pipeline: Merged CSV from 6 districts with basic missing value handling, review data

## 4. Basic Information

### 4.1 Dataset

: Collection region is Berlin 6 districts, Mitte, Friedrichshain-Kreuzberg, Pankow, Charlottenburg-Wilmersdorf, Tempelhof Schöneberg, Neukölln.

### 4.2 Algorithm: TextRank

TextRank is an unsupervised sentence ranking method that operates without labels, serving as the primary filtering stage. 
The following tuning values were adopted:min_sim=0.08, d=0.95,max_iter=100. 
The number of candidate sentences is dynamically configured as min(20, max(10, ⌊n × 0.4⌋)).

### 4.3 Algorithm: MMR

(Maximal Marginal Relevance)

MMR was applied as a post-processing step to eliminate redundancy from TextRank results. Since the objective
is to capture the overall context of reviews, diversity was prioritized as the primary criterion. The formula MMR = λ × sim1 − (1−λ) × sim2 was applied with a tuning value of λ=0.3.
The final number of output sentences is dynamically determined as max(3, min(5, ⌊n × 0.2⌋)).

### 4.4 Evaluation Metric

Since this project employs an unsupervised approach, reference-based metrics such as ROUGE and BLEU cannot be used.
Therefore, a Diversity Score was directly defined to verify whether the TextRank and MMR combination operates as intended.
Three methods were compared across 30 restaurants: 1. Random, 2. TextRank only, 3. TextRank + MMR.
Diversity = 1 − (1 / n(n−1)) ×
Σ cos_sim(si, sj)

## Tech Stack

Python · Google Maps Places API ·
Playwright · spaCy · TF-IDF ·
Streamlit · Figma"
