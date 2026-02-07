import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np
from io import BytesIO
import time

from odoo_client import OdooConnector  # NUEVO: usar datos reales de Odoo

st.set_page_config(
    page_title="NEXUS PRO | Enterprise Command Center",
    layout="wide",
    page_icon="💎",
    initial_sidebar_state="collapsed"
)

# --- Estilos (se conservan) ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;800&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .stApp { background-color: #f1f5f9; }
    h1, h2, h3 { color: #0f172a; font-weight: 800; letter-spacing: -0.5px; }
    div[data-testid="metric-container"] {
        background-color: #ffffff; border: 1px solid #e2e8f0; padding: 15px 20px;
        border-radius: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); transition: all 0.2s ease;
    }
    div[data-testid="metric-container"]:hover { box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1); transform: translateY(-2px); border-color: #3b82f6; }
    div[data-testid="metric-container"] label { font-size: 0.8rem; text-transform: uppercase; color: #64748b; font-weight: 600; }
    div[data-testid="metric-container"] div[data-testid="stMetricValue"] { font-size: 1.8rem; color: #1e293b; font-weight: 800; }
    div[data-testid="stDataEditor"] { border-radius: 10px; overflow: hidden; border: 1px solid #e2e8f0; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); }
    .stButton > button { border-radius: 8px; font-weight: 600; border: none; transition: all 0.2s; }
    .stButton > button:hover { transform: scale(1.02); }
    .stTabs [data-baseweb="tab-list"] { gap: 10px; background-color: transparent; padding-bottom: 10px; }
    .stTabs [data-baseweb="tab"] {
        height: 45px; background-color: #ffffff; border-radius: 8px; font-weight: 600;
        color: #64748b; border: 1px solid #e2e8f0; padding: 0 20px;
    }
    .stTabs [aria-selected="true"] { background-color: #2563eb; color: #ffffff !important; border-color: #2563eb; }
    .block-container { padding-top: 2rem; padding-bottom: 2rem; }
</style>
""", unsafe_allow_html=True)

def format_currency(value):
    return f"$ {value:,.2f}"

def format_number(value):
    return f"{value:,.0f}"

# --- Motor de negocio con datos reales Odoo ---
def process_business_logic(df_stock, df_sales, df_product, df_location, dias_analisis):
    # Mapas auxiliares
    prod_name_map = dict(zip(df_product['id'], df_product['name']))
    prod_cost_map = dict(zip(df_product['id'], df_product['standard_price']))
    loc_name_map = dict(zip(df_location['id'], df_location['name']))

    # Enriquecer Stock
    df_stock = df_stock.copy()
    df_stock['product_name'] = df_stock['product_id'].map(prod_name_map)
    df_stock['location_name'] = df_stock['location_id'].map(loc_name_map)
    df_stock['cost_unit'] = df_stock['product_id'].map(prod_cost_map).fillna(0)
    df_stock['capital_inmovilizado'] = df_stock['quantity'] * df_stock['cost_unit']

    # Enriquecer Ventas
    df_sales = df_sales.copy()
    df_sales['product_name'] = df_sales['product_id'].map(prod_name_map)

    # Agregados
    stock_gb = df_stock.groupby(['product_id', 'product_name'], as_index=False).agg({
        'quantity': 'sum',
        'capital_inmovilizado': 'sum',
        'cost_unit': 'mean'
    })
    ventas_gb = df_sales.groupby(['product_id', 'product_name'], as_index=False).agg({
        'qty_sold': 'sum',
        'revenue': 'sum'
    })

    # Merge KPI
    df_final = pd.merge(stock_gb, ventas_gb, on=['product_id', 'product_name'], how='outer').fillna(0)
    df_final['rotacion'] = df_final['qty_sold'] / dias_analisis
    df_final['cobertura_dias'] = df_final['quantity'] / df_final['rotacion'].replace(0, np.nan)
    df_final['cobertura_dias'] = df_final['cobertura_dias'].replace([np.inf, -np.inf], 0).fillna(0)

    def diagnostico(row):
        if row['quantity'] == 0 and row['qty_sold'] > 0:
            return "URGENTE COMPRAR"
        elif row['cobertura_dias'] > 180:
            return "LIQUIDAR"
        elif row['rotacion'] > 0 and row['cobertura_dias'] < 15:
            return "REVISAR STOCK"
        else:
            return "SALUDABLE"
    df_final['diagnostico'] = df_final.apply(diagnostico, axis=1)

    # Traslados sugeridos (simple)
    traslados = []
    for prod in df_final['product_id'].unique():
        prod_data = df_final[df_final['product_id'] == prod]
        exceso = prod_data[prod_data['cobertura_dias'] > 90]
        quiebre = prod_data[prod_data['cobertura_dias'] < 10]
        for _, row_exceso in exceso.iterrows():
            for _, row_quiebre in quiebre.iterrows():
                traslados.append({
                    'producto': row_exceso['product_name'],
                    'de': row_exceso.get('location_name', ''),
                    'a': row_quiebre.get('location_name', ''),
                    'cantidad_sugerida': max(min(row_exceso['quantity'] - 10, 10), 0)
                })
    df_traslados = pd.DataFrame(traslados)

    # Compras sugeridas
    compras = df_final[(df_final['diagnostico'] == "URGENTE COMPRAR")][
        ['product_name', 'quantity', 'qty_sold', 'cost_unit']
    ].copy()
    compras['cantidad_sugerida'] = (compras['qty_sold'] / dias_analisis * 30 - compras['quantity']).clip(lower=0)

    capital_inmovilizado = df_final['capital_inmovilizado'].sum()

    return {
        'kpi': df_final,
        'traslados': df_traslados,
        'compras': compras,
        'capital_inmovilizado': capital_inmovilizado
    }

def main():
    st.markdown(f"## 🚀 Tablero de Comando Odoo | {pd.to_datetime('today').strftime('%Y-%m-%d')}")
    with st.sidebar:
        st.title("NEXUS PRO v2.0 (Odoo)")
        st.markdown("---")
        dias_analisis = st.slider("📅 Ventana Histórica (Días)", 30, 365, 90)
        st.markdown("---")
        st.info("Datos en vivo desde Odoo")

    # Conexión y carga de datos reales
    connector = OdooConnector()
    df_stock = connector.get_stock_data()
    df_sales = connector.get_sales_data()
    df_product = connector.get_product_data()
    df_location = connector.get_location_data()

    if df_stock.empty and df_sales.empty:
        st.error("No se encontraron datos en Odoo para stock o ventas.")
        return

    bi = process_business_logic(df_stock, df_sales, df_product, df_location, dias_analisis)
    df_final = bi['kpi']

    # KPIs
    k1, k2, k3, k4, k5 = st.columns(5)
    with k1: st.metric("Capital Inmovilizado", format_currency(bi['capital_inmovilizado']))
    with k2: st.metric("Productos con Stock", format_number(df_final[df_final['quantity'] > 0]['product_id'].nunique()))
    with k3: st.metric("Productos Vendidos", format_number(df_final[df_final['qty_sold'] > 0]['product_id'].nunique()))
    with k4: st.metric("Rotación Prom (u/día)", f"{df_final['rotacion'].mean():.2f}")
    with k5: st.metric("Cobertura Prom (días)", f"{df_final['cobertura_dias'].mean():.1f}")

    st.markdown("---")
    tab_kpi, tab_traslados, tab_compras, tab_raw = st.tabs([
        "📊 KPIs & Visuales",
        "🚚 Traslados sugeridos",
        "🛒 Compras sugeridas",
        "🔎 Datos crudos"
    ])

    with tab_kpi:
        col1, col2 = st.columns([2,1])
        with col1:
            st.markdown("### 📈 Cobertura vs Rotación")
            fig_scatter = px.scatter(
                df_final,
                x="cobertura_dias",
                y="rotacion",
                size="quantity",
                color="diagnostico",
                hover_name="product_name",
                height=420
            )
            st.plotly_chart(fig_scatter, use_container_width=True)
        with col2:
            st.markdown("### 🥧 Distribución por diagnóstico")
            fig_pie = px.pie(
                df_final,
                names='diagnostico',
                values='capital_inmovilizado',
                hole=0.4
            )
            st.plotly_chart(fig_pie, use_container_width=True)

        st.markdown("### 🔎 Tabla KPI por producto")
        st.dataframe(
            df_final[['product_id','product_name','quantity','capital_inmovilizado','cost_unit','qty_sold','revenue','rotacion','cobertura_dias','diagnostico']],
            use_container_width=True, height=500
        )

    with tab_traslados:
        st.markdown("### 🔄 Traslados sugeridos")
        st.dataframe(bi['traslados'], use_container_width=True, height=400)

    with tab_compras:
        st.markdown("### 🛒 Compras sugeridas")
        st.dataframe(
            bi['compras'][['product_name','qty_sold','quantity','cost_unit','cantidad_sugerida']],
            use_container_width=True, height=400
        )

    with tab_raw:
        st.markdown("### 📦 Stock (raw)")
        st.dataframe(df_stock.head(50), use_container_width=True)
        st.markdown("### 🛒 Ventas (raw)")
        st.dataframe(df_sales.head(50), use_container_width=True)
        st.markdown("### 🧾 Productos (raw)")
        st.dataframe(df_product.head(50), use_container_width=True)
        st.markdown("### 🏬 Ubicaciones (raw)")
        st.dataframe(df_location.head(50), use_container_width=True)

if __name__ == "__main__":
    main()