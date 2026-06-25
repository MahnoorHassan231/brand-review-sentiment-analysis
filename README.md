# Brand Review Sentiment Analysis

A full-stack NLP application to collect, analyze, and manage customer reviews. Features real-time sentiment classification, persistent cloud storage, and an interactive analytics dashboard.

**Live Demo:** [huggingface.co/spaces/Mahnoor4789/brand-review-web](https://huggingface.co/spaces/Mahnoor4789/brand-review-web)

---

## AI Model & Core Techniques

This project applies key concepts from Natural Language Processing (NLP) and MLOps:

- **Model Architecture** – Uses a pre-trained transformer model (`cardiffnlp/twitter-roberta-base-sentiment-latest`). RoBERTa is an optimized variant of BERT trained on 124 million tweets, making it highly effective for short, informal text like customer reviews.

- **Transfer Learning** – Leverages the model's pre-trained weights instead of training from scratch. This reduces computational cost while maintaining high accuracy on domain-specific data.

- **Model Caching** – Implements `@st.cache_resource` to load the 500 MB model into memory only once. Consecutive inferences run in under 200ms, drastically reducing latency for end-users.

- **Case-Insensitive Label Mapping** – Standardizes model outputs (LABEL_0 → NEGATIVE, LABEL_2 → POSITIVE) and converts all sentiment labels to uppercase, ensuring consistent dashboard rendering regardless of input variations.

---

## System Layers (How Data Flows)

The application follows a layered architecture to separate concerns and improve maintainability:

1. **Input Layer (UI)** – Users interact via the Streamlit sidebar. They can either fill out a manual form (Brand, Category, Product, Review, Rating) or upload a CSV file. File uploads trigger auto-detection of the review column.

2. **Write Layer (Persistence)** – Once a review is submitted, it is immediately appended as a new row to a Google Sheet using the `gspread` library. This is an **append-only** operation, meaning existing rows are never modified or deleted during normal usage.

3. **Inference Layer (NLP Processing)** – The review text is passed to the Hugging Face pipeline. The RoBERTa model processes the text and returns a raw label (LABEL_0, LABEL_1, LABEL_2) along with a confidence score between 0 and 1. The label is then mapped to human-readable sentiment.

4. **Read Layer (Sync)** – On page refresh (or via manual sync button), the application queries the Google Sheet for all existing records. A 60-second cooldown throttle prevents hitting Google's API read limits (60 requests/minute). Deduplication logic checks existing reviews (by review text and product name) to prevent duplicates before merging new data.

5. **Visualization Layer (Dashboard)** – The final processed data is passed to Plotly to render interactive charts (Sentiment Distribution Pie Chart, Product Performance Bar Chart, Brand Comparison Stacked Chart) and to Streamlit to display the main data table with filtering capabilities (Brand, Category, Product).

---

## Storage & Concurrency Model

- **Append-Only Write**: Prevents data conflicts. If two users submit reviews at the exact same time, both are added as new rows at the bottom of the sheet, ensuring neither overwrites the other's entry.
- **Deduplication**: The system scans existing entries for identical (review + product_name) pairs before writing, keeping the dataset clean and free of redundant records.
- **Stateless UI**: Filters and visualizations operate on the cached DataFrame, so users can explore data without triggering unnecessary API calls to Google Sheets.

---

## Tech Stack

- **Frontend** – Streamlit
- **NLP / AI Model** – Hugging Face Transformers (RoBERTa)
- **Storage** – Google Sheets API (gspread)
- **Visualization** – Plotly
- **Data Handling** – Pandas
- **Deployment** – Hugging Face Spaces

---

## CSV Format

To upload bulk reviews, ensure your CSV has these columns:

| Column | Type |
| :--- | :--- |
| brand | Text |
| category | Text |
| product_name | Text |
| review | Text |
| rating | Integer (1-5) |
| date | Date (YYYY-MM-DD) |

Example:
