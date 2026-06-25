import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from transformers import pipeline
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials
import json
import time

# ---------- PAGE CONFIG ----------
st.set_page_config(page_title="Brand Review Web", page_icon="🌐", layout="wide")

# ---------- GOOGLE SHEETS CONNECTION ----------
@st.cache_resource
def get_sheet():
    try:
        creds_dict = json.loads(st.secrets["GOOGLE_CREDENTIALS"])
        scope = ["https://spreadsheets.google.com/feeds", 
                 "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        client = gspread.authorize(creds)
        SHEET_ID = "1RwNCgYLdnC2hSnLWKbnFk9qRDf7Zqu0pQ493wGUjXNg"
        return client.open_by_key(SHEET_ID).sheet1
    except Exception as e:
        return None

# ---------- DATA LOAD ----------
def load_reviews_from_sheet():
    sheet = get_sheet()
    if sheet is None:
        return None
    try:
        records = sheet.get_all_records()
        if not records:
            return []
        reviews = []
        for row in records:
            if not row.get("review"):
                continue
            try:
                rating_val = row.get("rating", 5)
                if isinstance(rating_val, str):
                    if "-" in rating_val:
                        rating = 5
                    else:
                        rating = int(float(rating_val))
                else:
                    rating = int(rating_val)
            except:
                rating = 5
            try:
                date_str = str(row.get("date", ""))
                if date_str and date_str.strip():
                    date_val = datetime.strptime(date_str, "%Y-%m-%d").date()
                else:
                    date_val = datetime.now().date()
            except:
                date_val = datetime.now().date()
            reviews.append({
                "brand": str(row.get("brand", "").strip()),
                "category": str(row.get("category", "").strip()),
                "product_name": str(row.get("product_name", "").strip()),
                "review": str(row.get("review", "").strip()),
                "rating": rating,
                "date": date_val
            })
        return reviews
    except Exception as e:
        st.sidebar.error(f"❌ Read Error: {str(e)[:80]}")
        return None

def add_review_to_sheet(review):
    sheet = get_sheet()
    if sheet is None:
        return False
    try:
        if not sheet.get_all_records():
            headers = ["brand", "category", "product_name", "review", "rating", "date"]
            sheet.append_row(headers, value_input_option="USER_ENTERED")
        row = [
            review["brand"],
            review["category"],
            review["product_name"],
            review["review"],
            review["rating"],
            review["date"].strftime("%Y-%m-%d")
        ]
        sheet.append_row(row, value_input_option="USER_ENTERED")
        return True
    except Exception as e:
        st.sidebar.error(f"❌ Write Error: {str(e)[:80]}")
        return False

def clear_google_sheet():
    try:
        sheet = get_sheet()
        if sheet is None:
            return False, "Google Sheets connection failed."
        sheet.clear()
        headers = ["brand", "category", "product_name", "review", "rating", "date"]
        sheet.append_row(headers, value_input_option="USER_ENTERED")
        return True, "Google Sheet cleared successfully!"
    except Exception as e:
        return False, f"Error clearing sheet: {str(e)}"

# ---------- SESSION STATE ----------
if "reviews" not in st.session_state:
    loaded = load_reviews_from_sheet()
    if loaded is not None and len(loaded) > 0:
        st.session_state.reviews = loaded
    else:
        st.session_state.reviews = [
            {"brand": "L'Oréal", "category": "Skincare", "product_name": "Revitalift", 
             "review": "Great product! My skin feels amazing.", "rating": 5, "date": datetime.now().date()},
            {"brand": "Nivea", "category": "Skincare", "product_name": "Soft Cream", 
             "review": "Loved it, very moisturizing.", "rating": 4, "date": datetime.now().date()}
        ]

if "uploaded_files" not in st.session_state:
    st.session_state.uploaded_files = set()

# ---------- AUTO SYNC ----------
if "_last_auto_sync" not in st.session_state:
    st.session_state._last_auto_sync = 0

current_time = time.time()
if current_time - st.session_state._last_auto_sync > 60:
    loaded = load_reviews_from_sheet()
    if loaded is not None and len(loaded) > 0:
        existing = st.session_state.reviews.copy()
        added_count = 0
        for new_review in loaded:
            is_dup = False
            for e in existing:
                if e["review"] == new_review["review"] and e["product_name"] == new_review["product_name"]:
                    is_dup = True
                    break
            if not is_dup:
                existing.append(new_review)
                added_count += 1
        if added_count > 0:
            st.session_state.reviews = existing
            st.session_state._last_auto_sync = current_time

# ---------- 🔥 FIXED: LOAD SENTIMENT MODEL (ALL CAPS) ----------
@st.cache_resource
def load_model():
    return pipeline("sentiment-analysis", model="cardiffnlp/twitter-roberta-base-sentiment-latest")

def analyze_reviews(reviews):
    if not reviews:
        return pd.DataFrame()
    
    classifier = load_model()
    
    valid_reviews = []
    for r in reviews:
        if r.get("review", "").strip():
            valid_reviews.append(r)
    
    if not valid_reviews:
        return pd.DataFrame()
    
    texts = [r["review"] for r in valid_reviews]
    results = []
    
    for i, text in enumerate(texts):
        pred = classifier(text)[0]
        label_raw = pred["label"]
        score = pred["score"]
        
        # 🔥 FIX: Return ALL CAPS labels
        if label_raw == "LABEL_0":
            sent = "NEGATIVE"
        elif label_raw == "LABEL_1":
            sent = "NEUTRAL"
        elif label_raw == "LABEL_2":
            sent = "POSITIVE"
        else:
            sent = label_raw.upper()  # Fallback: convert to uppercase
        
        results.append({
            "sentiment": sent, 
            "confidence": round(score * 100, 2)
        })
    
    df = pd.DataFrame(valid_reviews)
    sent_df = pd.DataFrame(results)
    
    # Combine
    final_df = pd.concat([df, sent_df], axis=1)
    
    # 🔥 FIX: Ensure all sentiment labels are ALL CAPS (if any lowercase exists)
    if "sentiment" in final_df.columns:
        final_df["sentiment"] = final_df["sentiment"].str.upper()
    
    return final_df

# ---------- SIDEBAR: MANUAL ENTRY ----------
st.sidebar.markdown("## ✍️ Add New Review")
with st.sidebar.form("add_review_form"):
    brand = st.text_input("Brand", value="L'Oréal")
    category = st.text_input("Category", value="Skincare")
    product = st.text_input("Product Name", value="Vitamin C Serum")
    review = st.text_area("Review", height=80, value="Amazing product!")
    rating = st.slider("Rating (1-5)", 1, 5, 5)
    if st.form_submit_button("➕ Add Review") and review.strip():
        new_review = {
            "brand": brand.strip(), "category": category.strip(),
            "product_name": product.strip(), "review": review.strip(),
            "rating": rating, "date": datetime.now().date()
        }
        add_review_to_sheet(new_review)
        st.session_state.reviews.append(new_review)
        st.rerun()

st.sidebar.markdown("---")

# ---------- SIDEBAR: CSV UPLOAD ----------
st.sidebar.markdown("### 📂 Upload CSV")

uploaded_file = st.sidebar.file_uploader("Upload CSV", type=["csv"], key="csv_uploader_main")

if uploaded_file:
    file_key = uploaded_file.name + str(uploaded_file.size)
    if file_key not in st.session_state.uploaded_files:
        try:
            df_upload = pd.read_csv(uploaded_file, encoding='utf-8', quoting=1)
            df_upload.columns = df_upload.columns.str.strip()
            
            review_col = None
            possible_review_cols = ["review", "text", "comment", "feedback", "customer_review"]
            for col in possible_review_cols:
                if col in df_upload.columns:
                    review_col = col
                    break
            
            if review_col is None:
                for col in df_upload.columns:
                    if df_upload[col].dtype == 'object':
                        sample = df_upload[col].dropna().astype(str)
                        if len(sample) > 0 and len(sample.iloc[0]) > 20:
                            review_col = col
                            break
            
            if review_col is None:
                st.sidebar.error("❌ Could not identify the 'review' column.")
            else:
                st.sidebar.info(f"ℹ️ Detected review column: '{review_col}'")
                df_upload.rename(columns={review_col: "review"}, inplace=True)
                
                required_cols = ["brand", "category", "product_name", "review"]
                if all(col in df_upload.columns for col in required_cols):
                    added = 0
                    for _, row in df_upload.iterrows():
                        review_text = str(row["review"]).strip()
                        if not review_text:
                            continue
                        
                        rating_val = 5
                        if "rating" in df_upload.columns:
                            try:
                                rating_val = int(row["rating"])
                            except:
                                rating_val = 5
                        else:
                            rating_val = 5
                        
                        try:
                            date_val = pd.to_datetime(row.get("date", datetime.now().date())).date()
                        except:
                            date_val = datetime.now().date()
                        
                        new_review = {
                            "brand": str(row["brand"]).strip(),
                            "category": str(row["category"]).strip(),
                            "product_name": str(row["product_name"]).strip(),
                            "review": review_text,
                            "rating": int(rating_val),
                            "date": date_val
                        }
                        
                        is_dup = False
                        for e in st.session_state.reviews:
                            if e["review"] == new_review["review"] and e["product_name"] == new_review["product_name"]:
                                is_dup = True
                                break
                        
                        if not is_dup:
                            add_review_to_sheet(new_review)
                            st.session_state.reviews.append(new_review)
                            added += 1
                    
                    st.session_state.uploaded_files.add(file_key)
                    st.sidebar.success(f"✅ {added} new reviews ADDED! Total: {len(st.session_state.reviews)}")
                    st.rerun()
                else:
                    st.sidebar.error(f"❌ CSV must have: brand, category, product_name, review")
        except Exception as e:
            st.sidebar.error(f"❌ CSV Error: {str(e)}")
    else:
        st.sidebar.info("ℹ️ This file was already uploaded.")

st.sidebar.markdown("---")

if st.sidebar.button("🔄 Emergency Sync"):
    with st.spinner("Syncing..."):
        loaded = load_reviews_from_sheet()
        if loaded is not None and len(loaded) > 0:
            existing = st.session_state.reviews.copy()
            added_count = 0
            for new_review in loaded:
                is_dup = False
                for e in existing:
                    if e["review"] == new_review["review"] and e["product_name"] == new_review["product_name"]:
                        is_dup = True
                        break
                if not is_dup:
                    existing.append(new_review)
                    added_count += 1
            st.session_state.reviews = existing
            st.sidebar.success(f"✅ Synced {len(loaded)} reviews! ({added_count} new)")
            st.rerun()
        else:
            st.sidebar.warning("⚠️ No data found.")

st.sidebar.markdown("---")

# ---------- RESET BUTTON ----------
if st.sidebar.button("🗑️ Reset Everything"):
    with st.spinner("Resetting data..."):
        success, message = clear_google_sheet()
        st.session_state.reviews = []
        st.session_state.uploaded_files = set()
        if success:
            st.sidebar.success("✅ Web data AND Google Sheet cleared successfully!")
        else:
            st.sidebar.error(f"❌ {message}")
        st.rerun()

# ---------- MAIN UI ----------
st.markdown("# 🌐 Brand Review Web")
st.caption("*Data is permanently saved to Google Sheets.*")

sheet = get_sheet()
if sheet is not None:
    st.success(f"✅ Google Sheets connected • {len(st.session_state.reviews)} reviews loaded")
else:
    st.info("ℹ️ Google Sheets not connected.")

# ---------- DASHBOARD ----------
if st.session_state.reviews:
    df = analyze_reviews(st.session_state.reviews)
    
    # 🔥 FIX: Ensure sentiment column exists and has values
    if df.empty or "sentiment" not in df.columns:
        st.warning("⚠️ No valid reviews to analyze. Please check your data.")
    else:
        # Count actual sentiments (case-insensitive)
        sentiment_counts = df["sentiment"].value_counts()
        
        # Get counts for each sentiment (handle case variations)
        pos_count = sentiment_counts.get("POSITIVE", 0) + sentiment_counts.get("positive", 0)
        neg_count = sentiment_counts.get("NEGATIVE", 0) + sentiment_counts.get("negative", 0)
        neu_count = sentiment_counts.get("NEUTRAL", 0) + sentiment_counts.get("neutral", 0)
        total = len(df)
        
        st.info(f"📊 **{len(df)}** reviews processed")
        
        # ---------- KPIs ----------
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("📝 Total", total)
        c2.metric("😊 Positive", f"{pos_count} ({round(pos_count/total*100 if total>0 else 0,1)}%)")
        c3.metric("😞 Negative", f"{neg_count} ({round(neg_count/total*100 if total>0 else 0,1)}%)")
        c4.metric("😐 Neutral", f"{neu_count} ({round(neu_count/total*100 if total>0 else 0,1)}%)")
        c5.metric("🎯 Avg Confidence", f"{df['confidence'].mean():.1f}%")
        
        # ---------- FILTERS ----------
        col1, col2, col3 = st.columns(3)
        with col1:
            brands = ["All"] + sorted(df["brand"].unique().tolist())
            selected_brand = st.selectbox("Brand", brands)
        with col2:
            categories = ["All"] + sorted(df["category"].unique().tolist())
            selected_category = st.selectbox("Category", categories)
        with col3:
            products = ["All"] + sorted(df["product_name"].unique().tolist())
            selected_product = st.selectbox("Product", products)
        
        filtered = df.copy()
        if selected_brand != "All":
            filtered = filtered[filtered["brand"] == selected_brand]
        if selected_category != "All":
            filtered = filtered[filtered["category"] == selected_category]
        if selected_product != "All":
            filtered = filtered[filtered["product_name"] == selected_product]
        
        if filtered.empty:
            st.warning("No reviews match the selected filters.")
        else:
            # ---------- FILTERED KPIs ----------
            f_total = len(filtered)
            f_pos = len(filtered[filtered["sentiment"].str.upper() == "POSITIVE"])
            f_neg = len(filtered[filtered["sentiment"].str.upper() == "NEGATIVE"])
            f_neu = len(filtered[filtered["sentiment"].str.upper() == "NEUTRAL"])
            
            st.markdown("### 📊 Filtered Results")
            col_a, col_b, col_c, col_d = st.columns(4)
            col_a.metric("Total", f_total)
            col_b.metric("Positive", f"{f_pos} ({round(f_pos/f_total*100 if f_total>0 else 0,1)}%)")
            col_c.metric("Negative", f"{f_neg} ({round(f_neg/f_total*100 if f_total>0 else 0,1)}%)")
            col_d.metric("Neutral", f"{f_neu} ({round(f_neu/f_total*100 if f_total>0 else 0,1)}%)")
            
            # ---------- CHARTS ----------
            left, right = st.columns(2)
            with left:
                st.subheader("Sentiment Distribution")
                sent_counts = filtered["sentiment"].value_counts()
                # Ensure uppercase for pie chart
                sent_counts.index = sent_counts.index.str.upper()
                colors = {"POSITIVE": "#4CAF50", "NEUTRAL": "#FFC107", "NEGATIVE": "#f44336"}
                fig = go.Figure(go.Pie(
                    labels=sent_counts.index,
                    values=sent_counts.values,
                    hole=0.4,
                    marker=dict(colors=[colors.get(s, "#888") for s in sent_counts.index])
                ))
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True)
            
            with right:
                st.subheader("Product Performance")
                # Group by product and sentiment
                prod_sent = filtered.groupby("product_name")["sentiment"].value_counts().unstack().fillna(0)
                # Ensure columns are uppercase
                prod_sent.columns = prod_sent.columns.str.upper()
                if not prod_sent.empty:
                    fig_bar = go.Figure()
                    for sent in ["POSITIVE", "NEUTRAL", "NEGATIVE"]:
                        if sent in prod_sent.columns:
                            fig_bar.add_trace(go.Bar(
                                name=sent,
                                x=prod_sent.index,
                                y=prod_sent[sent],
                                marker_color=colors.get(sent, "#888")
                            ))
                    fig_bar.update_layout(barmode="stack", xaxis_tickangle=45, height=400)
                    st.plotly_chart(fig_bar, use_container_width=True)
            
            # ---------- BRAND COMPARISON ----------
            st.subheader("🏢 Brand Comparison")
            brand_agg = filtered.groupby("brand")["sentiment"].value_counts().unstack().fillna(0)
            brand_agg.columns = brand_agg.columns.str.upper()
            if not brand_agg.empty:
                brand_agg["Positive %"] = round((brand_agg.get("POSITIVE", 0) / brand_agg.sum(axis=1)) * 100, 1)
                brand_agg = brand_agg.sort_values("Positive %", ascending=False)
                fig_brand = go.Figure()
                for sent in ["POSITIVE", "NEUTRAL", "NEGATIVE"]:
                    if sent in brand_agg.columns:
                        fig_brand.add_trace(go.Bar(
                            name=sent,
                            x=brand_agg.index,
                            y=brand_agg[sent],
                            marker_color=colors.get(sent, "#888")
                        ))
                fig_brand.update_layout(barmode="stack", height=300)
                st.plotly_chart(fig_brand, use_container_width=True)
            
            # ---------- TABLE ----------
            st.subheader("📋 All Reviews")
            display_df = filtered[["brand", "category", "product_name", "review", "sentiment", "confidence", "rating", "date"]]
            st.dataframe(display_df, use_container_width=True, height=400)
            
            st.download_button(
                label="⬇️ Download CSV",
                data=filtered.to_csv(index=False).encode("utf-8"),
                file_name=f"reviews_export_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                mime="text/csv",
                use_container_width=True
            )
else:
    st.warning("No reviews yet. Add from sidebar or upload CSV.")

st.caption("💾 All sentiment labels are now standardized to ALL CAPS for proper dashboard display.")