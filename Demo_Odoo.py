import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
from io import BytesIO
from datetime import datetime, timedelta
import urllib.parse
import base64
from fpdf import FPDF
from utils_data import upload_odoo_data_to_postgres
from sqlalchemy import create_engine

# --- 1. CONFIGURACIÓN DE SEGURIDAD Y PÁGINA ---
st.set_page_config(
    page_title="NEXUS PRO IA", 
    layout="wide", 
    page_icon="💎",
    initial_sidebar_state="expanded",
    menu_items={
        'Get Help': None,
        'Report a bug': None,
        'About': None
    }
)

# --- 2. ESTILOS CSS BLINDADOS (VISUALIZACIÓN PRO) ---
st.markdown("""
<style>
    /* BLOQUEO VISUAL TOTAL DE MENÚS STREAMLIT */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* ESTILOS DE LA INTERFAZ PRO */
    .metric-card {
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
        border-radius: 15px; 
        padding: 20px; 
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        text-align: center;
        border-left: 5px solid #2E86C1;
        margin-bottom: 10px;
    }
    div[data-testid="stMetricValue"] {
        font-size: 24px;
        color: #1B4F72;
    }
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] {
        height: 60px;
        white-space: pre-wrap;
        background-color: #F8F9F9;
        border-radius: 10px 10px 0 0;
        font-weight: 600;
        border: 1px solid #ddd;
    }
    .stTabs [aria-selected="true"] {
        background-color: #2E86C1;
        color: white;
    }
</style>
""", unsafe_allow_html=True)

# --- 3. MÓDULO DE CONEXIÓN Y DATOS ---

# Intentamos importar el cliente Odoo.
try:
    from odoo_client import OdooConnector
    # Si la importación funciona, asumimos que podemos intentar conectar
    CONNECTION_ACTIVE = True
except ImportError:
    CONNECTION_ACTIVE = False

def generate_mock_data():
    """Genera datos simulados matemáticamente realistas para demostración."""
    np.random.seed(42)
    categories = ['Alta Tecnología', 'Accesorios', 'Hogar Smart', 'Legacy/Obsoletos']
    products = []
    
    for i in range(150):
        cat = np.random.choice(categories)
        base_price = np.random.randint(20, 1500)
        cost = base_price * 0.55 # Margen aprox 45%
        
        # Simulación de escenarios de negocio
        if cat == 'Alta Tecnología':
            qty = np.random.randint(0, 40) # Stock bajo
            sold = np.random.randint(40, 300) # Venta alta
        elif cat == 'Legacy/Obsoletos':
            qty = np.random.randint(100, 600) # Stock altísimo
            sold = np.random.randint(0, 5) # Venta nula
        else:
            qty = np.random.randint(10, 100)
            sold = np.random.randint(10, 150)
            
        products.append({
            'product_name': f"SKU-{i:03d} | {cat} - Item {i}",
            'category': cat,
            'quantity': qty,
            'value': qty * cost,
            'qty_sold': sold,
            'revenue': sold * base_price,
            'cost_unit': cost
        })
    
    return pd.DataFrame(products)

