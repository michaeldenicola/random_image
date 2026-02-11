"""
Niji Library Browser - Enhanced Streamlit App
==============================================
A powerful image browser for your Midjourney/Nijijourney library.

Features:
- Random image with filters (source, model, date, prompt)
- Prompt search
- Statistics dashboard
- Metadata display
- Gallery view

Setup:
1. Run `python export_manifest.py` to upload manifest to S3
2. Deploy this app to Streamlit Cloud
3. Set secrets in Streamlit Cloud dashboard

Secrets required (in Streamlit Cloud):
    AWS_BUCKET = "inklungsbucket"
    AWS_REGION = "us-east-2"
    MANIFEST_URL = "https://inklungsbucket.s3.us-east-2.amazonaws.com/manifest/manifest.json.gz"
"""

import streamlit as st
import pandas as pd
import json
import gzip
import random
from datetime import datetime, timedelta
from io import BytesIO
from typing import Optional, List, Dict
import requests

# ============== CONFIG ============== #
# These can be overridden by Streamlit secrets
DEFAULT_BUCKET = "inklungsbucket"
DEFAULT_REGION = "us-east-2"
DEFAULT_MANIFEST_URL = f"https://{DEFAULT_BUCKET}.s3.{DEFAULT_REGION}.amazonaws.com/manifest/manifest.json.gz"

