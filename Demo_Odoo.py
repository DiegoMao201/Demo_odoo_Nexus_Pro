import streamlit as st
import pandas as pd
import plotly.express as px
from odoo_client import OdooConnector

# Configuración visual
st.set_page_config(page_title="Dashboard IA Retail", layout="wide", page_icon="🚀")

# Encabezado
st.title("📊 Dashboard de Inteligencia Comercial")
st.markdown("Análisis automatizado de **Rotación**, **Inventario** y **Oportunidades**.")

# --- 1. CONEXIÓN Y CARGA DE DATOS ---
@st.cache_resource
def load_data():
    connector = OdooConnector()
    df_stock = connector.get_stock_clean()
    df_sales = connector.get_sales_clean()
    return df_stock, df_sales

with st.spinner('Conectando con Odoo y procesando datos...'):
    try:
        df_stock, df_sales = load_data()
    except Exception as e:
        st.error("Error de conexión. Revisa los logs.")
        st.stop()

if df_stock.empty and df_sales.empty:
    st.warning("Conexión exitosa, pero no se encontraron datos. ¿Estás seguro de que la base de datos tiene movimientos?")
    st.stop()

# --- 2. PROCESAMIENTO DE DATOS (CRUCE INTELIGENTE) ---

# A. Resumen de STOCK por Producto (Suma de todas las bodegas)
stock_groupped = df_stock.groupby('product_name').agg({
    'quantity': 'sum',
    'value': 'sum'
}).reset_index()

# B. Resumen de VENTAS por Producto
sales_groupped = df_sales.groupby('product_name').agg({
    'qty_sold': 'sum',
    'revenue': 'sum'
}).reset_index()

# C. JOIN (Unimos todo en una Tabla Maestra)
df_master = pd.merge(stock_groupped, sales_groupped, on='product_name', how='outer').fillna(0)

# D. Ingeniería de Características (KPIs calculados)
# Rotación: Cuántas veces vendo mi stock (Ventas / Stock)
# Nota: Sumamos 0.1 al stock para evitar división por cero
df_master['rotacion'] = df_master['qty_sold'] / (df_master['quantity'] + 0.1)

# Clasificación Simple
def clasificar_producto(row):
    if row['quantity'] <= 0: return "Sin Stock"
    if row['rotacion'] > 2: return "Estrella ⭐"    # Vende mucho, poco stock relativo
    if row['rotacion'] < 0.5: return "Lento 🐢"   # Mucho stock, vende poco
    return "Regular"

df_master['categoria_ia'] = df_master.apply(clasificar_producto, axis=1)

# --- 3. VISUALIZACIÓN ---

# Tarjetas KPI Superiores
col1, col2, col3, col4 = st.columns(4)
col1.metric("📦 Valor Inventario", f"${df_master['value'].sum():,.0f}")
col2.metric("💰 Ventas Totales", f"${df_master['revenue'].sum():,.0f}")
col3.metric("🐢 Productos Lentos", len(df_master[df_master['categoria_ia'] == "Lento 🐢"]))
col4.metric("⭐ Productos Estrella", len(df_master[df_master['categoria_ia'] == "Estrella ⭐"]))

st.divider()

# Gráfico Principal: Matriz de Rotación
st.subheader("🔎 Matriz de Análisis: Stock vs. Ventas")
st.info("Eje X = Cuánto tienes en bodega | Eje Y = Cuánto has vendido")

fig_scatter = px.scatter(
    df_master[df_master['quantity'] > 0], # Filtramos negativos para limpieza visual
    x="quantity", 
    y="qty_sold", 
    size="value",           # El tamaño de la burbuja es el valor en dinero
    color="categoria_ia",   # Color por nuestra clasificación IA
    hover_name="product_name",
    log_x=True, log_y=True, # Escala logarítmica para ver mejor los datos dispersos
    title="Mapa de Calor de Inventario",
    color_discrete_map={"Estrella ⭐": "#00CC96", "Lento 🐢": "#EF553B", "Regular": "#636EFA"}
)
st.plotly_chart(fig_scatter, use_container_width=True)

# --- 4. ACCIONES SUGERIDAS (TABLAS) ---

c1, c2 = st.columns(2)

with c1:
    st.subheader("🚨 Sugerencia de Reabastecimiento")
    st.caption("Productos que se venden bien pero tienen poco stock (Riesgo de Quiebre).")
    # Lógica: Stock bajo (<10) y Ventas altas (>5)
    reponer = df_master[(df_master['quantity'] < 10) & (df_master['qty_sold'] > 5)].sort_values('qty_sold', ascending=False)
    st.dataframe(reponer[['product_name', 'quantity', 'qty_sold']], hide_index=True)

with c2:
    st.subheader("💸 Sugerencia de Liquidación")
    st.caption("Productos con mucho dinero estancado y pocas ventas.")
    # Lógica: Stock alto y Rotación baja
    liquidar = df_master[(df_master['categoria_ia'] == "Lento 🐢") & (df_master['value'] > 0)].sort_values('value', ascending=False)
    st.dataframe(liquidar[['product_name', 'quantity', 'qty_sold', 'value']], hide_index=True)

# --- 5. DETALLE DE DATOS ---
with st.expander("📂 Ver Tabla Maestra Completa"):
    st.dataframe(df_master)