@st.cache_data(ttl=600)
def get_master_data():
    """
    Función MAESTRA de obtención de datos.
    Integra Odoo y maneja la fusión (Merge).
    """
    if CONNECTION_ACTIVE:
        try:
            # Instanciamos la clase que creamos en odoo_client.py
            connector = OdooConnector()
            
            # 1. Traer datos crudos
            df_stock = connector.get_stock_data()
            df_product = connector.get_product_data()
            df_sales = connector.get_sales_data()
            df_location = connector.get_location_data()
            df_moves = connector.get_stock_move_data()
            df_clients = connector.get_partner_data()
            df_purchases = connector.get_purchase_order_line_data()

            # Verificación de datos vacíos
            if df_stock.empty and df_sales.empty:
                return generate_mock_data(), False

            # 2. Agrupación segura
            stock_gb = df_stock.groupby('product_name').agg({
                'quantity': 'sum', 
                'value': 'sum'
            }).reset_index()

            sales_gb = df_sales.groupby('product_name').agg({
                'qty_sold': 'sum', 
                'revenue': 'sum'
            }).reset_index()

            # 3. MERGE (Fusión) OUTER JOIN
            df_final = pd.merge(stock_gb, sales_gb, on='product_name', how='outer').fillna(0)
            
            # 4. Enriquecimiento de datos
            df_final['category'] = 'General' # En una versión futura podríamos traer la categoría real de Odoo
            
            # Calculo de costo unitario promedio
            df_final['cost_unit'] = np.where(df_final['quantity'] > 0, 
                                            df_final['value'] / df_final['quantity'], 
                                            0)
            
            return df_final, True

        except Exception as e:
            st.error(f"❌ Error de conexión crítico con Odoo: {e}")
            st.stop()
    else:
        return generate_mock_data(), False

# --- 4. MOTOR DE INTELIGENCIA DE NEGOCIOS (BI ENGINE) ---

def process_business_logic(df_stock, df_sales, df_product, df_location, df_moves, df_clients, df_purchases, days_analyzed):
    # Merge stock y producto
    df_stock = df_stock.merge(df_product, left_on='product_id', right_on='id', suffixes=('_stock', '_prod'))
    # Merge ventas y producto
    df_sales = df_sales.merge(df_product, left_on='product_id', right_on='id', suffixes=('_sale', '_prod'))
    # KPIs por producto
    kpi = df_sales.groupby('product_name').agg({
        'qty_sold': 'sum',
        'revenue': 'sum'
    }).reset_index()
    stock_kpi = df_stock.groupby('product_name').agg({
        'quantity': 'sum',
        'value': 'sum'
    }).reset_index()
    df_final = pd.merge(kpi, stock_kpi, on='product_name', how='outer').fillna(0)
    # Calcula rotación, cobertura, etc.
    df_final['rotacion'] = df_final['qty_sold'] / df_final['quantity'].replace(0, np.nan)
    # ...más cálculos...
    return df_final

# --- 5. CLASE GENERADOR PDF ---
class PDFReport(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 15)
        self.set_text_color(44, 62, 80)
        self.cell(0, 10, 'NEXUS PRO IA - INFORME GERENCIAL', 0, 1, 'C')
        self.set_font('Arial', 'I', 10)
        self.cell(0, 10, f'Generado: {datetime.now().strftime("%d/%m/%Y %H:%M")}', 0, 1, 'C')
        self.ln(10)
        self.line(10, 30, 200, 30)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.set_text_color(128)
        self.cell(0, 10, f'NEXUS PRO IA System - Pagina {self.page_no()}', 0, 0, 'C')