# ============== PAGE CONFIG ============== #
st.set_page_config(
    page_title="Niji Library Browser",
    page_icon="🎨",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============== CUSTOM CSS ============== #
st.markdown("""
<style>
    /* Pinterest-style card hover effect */
    .stImage {
        border-radius: 12px;
        overflow: hidden;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    
    .stImage:hover {
        transform: translateY(-4px);
        box-shadow: 0 8px 25px rgba(0,0,0,0.3);
    }
    
    /* Card container styling */
    [data-testid="stVerticalBlock"] > [data-testid="stVerticalBlock"] {
        background-color: rgba(30, 30, 30, 0.5);
        border-radius: 12px;
        padding: 8px;
        margin-bottom: 12px;
    }
    
    /* Expander styling */
    .streamlit-expanderHeader {
        font-size: 0.85rem;
        padding: 0.25rem 0;
    }
    
    /* Make images rounded */
    .stImage img {
        border-radius: 8px;
    }
    
    /* Reduce padding in columns for tighter grid */
    [data-testid="column"] {
        padding: 0 4px;
    }
    
    /* Style the shuffle button */
    .stButton > button[kind="primary"] {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        border: none;
        border-radius: 25px;
        padding: 0.5rem 2rem;
        font-weight: 600;
    }
    
    .stButton > button[kind="primary"]:hover {
        background: linear-gradient(90deg, #764ba2 0%, #667eea 100%);
        transform: scale(1.02);
    }
    
    /* Metadata box styling */
    .metadata-box {
        background-color: #1e1e1e;
        padding: 1rem;
        border-radius: 0.5rem;
        margin-top: 1rem;
    }
    
    /* Stat card styling */
    .stat-card {
        background-color: #262730;
        padding: 1rem;
        border-radius: 0.5rem;
        text-align: center;
    }
    
    /* Caption styling */
    .stCaption {
        font-size: 0.75rem;
        opacity: 0.8;
    }
</style>
""", unsafe_allow_html=True)


# ============== DATA LOADING ============== #
@st.cache_data(ttl=3600)  # Cache for 1 hour
def load_manifest() -> pd.DataFrame:
    """Load manifest from S3."""
    # Get URL from secrets or use default
    manifest_url = st.secrets.get("MANIFEST_URL", DEFAULT_MANIFEST_URL)
    
    try:
        response = requests.get(manifest_url, timeout=30)
        response.raise_for_status()
        
        # Decompress if gzipped
        if manifest_url.endswith('.gz'):
            data = gzip.decompress(response.content)
            manifest = json.loads(data.decode('utf-8'))
        else:
            manifest = response.json()
        
        # Convert to DataFrame
        df = pd.DataFrame(manifest['images'])
        
        # Parse dates
        if 'created_at' in df.columns:
            df['created_at'] = pd.to_datetime(df['created_at'], errors='coerce')
            df['month'] = df['created_at'].dt.to_period('M').astype(str)
        
        return df
        
    except Exception as e:
        st.error(f"Failed to load manifest: {e}")
        return pd.DataFrame()


def filter_images(
    df: pd.DataFrame,
    source: Optional[str] = None,
    model: Optional[str] = None,
    prompt_search: Optional[str] = None,
    date_range: Optional[tuple] = None
) -> pd.DataFrame:
    """Apply filters to the image dataframe."""
    filtered = df.copy()
    
    if source and source != "All":
        filtered = filtered[filtered['source'] == source.lower()]
    
    if model and model != "All":
        filtered = filtered[filtered['model_version'] == model]
    
    if prompt_search:
        # Case-insensitive search in prompt
        mask = filtered['prompt'].fillna('').str.lower().str.contains(
            prompt_search.lower(), regex=False
        )
        filtered = filtered[mask]
    
    if date_range:
        start_date, end_date = date_range
        if start_date:
            filtered = filtered[filtered['created_at'] >= pd.Timestamp(start_date)]
        if end_date:
            filtered = filtered[filtered['created_at'] <= pd.Timestamp(end_date)]
    
    return filtered


# ============== PAGES ============== #
def page_random():
    """Random image viewer with Pinterest-style gallery."""
    st.title("🎲 Random Images")
    
    df = load_manifest()
    if df.empty:
        st.warning("No images loaded. Make sure the manifest is uploaded to S3.")
        return
    
    # Sidebar filters
    with st.sidebar:
        st.header("Filters")
        
        source_options = ["All"] + sorted(df['source'].dropna().unique().tolist())
        selected_source = st.selectbox("Source", source_options)
        
        model_options = ["All"] + sorted(df['model_version'].dropna().unique().tolist())
        selected_model = st.selectbox("Model", model_options)
        
        prompt_search = st.text_input("Prompt contains", "")
        
        st.subheader("Date Range")
        use_date_filter = st.checkbox("Filter by date")
        date_range = None
        if use_date_filter:
            min_date = df['created_at'].min().date() if not df['created_at'].isna().all() else datetime.now().date()
            max_date = df['created_at'].max().date() if not df['created_at'].isna().all() else datetime.now().date()
            date_range = st.date_input(
                "Select range",
                value=(min_date, max_date),
                min_value=min_date,
                max_value=max_date
            )
        
        st.divider()
        
        # Number of images to show
        num_images = st.slider("Number of images", min_value=10, max_value=100, value=50, step=10)
        
        # Column layout
        num_columns = st.slider("Columns", min_value=3, max_value=6, value=4)
    
    # Apply filters
    filtered_df = filter_images(
        df,
        source=selected_source,
        model=selected_model,
        prompt_search=prompt_search,
        date_range=date_range if use_date_filter else None
    )
    
    st.caption(f"Showing {min(num_images, len(filtered_df))} random images from {len(filtered_df):,} (filtered from {len(df):,} total)")
    
    # Shuffle button
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("🎲 Shuffle Images", use_container_width=True, type="primary"):
            st.session_state.random_seed = random.randint(0, 999999)
    
    # Initialize or get random seed
    if 'random_seed' not in st.session_state:
        st.session_state.random_seed = random.randint(0, 999999)
    
    if filtered_df.empty:
        st.warning("No images match your filters.")
        return
    
    # Select random images
    random.seed(st.session_state.random_seed)
    sample_size = min(num_images, len(filtered_df))
    random_indices = random.sample(range(len(filtered_df)), sample_size)
    selected_images = filtered_df.iloc[random_indices]
    
    # Create Pinterest-style masonry grid using columns
    cols = st.columns(num_columns)
    
    for idx, (_, image_data) in enumerate(selected_images.iterrows()):
        col_idx = idx % num_columns
        
        with cols[col_idx]:
            # Create a card-like container
            with st.container():
                # Image
                st.image(image_data['url'], use_container_width=True)
                
                # Show prompt preview on hover (using expander as workaround)
                if image_data.get('prompt'):
                    prompt_preview = str(image_data['prompt'])[:80] + "..." if len(str(image_data.get('prompt', ''))) > 80 else str(image_data.get('prompt', ''))
                    with st.expander("📋 Details", expanded=False):
                        st.caption(f"**Prompt:** {image_data.get('prompt', 'N/A')}")
                        st.caption(f"**Source:** {image_data.get('source', 'N/A')} | **Model:** {image_data.get('model_version', 'N/A')}")
                        if st.button("📋 Copy Prompt", key=f"copy_{idx}"):
                            st.code(image_data.get('prompt', ''), language=None)
                
                # Small spacing between cards
                st.write("")
    
    # Bottom buttons: Shuffle + Go to Top
    st.divider()
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        if st.button("🎲 Shuffle Again", use_container_width=True, type="primary", key="bottom_shuffle"):
            st.session_state.random_seed = random.randint(0, 999999)
            st.rerun()
    with col3:
        if st.button("⬆ Go to Top", use_container_width=True, key="random_top"):
            st.components.v1.html(
                "<script>window.parent.document.querySelector('section.main').scrollTo({top: 0, behavior: 'smooth'});</script>",
                height=0
            )


def page_search():
    """Search images by prompt."""
    st.title("🔍 Search by Prompt")
    
    df = load_manifest()
    if df.empty:
        return
    
    search_query = st.text_input("Search prompts", "", placeholder="e.g., cyberpunk samurai")
    
    if search_query:
        results = filter_images(df, prompt_search=search_query)
        
        st.caption(f"Found {len(results):,} images")
        
        if not results.empty:
            # Randomize and show up to 100 results
            display_count = min(100, len(results))
            
            # Initialize or update search shuffle seed per query
            search_seed_key = f"search_seed_{search_query}"
            if search_seed_key not in st.session_state:
                st.session_state[search_seed_key] = random.randint(0, 999999)
            
            sampled = results.sample(n=display_count, random_state=st.session_state[search_seed_key])
            
            # Display as grid
            cols = st.columns(4)
            for idx, (_, row) in enumerate(sampled.iterrows()):
                with cols[idx % 4]:
                    st.image(row['url'], use_container_width=True)
                    if row.get('prompt'):
                        st.caption(row['prompt'][:50] + "..." if len(str(row['prompt'])) > 50 else row['prompt'])
            
            if len(results) > 100:
                st.info(f"Showing 100 of {len(results):,} results")
            
            # Go to Top button at bottom
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                if st.button("⬆ Go to Top", use_container_width=True, key="search_top"):
                    st.components.v1.html(
                        "<script>window.parent.document.querySelector('section.main').scrollTo({top: 0, behavior: 'smooth'});</script>",
                        height=0
                    )


def page_stats():
    """Statistics dashboard."""
    st.title("📊 Library Statistics")
    
    df = load_manifest()
    if df.empty:
        return
    
    # Summary stats
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Images", f"{len(df):,}")
    
    with col2:
        likes_count = len(df[df['source'] == 'likes'])
        st.metric("Liked", f"{likes_count:,}")
    
    with col3:
        created_count = len(df[df['source'] == 'created'])
        st.metric("Created", f"{created_count:,}")
    
    with col4:
        models = df['model_version'].nunique()
        st.metric("Models Used", models)
    
    st.divider()
    
    # Charts
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Images by Month")
        if 'month' in df.columns:
            monthly = df.groupby('month').size().reset_index(name='count')
            monthly = monthly.sort_values('month')
            st.bar_chart(monthly.set_index('month'))
    
    with col2:
        st.subheader("Images by Source")
        source_counts = df['source'].value_counts()
        st.bar_chart(source_counts)
    
    # Model breakdown
    st.subheader("Images by Model")
    model_counts = df['model_version'].value_counts().head(10)
    st.bar_chart(model_counts)
    
    # Recent images
    st.subheader("Most Recent Images")
    recent = df.nlargest(8, 'created_at')
    cols = st.columns(4)
    for idx, (_, row) in enumerate(recent.iterrows()):
        with cols[idx % 4]:
            st.image(row['url'], use_container_width=True)


def page_gallery():
    """Browse all images in a gallery view."""
    st.title("🖼️ Gallery")
    
    df = load_manifest()
    if df.empty:
        return
    
    # Filters in sidebar
    with st.sidebar:
        st.header("Filters")
        
        source_options = ["All"] + sorted(df['source'].dropna().unique().tolist())
        selected_source = st.selectbox("Source", source_options, key="gallery_source")
        
        if 'month' in df.columns:
            month_options = ["All"] + sorted(df['month'].dropna().unique().tolist(), reverse=True)
            selected_month = st.selectbox("Month", month_options)
        else:
            selected_month = "All"
    
    # Apply filters
    filtered = df.copy()
    if selected_source != "All":
        filtered = filtered[filtered['source'] == selected_source.lower()]
    if selected_month != "All":
        filtered = filtered[filtered['month'] == selected_month]
    
    st.caption(f"Showing {len(filtered):,} images")
    
    # Pagination
    images_per_page = 20
    total_pages = max(1, len(filtered) // images_per_page + (1 if len(filtered) % images_per_page else 0))
    
    page = st.number_input("Page", min_value=1, max_value=total_pages, value=1)
    
    start_idx = (page - 1) * images_per_page
    end_idx = start_idx + images_per_page
    page_images = filtered.iloc[start_idx:end_idx]
    
    # Display grid
    cols = st.columns(4)
    for idx, (_, row) in enumerate(page_images.iterrows()):
        with cols[idx % 4]:
            st.image(row['url'], use_container_width=True)
            if st.button("View", key=f"view_{row['job_id']}"):
                st.session_state.selected_image = row.to_dict()
    
    st.caption(f"Page {page} of {total_pages}")


# ============== MAIN APP ============== #
def main():
    # Navigation
    st.sidebar.title("🎨 Niji Library")
    
    page = st.sidebar.radio(
        "Navigate",
        ["Random", "Search", "Gallery", "Stats"],
        label_visibility="collapsed"
    )
    
    # Render selected page
    if page == "Random":
        page_random()
    elif page == "Search":
        page_search()
    elif page == "Gallery":
        page_gallery()
    elif page == "Stats":
        page_stats()
    
    # Footer
    st.sidebar.divider()
    st.sidebar.caption("Built with ❤️ for AI art collectors")
    
    # Refresh button
    if st.sidebar.button("🔄 Refresh Data"):
        st.cache_data.clear()
        st.rerun()


if __name__ == "__main__":
    main()
