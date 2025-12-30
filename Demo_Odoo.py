import streamlit as st
import pandas as pd
import plotly.express as px
from odoo_client import OdooConnector

st.set_page_config(page_title="Dashboard IA Odoo", layout="wide")

st.title("🚀 Dashboard de Inteligencia de Negocios Odoo")
st.markdown("Monitor de Stock, Rotación y Predicción de Traslados")

# --- CONEXIÓN ---
@st.cache_resource
def get_connector():
    return OdooConnector()

# Barra lateral
st.sidebar.header("Panel de Control")
if st.sidebar.button("🔄 Recargar Datos"):
    st.cache_resource.clear()
    st.rerun()

# Conectar
odoo = get_connector()

# --- EXTRACCIÓN DE DATOS ---
with st.spinner('Extrayendo datos de Odoo...'):
    df_stock = odoo.get_stock_analysis()
    df_sales = odoo.get_sales_history()

# --- VERIFICACIÓN DE DATOS ---
if df_stock.empty or df_sales.empty:
    st.warning("No se encontraron suficientes datos de ventas o stock para generar los análisis.")
    st.stop()

# --- KPIs PRINCIPALES ---
col1, col2, col3, col4 = st.columns(4)
total_stock_u = df_stock['quantity'].sum()
total_sales_val = df_sales['price_subtotal'].sum()

col1.metric("📦 Stock Total (Unidades)", f"{total_stock_u:,.0f}")
col2.metric("💰 Ventas Analizadas", f"${total_sales_val:,.2f}")
col3.metric("🏭 Referencias con Stock", f"{df_stock['product_name'].nunique()}")
col4.metric("🛒 Referencias Vendidas", f"{df_sales['product_name'].nunique()}")

st.divider()

# --- ANÁLISIS 1: STOCK VS DEMANDA (ROTACIÓN) ---
st.subheader("📊 Análisis de Rotación y Demanda")

# Preparar datos: Agrupar ventas por producto
sales_by_product = df_sales.groupby('product_name')['product_uom_qty'].sum().reset_index()
sales_by_product.columns = ['product_name', 'total_sold']

# Agrupar stock por producto
stock_by_product = df_stock.groupby('product_name')['quantity'].sum().reset_index()
stock_by_product.columns = ['product_name', 'current_stock']

# Unir (Merge) ambas tablas
analysis_df = pd.merge(sales_by_product, stock_by_product, on='product_name', how='outer').fillna(0)

# Calcular métrica simple de rotación (Ventas / Stock Actual)
# Nota: Si stock es 0, la rotación tiende a infinito (riesgo de quiebre)
analysis_df['indice_rotacion'] = analysis_df.apply(
    lambda x: x['total_sold'] / x['current_stock'] if x['current_stock'] > 0 else 0, axis=1
)

# Filtro interactivo
filtro_top = st.slider("Mostrar Top productos:", 5, 50, 10)
top_rotacion = analysis_df.sort_values('total_sold', ascending=False).head(filtro_top)

# Gráfico combinado
fig_combo = px.bar(top_rotacion, x='product_name', y=['total_sold', 'current_stock'],
                   title="Comparativa: Lo que se vende vs. Lo que hay en bodega",
                   barmode='group', labels={'value': 'Cantidad', 'variable': 'Métrica'})
st.plotly_chart(fig_combo, use_container_width=True)

# --- ANÁLISIS 2: SUGERENCIA DE TRASLADOS (Lógica IA Simple) ---
st.subheader("🚚 Sugerencias de Reabastecimiento / Traslados")
st.markdown("Productos con **altas ventas** pero **poco stock** (Riesgo de Quiebre).")

# Umbral: Productos con más de 5 ventas pero menos de 10 en stock
# Esto puedes ajustarlo según la realidad de tu negocio
oportunidad_traslado = analysis_df[
    (analysis_df['total_sold'] > 5) & 
    (analysis_df['current_stock'] < 10)
].sort_values('total_sold', ascending=False)

if not oportunidad_traslado.empty:
    st.dataframe(
        oportunidad_traslado[['product_name', 'total_sold', 'current_stock']],
        column_config={
            "product_name": "Producto",
            "total_sold": st.column_config.NumberColumn("Demanda (Ventas)", format="%d"),
            "current_stock": st.column_config.NumberColumn("Stock Crítico", format="%d ⚠️"),
        },
        use_container_width=True,
        hide_index=True
    )
else:
    st.success("¡Todo parece estar bien! No se detectaron productos con riesgo de quiebre inmediato bajo los parámetros actuales.")

# --- TABLA CRUDA ---
with st.expander("📂 Ver Datos Consolidados (Excel Export)"):
    st.dataframe(analysis_df)
