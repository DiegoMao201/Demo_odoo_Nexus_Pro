import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from io import BytesIO
from datetime import datetime, timedelta
import urllib.parse
from odoo_client import OdooConnector

# --- CONFIGURACIÓN PRO ---
st.set_page_config(page_title="Nexus Logistics AI", layout="wide", page_icon="🏢")

# Estilos CSS para apariencia profesional
st.markdown("""
<style>
    .metric-card {background-color: #f0f2f6; border-radius: 10px; padding: 20px; text-align: center;}
    .stTabs [data-baseweb="tab-list"] {gap: 20px;}
    .stTabs [data-baseweb="tab"] {height: 50px; white-space: pre-wrap; background-color: #f0f2f6; border-radius: 5px;}
    .stTabs [aria-selected="true"] {background-color: #FF4B4B; color: white;}
</style>
""", unsafe_allow_html=True)

# --- 1. CARGA Y PROCESAMIENTO ---
@st.cache_data(ttl=300) # Caché de 5 minutos
def get_master_data():
    connector = OdooConnector()
    df_stock = connector.get_stock_data()
    df_sales = connector.get_sales_data()
    return df_stock, df_sales

# Sidebar: Filtros Globales
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3043/3043221.png", width=50)
    st.title("Nexus Control")
    st.divider()
    
    # Filtro de Fechas para Ventas
    date_range = st.date_input("Periodo de Análisis", [datetime.now() - timedelta(days=90), datetime.now()])
    
    st.info("💡 Usa el rango de fechas para analizar la rotación en temporadas específicas.")
    
    # Configuración WhatsApp
    st.divider()
    st.header("📲 Configuración WhatsApp")
    admin_phone = st.text_input("Celular del Gerente (con país)", "573001234567")

# Cargar Datos
try:
    with st.spinner('Conectando con el Núcleo de Odoo...'):
        stock_raw, sales_raw = get_master_data()
except Exception:
    st.error("Error crítico de conexión.")
    st.stop()

# --- 2. MOTOR DE CÁLCULO (BUSINESS INTELLIGENCE) ---

# Filtrar ventas por fecha seleccionada
if len(date_range) == 2:
    start_date, end_date = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])
    sales_filtered = sales_raw[(sales_raw['date'] >= start_date) & (sales_raw['date'] <= end_date)]
else:
    sales_filtered = sales_raw

# Agrupaciones
stock_gb = stock_raw.groupby('product_name').agg({'quantity': 'sum', 'value': 'sum'}).reset_index()
sales_gb = sales_filtered.groupby('product_name').agg({'qty_sold': 'sum', 'revenue': 'sum'}).reset_index()

# Master Merge
df = pd.merge(stock_gb, sales_gb, on='product_name', how='outer').fillna(0)

# Cálculos Avanzados
df['precio_prom'] = df['revenue'] / df['qty_sold'].replace(0, 1) # Precio promedio venta
df['rotacion'] = df['qty_sold'] / (df['quantity'] + 1) # Índice de rotación
days_analyzed = (end_date - start_date).days if len(date_range) == 2 else 90
df['ventas_diarias'] = df['qty_sold'] / days_analyzed
df['dias_cobertura'] = df['quantity'] / df['ventas_diarias'].replace(0, 0.001)

# Clasificación ABC (Pareto por Ingresos)
df = df.sort_values('revenue', ascending=False)
df['cum_revenue'] = df['revenue'].cumsum()
df['revenue_perc'] = df['cum_revenue'] / df['revenue'].sum()

def get_abc(perc):
    if perc <= 0.8: return 'A'
    elif perc <= 0.95: return 'B'
    else: return 'C'

df['clasificacion_abc'] = df['revenue_perc'].apply(get_abc)

# Clasificación IA de Acción
def get_action(row):
    if row['quantity'] <= 0 and row['qty_sold'] > 0: return "🚨 QUIEBRE (Comprar YA)"
    if row['dias_cobertura'] < 15 and row['clasificacion_abc'] == 'A': return "⚠️ REABASTECER (Riesgo A)"
    if row['dias_cobertura'] > 180 and row['quantity'] > 10: return "🐢 LIQUIDAR (Exceso)"
    return "✅ OK"

