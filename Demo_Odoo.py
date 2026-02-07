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
            connector = OdooConnector()

            raw_data = {
                'stock'     : connector.get_stock_data(),
                'product'   : connector.get_product_data(),
                'sales'     : connector.get_sales_data(),
                'location'  : connector.get_location_data(),
                'moves'     : connector.get_stock_move_data(),
                'clients'   : connector.get_partner_data(),
                'purchases' : connector.get_purchase_order_line_data(),
            }

            # Si todo viene vacío, usar mock
            if all(df.empty for df in raw_data.values()):
                return {'mock': generate_mock_data()}, False
            return raw_data, True

        except Exception as e:
            st.error(f"❌ Error de conexión crítico con Odoo: {e}")
            st.stop()
    else:
        return {'mock': generate_mock_data()}, False

# --- 4. MOTOR DE INTELIGENCIA DE NEGOCIOS (BI ENGINE) ---

def process_business_logic(
    df_stock, df_sales, df_product, df_location, df_moves, df_clients, df_purchases, dias_analisis
):
    df_stock = df_stock.merge(df_product, left_on='product_id', right_on='id', suffixes=('_stock', '_prod'), how='left')
    df_stock = df_stock.merge(df_location, left_on='location_id', right_on='id', suffixes=('', '_loc'), how='left')
    df_stock['cost_unit'] = df_stock['standard_price']
    df_stock['capital_inmovilizado'] = df_stock['quantity'] * df_stock['cost_unit']

    df_sales = df_sales.merge(df_product, left_on='product_id', right_on='id', suffixes=('_sale', '_prod'), how='left')
    if 'warehouse_id' in df_sales.columns:
        df_sales['warehouse_id'] = df_sales['warehouse_id'].apply(lambda x: x[0] if isinstance(x, list) else x)
        df_sales['warehouse_name'] = df_sales['warehouse_id'].apply(lambda x: x[1] if isinstance(x, list) and len(x) > 1 else None)
    else:
        df_sales['warehouse_id'] = np.nan
        df_sales['warehouse_name'] = np.nan

    ventas_gb = df_sales.groupby(['product_id', 'product_name']).agg({'qty_sold': 'sum', 'revenue': 'sum'}).reset_index()
    stock_gb = df_stock.groupby(['product_id', 'product_name']).agg({'quantity': 'sum', 'capital_inmovilizado': 'sum', 'cost_unit': 'mean'}).reset_index()

    df_final = pd.merge(
        stock_gb,
        ventas_gb,
        on=['product_id', 'product_name'],
        how='outer'
    ).fillna(0)

    # --- 5. Cálculos de rotación y cobertura ---
    df_final['rotacion'] = df_final['qty_sold'] / dias_analisis
    df_final['cobertura_dias'] = df_final['quantity'] / df_final['rotacion'].replace(0, np.nan)
    df_final['cobertura_dias'] = df_final['cobertura_dias'].replace([np.inf, -np.inf], 0).fillna(0)

    # --- 6. Diagnóstico IA ---
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

    # --- 7. Sugerencias de traslado ---
    traslados = []
    for prod in df_final['product_id'].unique():
        prod_data = df_final[df_final['product_id'] == prod]
        exceso = prod_data[prod_data['cobertura_dias'] > 90]
        quiebre = prod_data[prod_data['cobertura_dias'] < 10]
        for _, row_exceso in exceso.iterrows():
            for _, row_quiebre in quiebre.iterrows():
                traslados.append({
                    'producto': row_exceso['product_name'],
                    'de': row_exceso.get('name', ''),
                    'a': row_quiebre.get('name', ''),
                    'cantidad_sugerida': min(row_exceso['quantity'] - 30, 30 - row_quiebre['quantity'])
                })
    df_traslados = pd.DataFrame(traslados)

    # --- 8. Sugerencias de compra ---
    compras = df_final[(df_final['diagnostico'] == "URGENTE COMPRAR")][
        ['product_name', 'quantity', 'qty_sold', 'cost_unit']
    ]
    compras['cantidad_sugerida'] = (compras['qty_sold'] / dias_analisis * 30 - compras['quantity']).clip(lower=0)

    # --- 9. Capital inmovilizado total ---
    capital_inmovilizado = df_final['capital_inmovilizado'].sum()

    # --- 10. Devuelve todo lo necesario para el dashboard ---
    return {
        'kpi': df_final,
        'traslados': df_traslados,
        'compras': compras,
        'capital_inmovilizado': capital_inmovilizado
    }

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
raw_data, is_real = get_master_data()
if not is_real and 'mock' in raw_data:
    df_mock = raw_data['mock']
    st.warning("Modo DEMO: usando datos simulados.")
    st.dataframe(df_mock.head())
else:
    df_stock = raw_data['stock']
    df_sales = raw_data['sales']
    df_product = raw_data['product']
    df_location = raw_data['location']
    df_moves = raw_data['moves']
    df_clients = raw_data['clients']
    df_purchases = raw_data['purchases']

    st.header("📦 Stock")
    st.dataframe(df_stock.head(20))
    st.header("🛒 Ventas")
    st.dataframe(df_sales.head(20))
    st.header("🧾 Productos")
    st.dataframe(df_product.head(20))
    st.header("🏬 Ubicaciones")
    st.dataframe(df_location.head(20))
    st.header("🚚 Movimientos de Stock")
    st.dataframe(df_moves.head(20))
    st.header("👤 Clientes")
    st.dataframe(df_clients.head(20))
    st.header("💼 Compras")
    st.dataframe(df_purchases.head(20))

    # Ahora tu BI Engine puede operar con estos DataFrames
    bi = process_business_logic(
        df_stock, df_sales, df_product,
        df_location, df_moves, df_clients,
        df_purchases, dias_analisis
    )
    st.metric("Capital Inmovilizado", f"${bi['capital_inmovilizado']:,.0f}")
    st.dataframe(bi['kpi'].head(20))
    st.subheader("🚚 Traslados sugeridos entre tiendas")
    st.dataframe(bi['traslados'])
    st.subheader("🛒 Compras sugeridas")
    st.dataframe(bi['compras'])
    st.subheader("🔎 Diagnóstico de Inventario")
    st.dataframe(bi['kpi'][['product_name', 'diagnostico', 'quantity', 'qty_sold', 'cobertura_dias']])
