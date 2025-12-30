import streamlit as st
import pandas as pd
import plotly.express as px
from odoo_client import OdooConnector

# Configuración de página
st.set_page_config(page_title="Dashboard Odoo AI", layout="wide")

st.title("📊 Dashboard de Análisis: Ventas y Stock Odoo")
st.markdown("Análisis de rotación, demanda y traslados.")

# --- BARRA LATERAL ---
st.sidebar.header("Conexión y Filtros")

# Inicializar conexión (Singleton simple)
@st.cache_resource
def get_connector():
    return OdooConnector()

try:
    odoo = get_connector()
    st.sidebar.success(f"✅ Conectado como: {st.secrets['odoo_connection']['username']}")
except Exception as e:
    st.sidebar.error("Error conectando.")
    st.stop()

# --- CARGA DE DATOS ---
with st.spinner('Consultando API de Odoo en tiempo real...'):
    df_sales = odoo.get_sales()
    df_stock = odoo.get_stock()

# --- MÉTRICAS PRINCIPALES ---
col1, col2, col3 = st.columns(3)

if not df_sales.empty:
    total_ventas = df_sales['product_uom_qty'].sum()
    ingresos_aprox = (df_sales['product_uom_qty'] * df_sales['price_unit']).sum()
    col1.metric("Unidades Vendidas (Muestra)", f"{total_ventas:,.0f}")
    col2.metric("Ingresos (Muestra)", f"${ingresos_aprox:,.2f}")
else:
    col1.warning("No se encontraron ventas")

if not df_stock.empty:
    total_stock = df_stock['quantity'].sum()
    col3.metric("Stock Total Físico", f"{total_stock:,.0f}")

st.divider()

# --- ANÁLISIS DE VENTAS Y DEMANDA ---
st.subheader("📈 Análisis de Demanda por Producto")

if not df_sales.empty:
    # Agrupar ventas por producto
    top_products = df_sales.groupby('product_name')['product_uom_qty'].sum().reset_index()
    top_products = top_products.sort_values('product_uom_qty', ascending=False).head(10)
    
    fig_bar = px.bar(top_products, x='product_name', y='product_uom_qty', 
                     title="Top 10 Productos Más Vendidos", text_auto=True)
    st.plotly_chart(fig_bar, use_container_width=True)

    # Tabla de datos crudos para análisis manual
    with st.expander("Ver detalle de últimas ventas"):
        st.dataframe(df_sales)

# --- ANÁLISIS DE STOCK ---
st.subheader("📦 Stock Actual vs Rotación")

if not df_stock.empty:
    col_stock1, col_stock2 = st.columns([2, 1])
    
    with col_stock1:
        # Gráfico de Stock
        fig_stock = px.treemap(df_stock, path=['product_name'], values='quantity',
                               title="Mapa de Stock (Tamaño = Cantidad)")
        st.plotly_chart(fig_stock, use_container_width=True)
    
    with col_stock2:
        st.markdown("**Alerta de Stock Bajo (IA Simple)**")
        # Lógica simple de IA/Análisis: Si stock < 5, alerta
        low_stock = df_stock[df_stock['quantity'] < 5]
        st.dataframe(low_stock[['product_name', 'quantity']], hide_index=True)
        
else:
    st.info("No hay datos de stock disponibles.")

# --- SECCIÓN IA (FUTURE PROOF) ---
st.divider()
st.subheader("🤖 Análisis Inteligente (Próximamente)")
st.info("Aquí conectaremos el modelo predictivo para sugerir traslados entre tiendas basado en la rotación histórica vs el stock actual.")

# Botón para forzar recarga (limpia caché)
if st.sidebar.button("Actualizar Datos"):
    st.cache_resource.clear()
    st.rerun()