df['accion_ia'] = df.apply(get_action, axis=1)

# --- 3. INTERFAZ VISUAL ---

st.title("Tablero de Mando Integral")

# PESTAÑAS PRINCIPALES
tab1, tab2, tab3, tab4 = st.tabs(["📊 Visión Gerencial", "📦 Análisis de Inventario", "🤖 Predicciones IA", "📤 Centro de Acción"])

# --- TAB 1: VISIÓN GERENCIAL ---
with tab1:
    # KPIs Financieros
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Valor Inventario (Costo)", f"${df['value'].sum():,.0f}", delta="Activo Corriente")
    c2.metric("Ventas del Periodo", f"${df['revenue'].sum():,.0f}", delta=f"{days_analyzed} días")
    c3.metric("Referencias Activas", f"{len(df[df['quantity']>0])}", delta="SKUs")
    c4.metric("Precisión Inventario", f"{100 - (len(df[df['quantity']<0])/len(df)*100):.1f}%")

    st.divider()
    
    # Gráfico Pareto ABC
    col_chart, col_data = st.columns([2, 1])
    with col_chart:
        st.subheader("Análisis Pareto (80/20)")
        fig_abc = px.bar(
            df.groupby('clasificacion_abc')['revenue'].sum().reset_index(),
            x='clasificacion_abc', y='revenue', color='clasificacion_abc',
            title="Ingresos por Clasificación ABC",
            color_discrete_map={'A': '#2ecc71', 'B': '#f1c40f', 'C': '#e74c3c'}
        )
        st.plotly_chart(fig_abc, use_container_width=True)
    
    with col_data:
        st.subheader("Resumen Ejecutivo")
        st.markdown("""
        * **Clase A:** Productos vitales. Generan el 80% del dinero. No pueden faltar.
        * **Clase B:** Importancia media.
        * **Clase C:** La mayoría de productos, pero generan poco dinero. Ojo con el sobre-stock aquí.
        """)
        st.dataframe(df['clasificacion_abc'].value_counts(), use_container_width=True)

# --- TAB 2: ANÁLISIS DE INVENTARIO ---
with tab2:
    st.subheader("Mapa de Calor: Stock vs Rotación")
    
    fig_scatter = px.scatter(
        df[df['quantity'] > 0],
        x="dias_cobertura", y="revenue",
        size="quantity", color="clasificacion_abc",
        hover_name="product_name",
        log_x=True, # Escala logarítmica para ver mejor
        title="Cobertura en Días vs Importancia (Dinero)",
        labels={"dias_cobertura": "Días que dura el stock", "revenue": "Dinero que genera"},
        color_discrete_map={'A': '#2ecc71', 'B': '#f1c40f', 'C': '#e74c3c'}
    )
    # Lineas de referencia
    fig_scatter.add_vline(x=30, line_dash="dash", line_color="green", annotation_text="Ideal (30 días)")
    fig_scatter.add_vline(x=180, line_dash="dash", line_color="red", annotation_text="Exceso (>6 meses)")
    
    st.plotly_chart(fig_scatter, use_container_width=True)

# --- TAB 3: PREDICCIONES IA ---
with tab3:
    col_alert, col_action = st.columns([3, 1])
    
    with col_alert:
        st.subheader("🚨 Radar de Problemas")
        filtro_accion = st.selectbox("Filtrar por tipo de problema:", 
                                     ["Todos", "🚨 QUIEBRE (Comprar YA)", "⚠️ REABASTECER (Riesgo A)", "🐢 LIQUIDAR (Exceso)"])
        
        if filtro_accion != "Todos":
            df_view = df[df['accion_ia'] == filtro_accion]
        else:
            df_view = df[df['accion_ia'] != "✅ OK"]
            
        st.dataframe(
            df_view[['product_name', 'quantity', 'qty_sold', 'dias_cobertura', 'clasificacion_abc', 'accion_ia']],
            use_container_width=True,
            column_config={
                "dias_cobertura": st.column_config.NumberColumn("Días Stock", format="%.1f d"),
                "accion_ia": "Diagnóstico IA"
            }
        )

