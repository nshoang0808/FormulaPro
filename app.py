import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import promo_intel as pi

# --- Page Configuration ---
st.set_page_config(page_title="Promotion Intelligence", layout="wide")

# --- Custom Styling for Finance Dashboard Aesthetic ---
st.markdown(
    """
    <style>
    /* Clean finance dashboard typography and metrics */
    [data-testid="stMetricValue"] {
        font-size: 1.85rem !important;
        font-weight: 700 !important;
        letter-spacing: -0.02em;
    }
    [data-testid="stMetricLabel"] {
        font-size: 0.85rem !important;
        font-weight: 600 !important;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        color: #57606a !important;
    }
    div[data-testid="stMetric"] {
        background-color: #f6f8fa;
        border: 1px solid #d0d7de;
        padding: 12px 18px;
        border-radius: 8px;
    }
    .hero-title {
        font-size: 2.2rem;
        font-weight: 800;
        letter-spacing: -0.03em;
        color: #1f2328;
        margin-bottom: 0px;
    }
    .hero-subtitle {
        font-size: 1.1rem;
        color: #57606a;
        margin-top: 2px;
        margin-bottom: 24px;
    }
    .section-header {
        font-size: 1.25rem;
        font-weight: 700;
        color: #1f2328;
        margin-top: 28px;
        margin-bottom: 6px;
    }
    .section-caption {
        font-size: 0.9rem;
        color: #57606a;
        margin-bottom: 14px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# --- Verdict Colors ---
VERDICT_COLORS = {
    "Winner": "#1a7f37",
    "Margin Trap": "#cf222e",
    "Cannibalizer": "#bc4c00",
    "Subsidy Dud": "#9a6700",
    "Underperformer": "#57606a",
}

# --- Cached Data Loaders ---
@st.cache_data
def load_kpis():
    return pi.get_kpis()

@st.cache_data
def load_leaderboard():
    return pi.get_leaderboard()

@st.cache_data
def load_timeseries(promo_id: str):
    return pi.get_promo_timeseries(promo_id)

@st.cache_data
def load_candidates():
    return pi.get_next_candidates()

# --- Initialize Session State for AI Insights & Recommendations ---
if "insights" not in st.session_state:
    st.session_state["insights"] = {}
if "next_recs" not in st.session_state:
    st.session_state["next_recs"] = None

# --- Page Header ---
st.markdown('<div class="hero-title">Promotion Intelligence</div>', unsafe_allow_html=True)
st.markdown('<div class="hero-subtitle">Which promotions make money, not just sales.</div>', unsafe_allow_html=True)

# ==============================================================================
# SECTION 1: KPI ROW
# ==============================================================================
kpis = load_kpis()
kpi_cols = st.columns(5)

with kpi_cols[0]:
    st.metric(
        label="Revenue",
        value=f"${kpis['total_revenue']:,.0f}",
    )

with kpi_cols[1]:
    st.metric(
        label="Gross Profit",
        value=f"${kpis['total_gross_profit']:,.0f}",
    )

with kpi_cols[2]:
    st.metric(
        label="Discount Spend",
        value=f"${kpis['total_discount_spend']:,.0f}",
    )

with kpi_cols[3]:
    net_inc = kpis["net_incremental_profit"]
    sign = "+$" if net_inc > 0 else ("-$" if net_inc < 0 else "$")
    st.metric(
        label="Net Incremental Profit (from promotions)",
        value=f"{sign}{abs(net_inc):,.0f}",
    )

with kpi_cols[4]:
    st.metric(
        label="Promotions Losing Money",
        value=str(int(kpis["losing_promo_count"])),
    )

# ==============================================================================
# SECTION 2: PROMOTION LEADERBOARD
# ==============================================================================
st.markdown('<div class="section-header">Promotion Leaderboard</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="section-caption">Promotions ranked by net incremental profit (actual incremental profit after cannibalization & subsidies).</div>',
    unsafe_allow_html=True,
)

lb_df = load_leaderboard()

# Prepare leaderboard columns for display
display_lb = pd.DataFrame({
    "Promotion": lb_df["promo_name"],
    "Product": lb_df["product_name"],
    "Discount": lb_df["discount_pct"],
    "Lift": lb_df["lift_pct"],
    "Breakeven Lift": lb_df["breakeven_lift_pct"].apply(
        lambda x: "Impossible" if pd.isna(x) else f"{x:+.0%}" if x != 0 else "0%"
    ),
    "Incremental Revenue": lb_df["incremental_revenue"],
    "Net Incremental Profit": lb_df["net_incremental_profit"],
    "ROI": lb_df["promo_roi"],
    "Verdict": lb_df["verdict"],
})

def style_verdict_badge(val):
    c = VERDICT_COLORS.get(val, "#57606a")
    return f"background-color: {c}1a; color: {c}; font-weight: 700; border-radius: 4px;"

styled_lb = display_lb.style.map(style_verdict_badge, subset=["Verdict"])

lb_column_config = {
    "Promotion": st.column_config.TextColumn("Promotion", width="medium"),
    "Product": st.column_config.TextColumn("Product", width="medium"),
    "Discount": st.column_config.NumberColumn("Discount", format="percent", step=1),
    "Lift": st.column_config.NumberColumn("Lift", format="percent", step=1),
    "Breakeven Lift": st.column_config.TextColumn("Breakeven Lift"),
    "Incremental Revenue": st.column_config.NumberColumn("Incremental Revenue", format="$%,d"),
    "Net Incremental Profit": st.column_config.NumberColumn("Net Incremental Profit", format="$%,d"),
    "ROI": st.column_config.NumberColumn("ROI", format="percent", step=1),
    "Verdict": st.column_config.TextColumn("Verdict"),
}

st.dataframe(
    styled_lb,
    column_config=lb_column_config,
    hide_index=True,
)

# ==============================================================================
# SECTION 3: PROMOTION DRILL-DOWN
# ==============================================================================
st.markdown('<div class="section-header">Promotion Drill-down</div>', unsafe_allow_html=True)

# Find default promotion: Margin Trap with largest incremental_revenue, fallback to first row
margin_traps = lb_df[lb_df["verdict"] == "Margin Trap"]
if not margin_traps.empty:
    default_promo_id = margin_traps.sort_values("incremental_revenue", ascending=False).iloc[0]["promo_id"]
else:
    default_promo_id = lb_df.iloc[0]["promo_id"]

promo_options = lb_df["promo_id"].tolist()
default_index = promo_options.index(default_promo_id) if default_promo_id in promo_options else 0
promo_name_map = dict(zip(lb_df["promo_id"], lb_df["promo_name"]))

selected_promo_id = st.selectbox(
    "Promotion",
    options=promo_options,
    index=default_index,
    format_func=lambda pid: promo_name_map.get(pid, pid),
    key="promo_select",
)

# Selected promotion details
promo_row = lb_df[lb_df["promo_id"] == selected_promo_id].iloc[0]
verdict = promo_row["verdict"]
verdict_color = VERDICT_COLORS.get(verdict, "#57606a")

# Format metrics for drill-down cards
lift_val = promo_row["lift_pct"]
lift_str = f"{lift_val:+.0%}"
if pd.isna(promo_row["breakeven_lift_pct"]):
    be_str = "Impossible"
else:
    be_str = f"{promo_row['breakeven_lift_pct']:.0%}"

inc_rev = promo_row["incremental_revenue"]
inc_rev_str = f"{'+$' if inc_rev > 0 else ('-$' if inc_rev < 0 else '$')}{abs(inc_rev):,.0f}"

net_profit = promo_row["net_incremental_profit"]
net_profit_str = f"{'+$' if net_profit > 0 else ('-$' if net_profit < 0 else '$')}{abs(net_profit):,.0f}"

# Verdict badge + 3 small metrics
m_cols = st.columns([1.2, 1.3, 1.3, 1.3])

with m_cols[0]:
    st.markdown(
        f"""
        <div style="
            margin-top: 10px;
            padding: 8px 14px;
            border-radius: 8px;
            background-color: {verdict_color}18;
            border: 2px solid {verdict_color};
            text-align: center;
        ">
            <div style="font-size: 0.75rem; text-transform: uppercase; font-weight: 700; color: #57606a;">Verdict</div>
            <div style="font-size: 1.15rem; font-weight: 800; color: {verdict_color}; margin-top: 2px;">● {verdict}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with m_cols[1]:
    st.metric(label="Lift vs. Breakeven Lift", value=f"{lift_str} vs. {be_str}")

with m_cols[2]:
    st.metric(label="Incremental Revenue", value=inc_rev_str)

with m_cols[3]:
    st.metric(label="Net Incremental Profit", value=net_profit_str)

# Timeseries Chart
ts_df = load_timeseries(selected_promo_id)
fig = go.Figure()

promo_days = ts_df[ts_df["is_promo_day"]]
if not promo_days.empty:
    start_date = promo_days["date"].min()
    end_date = promo_days["date"].max()
    fig.add_vrect(
        x0=start_date,
        x1=end_date,
        fillcolor="rgba(207, 34, 46, 0.08)" if verdict == "Margin Trap" else "rgba(9, 105, 218, 0.08)",
        layer="below",
        line_width=1,
        line_color="rgba(0, 0, 0, 0.12)",
        annotation_text="Promotion Window",
        annotation_position="top left",
        annotation=dict(font_size=11, font_color="#57606a"),
    )

baseline_val = float(ts_df["baseline_daily_units"].iloc[0]) if not ts_df.empty else 0.0
fig.add_hline(
    y=baseline_val,
    line_dash="dash",
    line_color="#57606a",
    line_width=1.5,
    annotation_text=f"Baseline ({baseline_val:.1f} units/day)",
    annotation_position="top right",
    annotation=dict(font_size=11, font_color="#57606a"),
)

fig.add_trace(
    go.Scatter(
        x=ts_df["date"],
        y=ts_df["units"],
        mode="lines+markers",
        name="Daily Units",
        line=dict(color="#0969da", width=2.5),
        marker=dict(size=5, color="#0969da"),
        hovertemplate="<b>Date</b>: %{x|%Y-%m-%d}<br><b>Units</b>: %{y}<extra></extra>",
    )
)

fig.update_layout(
    height=340,
    margin=dict(l=20, r=20, t=25, b=20),
    template="plotly_white",
    xaxis=dict(title="Date", showgrid=True, gridcolor="#f0f2f5"),
    yaxis=dict(title="Units Sold", showgrid=True, gridcolor="#f0f2f5"),
    hovermode="x unified",
    showlegend=False,
)

st.plotly_chart(fig)

# AI Analysis Button & Container
if st.button("Analyze with AI", key="analyze_btn", type="primary"):
    with st.spinner("Analyzing promotion performance with AI..."):
        insight = pi.analyze_promo(selected_promo_id)
        st.session_state["insights"][selected_promo_id] = insight

insight = st.session_state["insights"].get(selected_promo_id)
if insight:
    if insight.source == "fallback":
        st.caption("Offline insight (AI unavailable)")

    st.markdown(f"#### **{insight.headline}**")
    st.write(insight.explanation)

    st.markdown("**Root Causes:**")
    for rc in insight.root_causes:
        st.markdown(f"- {rc}")

    if insight.actions:
        st.markdown("**Recommended Actions:**")
        cols = st.columns(len(insight.actions))
        for col, act in zip(cols, insight.actions):
            with col:
                with st.container(border=True):
                    type_label = act.type.replace("_", " ").title()
                    conf_c = "#1a7f37" if act.confidence == "high" else ("#9a6700" if act.confidence == "medium" else "#57606a")
                    st.markdown(
                        f"""
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                            <span style="font-weight:700; font-size:0.8rem; text-transform:uppercase; color:#0969da; background:#ddf4ff; padding:2px 8px; border-radius:4px;">{type_label}</span>
                            <span style="font-size:0.75rem; font-weight:700; color:{conf_c}; border:1px solid {conf_c}; padding:1px 6px; border-radius:10px;">{act.confidence.upper()} CONFIDENCE</span>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                    st.markdown(f"**{act.action}**")
                    st.markdown(f"<div style='color:#57606a; font-size:0.88rem; margin-top:4px;'><b>Impact:</b> {act.expected_impact}</div>", unsafe_allow_html=True)

# ==============================================================================
# SECTION 4: NEXT PROMOTIONS
# ==============================================================================
st.markdown('<div class="section-header">Next Promotions</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="section-caption">Candidate products for upcoming promotions, scored to protect gross profit.</div>',
    unsafe_allow_html=True,
)

cand_df = load_candidates()
cand_display = pd.DataFrame({
    "Product": cand_df["product_name"],
    "Category": cand_df["category"],
    "Margin": cand_df["margin_pct"],
    "Category Avg Lift": cand_df["category_avg_lift"],
    "Suggested Discount": cand_df["suggested_discount_pct"].apply(
        lambda x: "Full price" if pd.isna(x) or x is None else f"{x:.0%}"
    ),
    "Projected Incremental Profit": cand_df["projected_incremental_profit"],
})

cand_config = {
    "Product": st.column_config.TextColumn("Product", width="medium"),
    "Category": st.column_config.TextColumn("Category", width="medium"),
    "Margin": st.column_config.NumberColumn("Margin", format="percent", step=1),
    "Category Avg Lift": st.column_config.NumberColumn("Category Avg Lift", format="percent", step=1),
    "Suggested Discount": st.column_config.TextColumn("Suggested Discount"),
    "Projected Incremental Profit": st.column_config.NumberColumn("Projected Incremental Profit", format="$%,d"),
}

st.dataframe(
    cand_display,
    column_config=cand_config,
    hide_index=True,
)

if st.button("Get AI recommendations", key="recommend_btn", type="primary"):
    with st.spinner("Generating AI recommendations for next promotion cycle..."):
        recs = pi.recommend_next()
        st.session_state["next_recs"] = recs

recs = st.session_state.get("next_recs")
if recs:
    if any(r.source == "fallback" for r in recs):
        st.caption("Offline insight (AI unavailable)")

    st.markdown("**Strategic Recommendations:**")
    cards = recs[:5]
    num_cols = 3 if len(cards) >= 3 else len(cards)
    for i in range(0, len(cards), num_cols):
        chunk = cards[i:i + num_cols]
        cols = st.columns(len(chunk))
        for col, rec in zip(cols, chunk):
            with col:
                with st.container(border=True):
                    disc_text = (
                        f"{rec.suggested_discount_pct:.0%}"
                        if rec.suggested_discount_pct is not None and not pd.isna(rec.suggested_discount_pct)
                        else "Full price"
                    )
                    conf_c = "#1a7f37" if rec.confidence == "high" else ("#9a6700" if rec.confidence == "medium" else "#57606a")
                    st.markdown(
                        f"""
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                            <span style="font-size:0.75rem; font-weight:700; color:{conf_c}; border:1px solid {conf_c}; padding:1px 6px; border-radius:10px;">{rec.confidence.upper()} CONFIDENCE</span>
                            <span style="font-weight:700; font-size:0.85rem; color:#1a7f37; background:#dafbe1; padding:2px 8px; border-radius:4px;">Discount: {disc_text}</span>
                        </div>
                        <div style="font-size:1.05rem; font-weight:700; color:#1f2328; margin-bottom:6px;">{rec.product_name}</div>
                        """,
                        unsafe_allow_html=True,
                    )
                    st.markdown(f"**Rationale:** {rec.rationale}")
                    st.markdown(f"<div style='color:#57606a; font-size:0.88rem; margin-top:4px;'><b>Impact:</b> {rec.expected_impact}</div>", unsafe_allow_html=True)