def create_pdf(df):
    pdf = PDFReport()
    pdf.add_page()
    
    # Métricas
    total_ventas = df['Ventas_Totales'].sum()
    capital_atrapado = df[df['Diagnostico_IA'].str.contains("LIQUIDAR")]['Capital_Invertido'].sum()
    quiebres = len(df[df['Diagnostico_IA'].str.contains("URGENTE")])
    
    # Cuerpo
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, '1. RESUMEN EJECUTIVO', 0, 1)
    pdf.set_font('Arial', '', 11)
    pdf.cell(0, 8, f"Ventas Totales del Periodo: ${total_ventas:,.2f}", 0, 1)
    pdf.set_text_color(192, 57, 43) # Rojo
    pdf.cell(0, 8, f"Capital Atrapado (Huesos): ${capital_atrapado:,.2f}", 0, 1)
    pdf.cell(0, 8, f"Referencias en Quiebre (Perdida Venta): {quiebres} items", 0, 1)
    pdf.set_text_color(0)
    
    pdf.ln(10)
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, '2. ACCIONES RECOMENDADAS', 0, 1)
    
    # Tabla simple
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(100, 10, 'Producto', 1)
    pdf.cell(40, 10, 'Accion', 1)
    pdf.cell(40, 10, 'Impacto ($)', 1)
    pdf.ln()
    
    pdf.set_font('Arial', '', 9)
    # Top 10 Acciones
    top_acciones = df[df['Diagnostico_IA'] != "✅ SALUDABLE"].sort_values('Ventas_Totales', ascending=False).head(15)
    
    for _, row in top_acciones.iterrows():
        name = (row['product_name'][:45] + '..') if len(row['product_name']) > 45 else row['product_name']
        action = "COMPRAR" if "URGENTE" in row['Diagnostico_IA'] else "LIQUIDAR"
        val = row['Ventas_Totales'] if action == "COMPRAR" else row['Capital_Invertido']
        
        pdf.cell(100, 8, name, 1)
        pdf.cell(40, 8, action, 1)
        pdf.cell(40, 8, f"${val:,.0f}", 1)
        pdf.ln()
        
    return pdf.output(dest='S').encode('latin-1')

# --- 6. INTERFAZ PRINCIPAL (SIDEBAR) ---

with st.sidebar:
    # URL de ícono genérico profesional
    st.image("https://cdn-icons-png.flaticon.com/512/882/882706.png", width=60)
    
    st.markdown("## 💎 NEXUS PRO IA")
    st.markdown("---")
    
    st.subheader("⚙️ Configuración")
    
    dias_analisis = st.slider("Ventana de Tiempo (Días)", 30, 365, 90)
    st.info(f"Analizando rotación basada en los últimos {dias_analisis} días.")
    
    st.markdown("---")
    admin_phone = st.text_input("📱 WhatsApp Gerencial", "573001234567")
    
    # Estado de Conexión
    if CONNECTION_ACTIVE:
        st.success("🟢 Conectado a Odoo ERP")
    else:
        st.warning("⚠️ Modo DEMO (Datos Simulados)")

st.sidebar.markdown("---")
if st.sidebar.button("🔄 Cargar y Actualizar Datos desde Odoo"):
    with st.spinner("Cargando y actualizando datos desde Odoo..."):
        # Construye la URL de conexión igual que en utils_data.py
        import os
        pg_url = (
            f"postgresql://{os.getenv('PG_USER')}:{os.getenv('PG_PASSWORD')}"
            f"@{os.getenv('PG_HOST')}:{os.getenv('PG_PORT')}/{os.getenv('PG_DB')}"
        )
        upload_odoo_data_to_postgres(pg_url)
        st.success("¡Datos actualizados correctamente desde Odoo!")

# --- 7. LÓGICA DE EJECUCIÓN UI ---

# Carga de datos
with st.spinner('🔄 Sincronizando con ERP y procesando algoritmos...'):
    raw_data, is_real = get_master_data()
    # Si detectamos que estamos usando datos reales, forzamos el indicador
    if is_real: 
        CONNECTION_ACTIVE = True
    
    df = process_business_logic(
        raw_data['stock'], raw_data['sales'], raw_data['product'],
        raw_data['location'], raw_data['moves'], raw_data['clients'],
        raw_data['purchases'], dias_analisis
    )

# KPIs
st.metric("Ingresos Totales", f"${df['Ventas_Totales'].sum():,.0f}")
st.metric("Capital Invertido", f"${df['Capital_Invertido'].sum():,.0f}")
st.metric("GMROI (Eficiencia)", f"{df['GMROI'].mean():.2f}x", delta="Retorno x $ Invertido")
st.metric("Salud de Inventario", f"{len(df[df['Diagnostico_IA'] == "✅ SALUDABLE"]) / len(df) * 100:.1f}%", delta="Referencias Sanas")

# Dashboard visual (sunburst, tablas, alertas, etc.)