# --- TAB 4: CENTRO DE ACCIÓN (WHATSAPP + EXCEL) ---
with tab4:
    st.header("⚡ Centro de Comandos")
    st.markdown("Toma decisiones inmediatas con estas herramientas.")
    
    c_excel, c_wpp = st.columns(2)
    
    # 1. GENERADOR DE EXCEL PROFESIONAL
    with c_excel:
        st.subheader("📥 Reporte Corporativo")
        
        # Función para generar Excel en memoria
        def to_excel(df):
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                # Hoja 1: Resumen General
                df.to_excel(writer, index=False, sheet_name='Maestro')
                
                # Hoja 2: A Comprar
                compras = df[df['accion_ia'].str.contains("QUIEBRE|REABASTECER")]
                compras.to_excel(writer, index=False, sheet_name='Para_Compras')
                
                # Hoja 3: A Liquidar
                liquidar = df[df['accion_ia'].str.contains("LIQUIDAR")]
                liquidar.to_excel(writer, index=False, sheet_name='Para_Liquidar')
                
                # Formato
                workbook = writer.book
                worksheet = writer.sheets['Maestro']
                format1 = workbook.add_format({'num_format': '#,##0.00'})
                worksheet.set_column('B:F', 18, format1)
                
            return output.getvalue()

        excel_data = to_excel(df)
        st.download_button(
            label="📄 Descargar Informe Completo (.xlsx)",
            data=excel_data,
            file_name=f'Reporte_Odoo_Nexus_{datetime.now().strftime("%Y%m%d")}.xlsx',
            mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            help="Incluye 3 pestañas: Maestro, Sugerencias de Compra y Sugerencias de Liquidación."
        )

    # 2. BOT API WHATSAPP
    with c_wpp:
        st.subheader("📲 Notificar a Gerencia")
        
        # Lógica para construir el mensaje
        n_quiebres = len(df[df['accion_ia'].str.contains("QUIEBRE")])
        n_exceso = len(df[df['accion_ia'].str.contains("LIQUIDAR")])
        top_sku = df.iloc[0]['product_name']
        total_val = df['value'].sum()
        
        mensaje = f"""
        *🤖 REPORTE AUTOMÁTICO NEXUS*
        -----------------------------
        📅 Fecha: {datetime.now().strftime('%d/%m/%Y')}
        
        *📊 Estado General:*
        - Valor Inventario: ${total_val:,.0f}
        - Producto Top Ventas: {top_sku}
        
        *🚨 ALERTAS:*
        - 🔴 Productos en Quiebre: {n_quiebres} (Urge Comprar)
        - 🐢 Productos en Exceso: {n_exceso} (Urge Liquidar)
        
        _Enviado desde Dashboard Odoo AI_
        """
        
        mensaje_encoded = urllib.parse.quote(mensaje)
        whatsapp_url = f"https://wa.me/{admin_phone}?text={mensaje_encoded}"
        
        st.markdown(f"""
            <a href="{whatsapp_url}" target="_blank">
                <button style="
                    background-color:#25D366; 
                    color:white; 
                    border:none; 
                    padding:15px 32px; 
                    text-align:center; 
                    text-decoration:none; 
                    display:inline-block; 
                    font-size:16px; 
                    border-radius:5px; 
                    cursor:pointer;
                    width: 100%;">
                    🚀 Enviar Reporte por WhatsApp
                </button>
            </a>
            """, unsafe_allow_html=True)
        st.info("Al dar clic, se abrirá WhatsApp Web con el reporte ya redactado.")

# Footer
st.markdown("---")
st.caption("Nexus Logistics AI System v2.0 | Conectado a Odoo Enterprise")
