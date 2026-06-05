import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import mysql.connector
import warnings
warnings.filterwarnings('ignore')

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title = "International Debt Analysis",
    page_icon  = "🌍",
    layout     = "wide",
    initial_sidebar_state = "expanded"
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .main-title  { font-size:2rem; font-weight:700; color:#1565C0; }
    .sub-title   { font-size:1rem; color:#555; margin-bottom:1.2rem; }
    .kpi-card    { background:#f0f4ff; border-radius:10px; padding:.9rem 1.1rem;
                   border-left:4px solid #1565C0; }
    .kpi-label   { font-size:.78rem; color:#777; font-weight:500; }
    .kpi-value   { font-size:1.45rem; font-weight:700; color:#1565C0; }
    .section-hdr { font-size:1.1rem; font-weight:600; color:#333;
                   border-bottom:2px solid #1565C0; padding-bottom:4px;
                   margin-top:1.4rem; margin-bottom:.7rem; }
    .sql-box     { background:#1e1e2e; color:#cdd6f4; font-family:monospace;
                   font-size:.85rem; padding:1rem; border-radius:8px;
                   white-space:pre-wrap; overflow-x:auto; line-height:1.6; }
    .badge-basic { background:#e3f2fd; color:#1565C0; padding:2px 8px;
                   border-radius:12px; font-size:.75rem; font-weight:600; }
    .badge-inter { background:#fff3e0; color:#e65100; padding:2px 8px;
                   border-radius:12px; font-size:.75rem; font-weight:600; }
    .badge-adv   { background:#fce4ec; color:#880e4f; padding:2px 8px;
                   border-radius:12px; font-size:.75rem; font-weight:600; }
</style>
""", unsafe_allow_html=True)


# LOAD CSV DATA
# Load the final_merged_debt_data.csv file.
# @st.cache_data means it loads once and caches — no reload on every user interaction.

@st.cache_data(show_spinner="Loading dataset...")
def load_data():
    # Load the cleaned CSV file and optimise memory usage.
    # category dtype = stores repeated strings very efficiently.

    df = pd.read_csv('final_merged_debt_data.csv')
    df = df[df['Region'].notna()].copy()

    # Convert numeric columns
    df['year']       = pd.to_numeric(df['year'],       errors='coerce')
    df['debt_value'] = pd.to_numeric(df['debt_value'], errors='coerce')
    df.dropna(subset=['year','debt_value'], inplace=True)
    df['year'] = df['year'].astype('int16')          # int16 saves memory vs int64

    # Convert repeated string columns to category — major memory saving
    for col in ['Country Name','Country Code','Region',
                'Income Group','Lending category','indicator','indicator_code']:
        if col in df.columns:
            df[col] = df[col].astype('category')

    return df

df = load_data()


# SIDEBAR — FILTERS
# Create filter widgets in the left sidebar.
# Users can filter by year, region, income group, or specific countries.
# df_filt = the filtered version of df used by all charts below.

st.sidebar.markdown("## Filters")
year_min, year_max = int(df['year'].min()), int(df['year'].max())
year_range = st.sidebar.slider("Year Range", year_min, year_max, (year_min, year_max))
all_regions  = sorted(df['Region'].dropna().unique())
all_income   = sorted(df['Income Group'].dropna().unique())
all_countries= sorted(df['Country Name'].dropna().unique())
sel_regions  = st.sidebar.multiselect("Region",       all_regions,  default=all_regions)
sel_income   = st.sidebar.multiselect("Income Group", all_income,   default=all_income)
sel_countries= st.sidebar.multiselect("Country (optional)", all_countries, default=[])
st.sidebar.markdown("---")
st.sidebar.markdown("**Data Source:** World Bank IDS  \n**Years:** 2000–2024")

df_filt = df[
    (df['year'].between(year_range[0], year_range[1])) &
    (df['Region'].isin(sel_regions)) &
    (df['Income Group'].isin(sel_income))
].copy()
if sel_countries:
    df_filt = df_filt[df_filt['Country Name'].isin(sel_countries)]


# HEADER
st.markdown('<div class="main-title">International Debt Analysis Dashboard</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">World Bank IDS · 2000–2024 · Individual Countries</div>', unsafe_allow_html=True)


# KPI CARDS
# Show 5 summary numbers at the top of the dashboard.
# KPI = Key Performance Indicator. Each card shows one important metric.

total_debt  = df_filt['debt_value'].sum()
n_countries = df_filt['Country Name'].nunique()
peak_yr_s   = df_filt.groupby('year')['debt_value'].sum()
peak_year   = int(peak_yr_s.idxmax()) if not peak_yr_s.empty else 0
top_country = df_filt.groupby('Country Name')['debt_value'].sum().idxmax() if not df_filt.empty else "N/A"
avg_debt    = df_filt.groupby('Country Name')['debt_value'].sum().mean()

c1,c2,c3,c4,c5 = st.columns(5)
for col, label, val, sub in [
    (c1, "Total Debt",       f"{total_debt/1e15:.2f} Q",  "Quadrillion USD"),
    (c2, "Countries",        f"{n_countries}",             "Individual nations"),
    (c3, "Peak Year",        f"{peak_year}",               "Highest global total"),
    (c4, "Top Debtor",       f"{top_country}",             "Highest total debt"),
    (c5, "Avg per Country",  f"{avg_debt/1e12:.1f}T",      "USD Trillions"),
]:
    col.markdown(f'''<div class="kpi-card">
        <div class="kpi-label">{label}</div>
        <div class="kpi-value">{val}</div>
        <div class="kpi-label">{sub}</div>
    </div>''', unsafe_allow_html=True)

st.markdown("---")


# ROW 1 — Trend + Top 10

cl, cr = st.columns([6,4])
with cl:
    st.markdown('<div class="section-hdr">Global Debt Trend by Year</div>', unsafe_allow_html=True)
    yr = df_filt.groupby('year')['debt_value'].sum().reset_index()
    yr.columns = ['Year','Total Debt']
    yr['YoY (%)'] = yr['Total Debt'].pct_change().mul(100).round(2)
    ft = make_subplots(rows=2, cols=1, row_heights=[0.65,0.35], vertical_spacing=0.08)
    ft.add_trace(go.Scatter(x=yr['Year'], y=yr['Total Debt'], mode='lines+markers',
        line=dict(color='#1565C0',width=2.5), fill='tozeroy',
        fillcolor='rgba(21,101,192,0.12)',
        hovertemplate='Year: %{x}<br>Debt: $%{y:,.0f}<extra></extra>'), row=1, col=1)
    bar_c = ['#2E7D32' if v>=0 else '#C62828' for v in yr['YoY (%)'].fillna(0)]
    ft.add_trace(go.Bar(x=yr['Year'], y=yr['YoY (%)'], marker_color=bar_c,
        hovertemplate='Year: %{x}<br>Growth: %{y:.2f}%<extra></extra>'), row=2, col=1)
    ft.update_layout(height=380, showlegend=False, margin=dict(t=10,b=10),
                     plot_bgcolor='white', paper_bgcolor='white')
    st.plotly_chart(ft, use_container_width=True)

with cr:
    st.markdown('<div class="section-hdr">Top 10 Countries</div>', unsafe_allow_html=True)
    t10 = df_filt.groupby('Country Name')['debt_value'].sum().nlargest(10).reset_index()
    t10.columns = ['Country','Total Debt']
    t10['T'] = (t10['Total Debt']/1e12).round(2)
    fb = px.bar(t10.sort_values('T'), x='T', y='Country', orientation='h',
                color='T', color_continuous_scale='Blues', text='T')
    fb.update_traces(texttemplate='%{text:.1f}T', textposition='outside')
    fb.update_layout(height=380, coloraxis_showscale=False,
                     margin=dict(t=10,b=10), plot_bgcolor='white', paper_bgcolor='white')
    st.plotly_chart(fb, use_container_width=True)


# ── ROW 2 — World Map ────────────────────────────────────────────────────────

st.markdown('<div class="section-hdr">🗺️ World Map — Total Debt by Country</div>',
            unsafe_allow_html=True)


map_d = (
    df_filt
    .assign(
        iso_alpha = df_filt['Country Code'].astype(str),
        Country   = df_filt['Country Name'].astype(str)
    )
    .groupby(['iso_alpha', 'Country'], observed=True)['debt_value']
    .sum()
    .reset_index()
)
map_d = map_d[map_d['debt_value'] > 0].copy()
map_d['Debt (Billions)'] = (map_d['debt_value'] / 1e9).round(2)


fm = px.choropleth(
    map_d,
    locations              = 'iso_alpha',
    color                  = 'Debt (Billions)',
    hover_name             = 'Country',
    hover_data             = {'Debt (Billions)': ':,.1f', 'iso_alpha': False},
    color_continuous_scale = 'YlOrRd',
    title                  = 'Total External Debt by Country (2000–2024) — USD Billions'
)
fm.update_layout(
    height=420,
    margin=dict(t=0, b=0, l=0, r=0),
    geo=dict(showframe=False, showcoastlines=True, projection_type='natural earth'),
    coloraxis_colorbar=dict(title='USD Billions')
)
st.plotly_chart(fm, use_container_width=True)

# ROW 3 — Income Group + Region

c3a, c3b = st.columns(2)
with c3a:
    st.markdown('<div class="section-hdr">Debt by Income Group per Year</div>', unsafe_allow_html=True)
    iy = (df_filt.dropna(subset=['Income Group']).groupby(['year','Income Group'])['debt_value']
          .sum().reset_index())
    iy['T'] = (iy['debt_value']/1e12).round(3)
    fi = px.bar(iy, x='year', y='T', color='Income Group', barmode='stack',
        color_discrete_map={'High income':'#1565C0','Upper middle income':'#42A5F5',
                            'Lower middle income':'#FF9800','Low income':'#EF5350'},
        labels={'year':'Year','T':'USD Trillions'})
    fi.update_layout(height=380, plot_bgcolor='white', paper_bgcolor='white', margin=dict(t=10,b=10),
        legend=dict(orientation='h', yanchor='bottom', y=1.01, xanchor='right', x=1, font=dict(size=10)))
    st.plotly_chart(fi, use_container_width=True)

with c3b:
    st.markdown('<div class="section-hdr">Debt Share by Region</div>', unsafe_allow_html=True)
    rd = (df_filt.dropna(subset=['Region']).groupby('Region')['debt_value'].sum().reset_index())
    rd['T'] = (rd['debt_value']/1e12).round(2)
    rd['Short'] = rd['Region'].str.split('&').str[0].str.strip()
    fr = px.pie(rd, names='Short', values='T', hole=0.35,
                color_discrete_sequence=px.colors.qualitative.Set2)
    fr.update_traces(textposition='inside', texttemplate='%{label}<br>%{percent:.1%}',
                     hovertemplate='%{label}<br>%{value:.1f}T<extra></extra>')
    fr.update_layout(height=380, margin=dict(t=10,b=10), showlegend=False)
    st.plotly_chart(fr, use_container_width=True)


# ROW 4 — Country Comparison

st.markdown('<div class="section-hdr">🔍 Country-wise Debt Trend (Select up to 5)</div>', unsafe_allow_html=True)
defaults = [c for c in ['China','India','Brazil','Indonesia','Pakistan'] if c in all_countries][:5]
compare  = st.multiselect("Choose countries:", all_countries, default=defaults, max_selections=5)
if compare:
    dc = (df_filt[df_filt['Country Name'].isin(compare)]
          .groupby(['year','Country Name'])['debt_value'].sum().reset_index())
    dc['T'] = (dc['debt_value']/1e12).round(3)
    fc = px.line(dc, x='year', y='T', color='Country Name', markers=True,
                 labels={'year':'Year','T':'USD Trillions','Country Name':'Country'})
    fc.update_layout(height=380, plot_bgcolor='white', paper_bgcolor='white', margin=dict(t=10),
        legend=dict(orientation='h', yanchor='bottom', y=1.01, xanchor='right', x=1))
    st.plotly_chart(fc, use_container_width=True)


# ROW 5 — Raw Data Table

st.markdown('<div class="section-hdr">Filtered Data Table</div>', unsafe_allow_html=True)
with st.expander("Show / Hide Data Table"):
    # Show filtered data as a table.
    # MEMORY FIX: Limit to 10,000 rows max.
    # Showing 1.3M rows at once caused a 124 MB memory crash.
    MAX_DISPLAY = 10_000
    show_cols = ['Country Name','Country Code','Region','Income Group','indicator','year','debt_value']
    tbl = df_filt[show_cols].head(MAX_DISPLAY).copy()
    tbl['debt_value'] = tbl['debt_value'].round(2)    # round numbers — no string formatting
    tbl.columns = ['Country','Code','Region','Income Group','Indicator','Year','Debt Value (USD)']
    # Convert category columns back to string for display
    for col in tbl.select_dtypes(['category']).columns:
        tbl[col] = tbl[col].astype(str)
    st.dataframe(tbl, use_container_width=True, height=350)
    total_rows = len(df_filt)
    if total_rows > MAX_DISPLAY:
        st.caption(f"Showing first {MAX_DISPLAY:,} of {total_rows:,} rows. Use filters to narrow down.")
    else:
        st.caption(f"Showing {total_rows:,} rows")


# ROW 6 — SQL QUERY EXPLORER
# Let the user pick any of 30 SQL queries from a dropdown.
# Run = execute against MySQL and show results.
# Edit = open SQL in a text box to modify it.
# Lock = save your edits and prevent accidental changes.

st.markdown("---")
st.markdown('<div class="section-hdr">🗄️ SQL Query Explorer — 30 Queries (Basic · Intermediate · Advanced)</div>', unsafe_allow_html=True)
st.caption("Connect to MySQL and run any of the 30 project queries. Edit and lock as needed.")

# ── MySQL connection helper ───────────────────────────────────────────────────
def get_mysql_conn():
    try:
        conn = mysql.connector.connect(
            host='localhost', user='root', password='root',
            database='international_debt_db'
        )
        return conn, None
    except Exception as e:
        return None, str(e)

# ── All 30 SQL queries ────────────────────────────────────────────────────────
SQL_QUERIES = {
    "Q01": """SELECT * FROM debt_data LIMIT 10;""",

    "Q02": """SELECT COUNT(*) AS total_records FROM debt_data;""",

    "Q03": """SELECT country_code, country_name, region, income_group
FROM countries
WHERE region IS NOT NULL
ORDER BY country_name;""",

    "Q04": """SELECT indicator_code, indicator_name, topic
FROM indicators
ORDER BY topic, indicator_name
LIMIT 20;""",

    "Q05": """SELECT d.country_code, c.country_name, i.indicator_name, d.year, d.debt_value
FROM debt_data d
JOIN countries  c ON d.country_code   = c.country_code
JOIN indicators i ON d.indicator_code = i.indicator_code
WHERE d.country_code = 'IND'
ORDER BY d.year, i.indicator_name
LIMIT 20;""",

    "Q06": """SELECT d.country_code, c.country_name, d.indicator_code, d.debt_value
FROM debt_data d
JOIN countries c ON d.country_code = c.country_code
WHERE d.year = 2020
  AND c.region IS NOT NULL
ORDER BY d.debt_value DESC
LIMIT 20;""",

    "Q07": """SELECT d.country_code, c.country_name, d.indicator_code, d.year, d.debt_value
FROM debt_data d
JOIN countries c ON d.country_code = c.country_code
WHERE d.debt_value > 1000000000
  AND c.region IS NOT NULL
ORDER BY d.debt_value DESC
LIMIT 20;""",

    "Q08": """SELECT d.country_code, c.country_name, COUNT(*) AS record_count
FROM debt_data d
JOIN countries c ON d.country_code = c.country_code
WHERE c.region IS NOT NULL
GROUP BY d.country_code, c.country_name
ORDER BY record_count DESC
LIMIT 15;""",

    "Q09": """SELECT d.country_code, c.country_name, i.indicator_name, d.year, d.debt_value
FROM debt_data d
JOIN countries  c ON d.country_code   = c.country_code
JOIN indicators i ON d.indicator_code = i.indicator_code
WHERE c.region IS NOT NULL
ORDER BY d.debt_value DESC
LIMIT 10;""",

    "Q10": """SELECT country_code, country_name, income_group, lending_category
FROM countries
WHERE region = 'South Asia'
ORDER BY country_name;""",

    "Q11": """SELECT d.country_code, c.country_name,
       FORMAT(SUM(d.debt_value), 2) AS total_debt_usd
FROM debt_data d
JOIN countries c ON d.country_code = c.country_code
WHERE c.region IS NOT NULL
GROUP BY d.country_code, c.country_name
ORDER BY SUM(d.debt_value) DESC
LIMIT 15;""",

    "Q12": """SELECT d.year, FORMAT(SUM(d.debt_value), 2) AS global_total_debt
FROM debt_data d
JOIN countries c ON d.country_code = c.country_code
WHERE c.region IS NOT NULL
GROUP BY d.year
ORDER BY d.year;""",

    "Q13": """SELECT c.income_group,
       COUNT(DISTINCT d.country_code)    AS countries,
       FORMAT(AVG(d.debt_value), 2)      AS avg_debt,
       FORMAT(SUM(d.debt_value), 2)      AS total_debt
FROM debt_data d
JOIN countries c ON d.country_code = c.country_code
WHERE c.income_group IS NOT NULL
GROUP BY c.income_group
ORDER BY SUM(d.debt_value) DESC;""",

    "Q14": """SELECT c.region,
       COUNT(DISTINCT d.country_code)  AS countries,
       FORMAT(SUM(d.debt_value), 2)    AS total_debt
FROM debt_data d
JOIN countries c ON d.country_code = c.country_code
WHERE c.region IS NOT NULL
GROUP BY c.region
ORDER BY SUM(d.debt_value) DESC;""",

    "Q15": """SELECT d.country_code, c.country_name,
       FORMAT(SUM(d.debt_value), 2) AS total_debt
FROM debt_data d
JOIN countries c ON d.country_code = c.country_code
WHERE c.region IS NOT NULL
GROUP BY d.country_code, c.country_name
HAVING SUM(d.debt_value) > (
    SELECT AVG(ctry_sum)
    FROM (
        SELECT SUM(d2.debt_value) AS ctry_sum
        FROM debt_data d2
        JOIN countries c2 ON d2.country_code = c2.country_code
        WHERE c2.region IS NOT NULL
        GROUP BY d2.country_code
    ) t
)
ORDER BY SUM(d.debt_value) DESC;""",

    "Q16": """SELECT d.indicator_code,
       LEFT(i.indicator_name, 55)          AS indicator_name,
       FORMAT(SUM(d.debt_value), 2)        AS total_debt
FROM debt_data d
JOIN indicators i ON d.indicator_code = i.indicator_code
JOIN countries  c ON d.country_code   = c.country_code
WHERE c.region IS NOT NULL
GROUP BY d.indicator_code, i.indicator_name
ORDER BY SUM(d.debt_value) DESC
LIMIT 10;""",

    "Q17": """SELECT c.lending_category,
       COUNT(DISTINCT d.country_code)  AS countries,
       FORMAT(SUM(d.debt_value), 2)    AS total_debt
FROM debt_data d
JOIN countries c ON d.country_code = c.country_code
WHERE c.lending_category IS NOT NULL
GROUP BY c.lending_category
ORDER BY SUM(d.debt_value) DESC;""",

    "Q18": """SELECT d.year,
       FORMAT(SUM(d.debt_value), 2) AS annual_debt
FROM debt_data d
WHERE d.country_code = 'CHN'
GROUP BY d.year
ORDER BY d.year;""",

    "Q19": """SELECT d.country_code, c.country_name,
       COUNT(DISTINCT d.indicator_code) AS indicator_count
FROM debt_data d
JOIN countries c ON d.country_code = c.country_code
WHERE c.region IS NOT NULL
GROUP BY d.country_code, c.country_name
ORDER BY indicator_count DESC
LIMIT 15;""",

    "Q20": """SELECT d.country_code, c.country_name,
       COUNT(*)                         AS negative_records,
       FORMAT(SUM(d.debt_value), 2)     AS total_negative
FROM debt_data d
JOIN countries c ON d.country_code = c.country_code
WHERE d.debt_value < 0
  AND c.region IS NOT NULL
GROUP BY d.country_code, c.country_name
ORDER BY SUM(d.debt_value) ASC
LIMIT 10;""",

    "Q21": """SELECT country_name, total_debt,
       RANK() OVER (ORDER BY total_debt DESC) AS debt_rank
FROM (
    SELECT c.country_name,
           SUM(d.debt_value) AS total_debt
    FROM debt_data d
    JOIN countries c ON d.country_code = c.country_code
    WHERE c.region IS NOT NULL
    GROUP BY c.country_name
) ranked
ORDER BY debt_rank
LIMIT 15;""",

    "Q22": """SELECT year, annual_debt,
       FORMAT(SUM(annual_debt) OVER (ORDER BY year), 2) AS cumulative_debt
FROM (
    SELECT d.year, SUM(d.debt_value) AS annual_debt
    FROM debt_data d
    JOIN countries c ON d.country_code = c.country_code
    WHERE c.region IS NOT NULL
    GROUP BY d.year
) yearly
ORDER BY year;""",

    "Q23": """SELECT year, annual_debt,
       LAG(annual_debt) OVER (ORDER BY year)          AS prev_year_debt,
       ROUND(
           (annual_debt - LAG(annual_debt) OVER (ORDER BY year))
           / LAG(annual_debt) OVER (ORDER BY year) * 100, 2
       )                                               AS yoy_growth_pct
FROM (
    SELECT d.year, SUM(d.debt_value) AS annual_debt
    FROM debt_data d
    JOIN countries c ON d.country_code = c.country_code
    WHERE c.region IS NOT NULL
    GROUP BY d.year
) yearly
ORDER BY year;""",

    "Q24": """SELECT country_name,
       FORMAT(total_debt, 2)                                  AS total_debt_usd,
       ROUND(total_debt * 100.0 / global_total, 2)           AS pct_of_global
FROM (
    SELECT c.country_name,
           SUM(d.debt_value) AS total_debt,
           (SELECT SUM(d2.debt_value)
            FROM debt_data d2
            JOIN countries c2 ON d2.country_code = c2.country_code
            WHERE c2.region IS NOT NULL) AS global_total
    FROM debt_data d
    JOIN countries c ON d.country_code = c.country_code
    WHERE c.region IS NOT NULL
    GROUP BY c.country_name
) t
WHERE total_debt * 100.0 / global_total > 5
ORDER BY pct_of_global DESC;""",

    "Q25": """SELECT country_name, region, total_debt,
       RANK() OVER (PARTITION BY region ORDER BY total_debt DESC) AS rank_in_region
FROM (
    SELECT c.country_name, c.region,
           SUM(d.debt_value) AS total_debt
    FROM debt_data d
    JOIN countries c ON d.country_code = c.country_code
    WHERE c.region IS NOT NULL
    GROUP BY c.country_name, c.region
) t
ORDER BY region, rank_in_region
LIMIT 30;""",

    "Q26": """SELECT year, annual_debt,
       ROUND(
           AVG(annual_debt) OVER (ORDER BY year ROWS BETWEEN 2 PRECEDING AND CURRENT ROW),
           2
       ) AS moving_avg_3yr
FROM (
    SELECT d.year, SUM(d.debt_value) AS annual_debt
    FROM debt_data d
    JOIN countries c ON d.country_code = c.country_code
    WHERE c.region IS NOT NULL
    GROUP BY d.year
) yearly
ORDER BY year;""",

    "Q27": """SELECT year, annual_debt, prev_debt,
       ROUND((annual_debt - prev_debt) / prev_debt * 100, 2) AS growth_pct
FROM (
    SELECT year, annual_debt,
           LAG(annual_debt) OVER (ORDER BY year) AS prev_debt
    FROM (
        SELECT d.year, SUM(d.debt_value) AS annual_debt
        FROM debt_data d
        JOIN countries c ON d.country_code = c.country_code
        WHERE c.region IS NOT NULL
        GROUP BY d.year
    ) base
) with_lag
WHERE prev_debt IS NOT NULL
ORDER BY growth_pct DESC
LIMIT 5;""",

    "Q28": """SELECT d.country_code, c.country_name, c.income_group,
       FORMAT(SUM(d.debt_value), 2)  AS country_total,
       FORMAT(grp.avg_debt, 2)       AS group_average
FROM debt_data d
JOIN countries c ON d.country_code = c.country_code
JOIN (
    SELECT c2.income_group,
           AVG(ctry.ctry_total) AS avg_debt
    FROM (
        SELECT d2.country_code, SUM(d2.debt_value) AS ctry_total
        FROM debt_data d2
        JOIN countries c3 ON d2.country_code = c3.country_code
        WHERE c3.income_group IS NOT NULL AND c3.region IS NOT NULL
        GROUP BY d2.country_code
    ) ctry
    JOIN countries c2 ON ctry.country_code = c2.country_code
    GROUP BY c2.income_group
) grp ON c.income_group = grp.income_group
WHERE c.income_group IS NOT NULL AND c.region IS NOT NULL
GROUP BY d.country_code, c.country_name, c.income_group, grp.avg_debt
HAVING SUM(d.debt_value) > grp.avg_debt
ORDER BY c.income_group, SUM(d.debt_value) DESC
LIMIT 20;""",

    "Q29": """SELECT country_name, total_debt,
       ROUND(PERCENT_RANK() OVER (ORDER BY total_debt) * 100, 1) AS percentile_rank
FROM (
    SELECT c.country_name,
           SUM(d.debt_value) AS total_debt
    FROM debt_data d
    JOIN countries c ON d.country_code = c.country_code
    WHERE c.region IS NOT NULL
    GROUP BY c.country_name
) t
ORDER BY percentile_rank DESC
LIMIT 20;""",

    "Q30": """SELECT d.year, c.income_group,
       FORMAT(SUM(d.debt_value), 2) AS total_debt
FROM debt_data d
JOIN countries c ON d.country_code = c.country_code
WHERE c.income_group IS NOT NULL
  AND d.year >= 2020
GROUP BY d.year, c.income_group
ORDER BY d.year, SUM(d.debt_value) DESC;""",
}

DROPDOWN_OPTIONS = [
    "Q01 (Basic) \u2014 Preview debt_data Table",
    "Q02 (Basic) \u2014 Count Total Records in debt_data",
    "Q03 (Basic) \u2014 List All Countries with Region",
    "Q04 (Basic) \u2014 List All Indicators with Topic",
    "Q05 (Basic) \u2014 All Debt Records for India (IND)",
    "Q06 (Basic) \u2014 All Records for Year 2020",
    "Q07 (Basic) \u2014 Records Where debt_value Exceeds 1 Billion",
    "Q08 (Basic) \u2014 Count Records per Country",
    "Q09 (Basic) \u2014 Top 10 Highest Single debt_value Records",
    "Q10 (Basic) \u2014 All Countries in South Asia Region",
    "Q11 (Intermediate) \u2014 Total Debt per Country (Top 15)",
    "Q12 (Intermediate) \u2014 Total Global Debt per Year",
    "Q13 (Intermediate) \u2014 Average and Total Debt by Income Group",
    "Q14 (Intermediate) \u2014 Total Debt by Region",
    "Q15 (Intermediate) \u2014 Countries with Total Debt Above Overall Average",
    "Q16 (Intermediate) \u2014 Top 10 Indicators by Total Debt Value",
    "Q17 (Intermediate) \u2014 Total Debt by Lending Category",
    "Q18 (Intermediate) \u2014 Year-wise Debt Trend for China (CHN)",
    "Q19 (Intermediate) \u2014 Count of Unique Indicators Used per Country",
    "Q20 (Intermediate) \u2014 Countries with Negative debt_value (Net Outflows)",
    "Q21 (Advanced) \u2014 Rank Countries by Total Debt Using RANK()",
    "Q22 (Advanced) \u2014 Running Cumulative Global Debt by Year Using SUM() OVER",
    "Q23 (Advanced) \u2014 Year-over-Year Global Debt Growth Using LAG()",
    "Q24 (Advanced) \u2014 Countries Contributing More Than 5% of Global Debt",
    "Q25 (Advanced) \u2014 Rank Countries Within Each Region Using PARTITION BY",
    "Q26 (Advanced) \u2014 3-Year Moving Average of Global Debt",
    "Q27 (Advanced) \u2014 Year with Highest Single-Year Debt Growth Rate",
    "Q28 (Advanced) \u2014 Countries with Above-Average Debt in Their Income Group",
    "Q29 (Advanced) \u2014 Debt Percentile Rank per Country Using PERCENT_RANK()",
    "Q30 (Advanced) \u2014 Total Debt by Income Group per Year (Last 5 Years)"
]

# ── Session state init ────────────────────────────────────────────────────────
if "sql_edit_mode"   not in st.session_state: st.session_state.sql_edit_mode   = {}
if "sql_locked_text" not in st.session_state: st.session_state.sql_locked_text = {}
if "sql_results"     not in st.session_state: st.session_state.sql_results     = {}
if "sql_error"       not in st.session_state: st.session_state.sql_error       = {}

# ── Dropdown ──────────────────────────────────────────────────────────────────
selected_label = st.selectbox(
    "Select a Query",
    options=DROPDOWN_OPTIONS,
    index=0,
    help="Choose any of the 30 SQL queries. Q01-Q10 Basic | Q11-Q20 Intermediate | Q21-Q30 Advanced"
)

# Parse selected query key
q_num = int(selected_label.split('(')[0].replace('Q','').strip())
q_key = f"Q{q_num:02d}"

# Category badge
if q_num <= 10:
    badge = '<span class="badge-basic">🟦 Basic</span>'
elif q_num <= 20:
    badge = '<span class="badge-inter">🟧 Intermediate</span>'
else:
    badge = '<span class="badge-adv">🟥 Advanced</span>'

q_title = selected_label.split('— ')[1] if '— ' in selected_label else selected_label
st.markdown(f'**Query {q_num:02d} — {q_title}** &nbsp; {badge}', unsafe_allow_html=True)

# ── Get current SQL (use locked version if edited, else default) ──────────────
current_sql = st.session_state.sql_locked_text.get(q_key, SQL_QUERIES[q_key])
is_edit_mode = st.session_state.sql_edit_mode.get(q_key, False)

# ── SQL Display — edit mode = text area, lock mode = code block ───────────────
if is_edit_mode:
    edited_sql = st.text_area(
        "✏️ Edit SQL Query — click 🔒 Lock to save",
        value=current_sql,
        height=200,
        key=f"sql_textarea_{q_key}",
        help="Edit the SQL query. Click Lock to save your changes."
    )
else:
    st.markdown(f'<div class="sql-box">{current_sql}</div>', unsafe_allow_html=True)
    edited_sql = current_sql

# ── Action Buttons ────────────────────────────────────────────────────────────
b1, b2, b3, b4 = st.columns([1, 1, 1, 5])

with b1:
    run_clicked = st.button("▶ Run", key=f"run_{q_key}",
                            help="Execute this query against MySQL", type="primary")
with b2:
    if is_edit_mode:
        edit_clicked = st.button("📄 View", key=f"edit_{q_key}",
                                 help="Switch back to view mode without saving")
    else:
        edit_clicked = st.button("✏️ Edit", key=f"edit_{q_key}",
                                 help="Edit this SQL query")
with b3:
    if is_edit_mode:
        lock_clicked = st.button("🔒 Lock", key=f"lock_{q_key}",
                                 help="Save edits and lock query", type="secondary")
    else:
        lock_clicked = st.button("🔓 Unlock", key=f"unlock_{q_key}",
                                 help="Unlock to enable editing")

# ── Button logic ──────────────────────────────────────────────────────────────
if run_clicked:
    sql_to_run = edited_sql if is_edit_mode else current_sql
    conn, err = get_mysql_conn()
    if err:
        st.session_state.sql_error[q_key]   = f"MySQL connection failed: {err}"
        st.session_state.sql_results[q_key] = None
    else:
        try:
            result_df = pd.read_sql(sql_to_run, conn)
            st.session_state.sql_results[q_key] = result_df
            st.session_state.sql_error[q_key]   = None
            conn.close()
        except Exception as e:
            st.session_state.sql_error[q_key]   = f"Query error: {e}"
            st.session_state.sql_results[q_key] = None

if edit_clicked:
    if is_edit_mode:
        # View mode — discard unsaved edits
        st.session_state.sql_edit_mode[q_key] = False
    else:
        # Enter edit mode
        st.session_state.sql_edit_mode[q_key] = True
    st.rerun()

if lock_clicked:
    if is_edit_mode:
        # Save the edited SQL and lock
        st.session_state.sql_locked_text[q_key] = edited_sql
        st.session_state.sql_edit_mode[q_key]   = False
        st.success(f"Query {q_key} locked with your edits.")
    else:
        # Unlock — go to edit mode
        st.session_state.sql_edit_mode[q_key] = True
    st.rerun()

# ── Show results or error ─────────────────────────────────────────────────────
if st.session_state.sql_error.get(q_key):
    st.error(st.session_state.sql_error[q_key])

if st.session_state.sql_results.get(q_key) is not None:
    result_df = st.session_state.sql_results[q_key]
    st.markdown(f"**Result — Query {q_num:02d}: {q_title}**")
    st.markdown(f"Rows returned : **{len(result_df):,}**")
    st.dataframe(result_df, use_container_width=True, height=min(400, 80 + len(result_df)*35))



# FOOTER

st.markdown("---")
st.markdown(
    "**International Debt Analysis Dashboard** · "
    "\nMain Data Source: [World Bank IDS](https://databank.worldbank.org/source/international-debt-statistics) · "
)
