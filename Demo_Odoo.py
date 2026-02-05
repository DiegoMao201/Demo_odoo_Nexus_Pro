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
            df_sales = connector.get_sales_data()

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

def process_business_logic(df_raw, days_analyzed):
    df = df_raw.copy()
    
    # A. Renombrar a lenguaje de Negocio
    df = df.rename(columns={
        'quantity': 'Stock_Fisico',
        'value': 'Capital_Invertido',
        'qty_sold': 'Rotacion_Unidades',
        'revenue': 'Ventas_Totales'
    })
    
    # B. Cálculos Financieros Avanzados
    df['Venta_Diaria'] = df['Rotacion_Unidades'] / dias_analisis
    
    # Cobertura (Días de Inventario)
    df['Dias_Cobertura'] = df['Stock_Fisico'] / df['Venta_Diaria'].replace(0, 0.001)
    
    # Precio Promedio Real
    df['Precio_Promedio'] = df['Ventas_Totales'] / df['Rotacion_Unidades'].replace(0, 1)
    
    # Margen Bruto Estimado
    df['Costo_Ventas'] = df['Rotacion_Unidades'] * df['cost_unit']
    df['Margen_Bruto'] = df['Ventas_Totales'] - df['Costo_Ventas']
    
    # GMROI (Gross Margin Return on Investment)
    df['GMROI'] = np.where(df['Capital_Invertido'] > 0, 
                           df['Margen_Bruto'] / df['Capital_Invertido'], 
                           0)

    # C. Segmentación de Marketing (Pareto)
    df = df.sort_values('Ventas_Totales', ascending=False)
    df['Ventas_Acum'] = df['Ventas_Totales'].cumsum()
    df['Pareto_Perc'] = df['Ventas_Acum'] / df['Ventas_Totales'].sum()
    
    def clasificar_segmento(row):
        perc = row['Pareto_Perc']
        dias = row['Dias_Cobertura']
        
        tipo_producto = "C"
        if perc <= 0.80: tipo_producto = "A"
        elif perc <= 0.95: tipo_producto = "B"
        
        if tipo_producto == "A": return "💎 DIAMANTE (Vital)"
        if tipo_producto == "C" and dias > 180: return "💀 HUESO (Obsoleto)"
        if tipo_producto == "B": return "🛡️ CORE (Estándar)"
        return "📉 COLA (Baja Rotación)"

    df['Segmento_Mkt'] = df.apply(clasificar_segmento, axis=1)

    # D. Motor de Recomendación IA
    def motor_decision(row):
        stock = row['Stock_Fisico']
        dias = row['Dias_Cobertura']
        segmento = row['Segmento_Mkt']
        
        if stock <= 0 and row['Rotacion_Unidades'] > 0:
            return "🚨 URGENTE: Quiebre de Stock (Venta Perdida)"
        
        if "DIAMANTE" in segmento and dias < 20:
            return "⚠️ ALERTA: Reabastecer Diamante (Riesgo)"
            
        if "HUESO" in segmento:
            return "💸 LIQUIDAR: Capital Atrapado (>6 meses)"
            
        if dias > 365:
            return "🛑 EXCESO CRÍTICO: > 1 Año Stock"
            
        return "✅ SALUDABLE"

    df['Diagnostico_IA'] = df.apply(motor_decision, axis=1)
    
    return df

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
    
    df = process_business_logic(raw_data, dias_analisis)

# KPIs Principales (Header)
st.title("💎 NEXUS PRO IA | Dashboard Gerencial")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown('<div class="metric-card">', unsafe_allow_html=True)
    st.metric("Ingresos Totales", f"${df['Ventas_Totales'].sum():,.0f}", delta="Periodo Seleccionado")
    st.markdown('</div>', unsafe_allow_html=True)

with col2:
    st.markdown('<div class="metric-card">', unsafe_allow_html=True)
    st.metric("Capital Invertido", f"${df['Capital_Invertido'].sum():,.0f}", delta="Costo Inventario")
    st.markdown('</div>', unsafe_allow_html=True)

with col3:
    st.markdown('<div class="metric-card">', unsafe_allow_html=True)
    roi = df['GMROI'].mean()
    st.metric("GMROI (Eficiencia)", f"{roi:.2f}x", delta="Retorno x $ Invertido")
    st.markdown('</div>', unsafe_allow_html=True)

with col4:
    st.markdown('<div class="metric-card">', unsafe_allow_html=True)
    health = len(df[df['Diagnostico_IA'] == "✅ SALUDABLE"]) / len(df) * 100
    st.metric("Salud de Inventario", f"{health:.1f}%", delta="Referencias Sanas")
    st.markdown('</div>', unsafe_allow_html=True)

# --- PESTAÑAS DE ANÁLISIS ---
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "👔 Visión Estratégica", 
    "📊 Matriz Rentabilidad", 
    "🤖 Diagnóstico IA", 
    "📉 Capital Atrapado", 
    "📤 Reportes & Exportación"
])

# TAB 1: ESTRATEGIA
with tab1:
    c_pie, c_desc = st.columns([2, 1])
    with c_pie:
        st.subheader("Composición del Portafolio (Estrategia Diamante)")
        fig_sun = px.sunburst(
            df, 
            path=['Segmento_Mkt', 'category'], 
            values='Ventas_Totales',
            color='Segmento_Mkt',
            color_discrete_map={
                '💎 DIAMANTE (Vital)': '#2ECC71',
                '🛡️ CORE (Estándar)': '#F1C40F',
                '💀 HUESO (Obsoleto)': '#E74C3C',
                '📉 COLA (Baja Rotación)': '#95A5A6'
            },
            title="Distribución de Ingresos por Segmento"
        )
        st.plotly_chart(fig_sun, use_container_width=True)
    
    with c_desc:
        st.info("💡 **Interpretación Gerencial:**")
        st.markdown("""
        * **💎 DIAMANTES:** Generan el 80% de tu flujo de caja. **Prioridad: Cero Quiebres.**
        * **🛡️ CORE:** Productos complementarios. Mantener stock saludable.
        * **💀 HUESOS:** Consumen capital y espacio pero no generan dinero. **Prioridad: Liquidar.**
        """)

# TAB 2: MATRIZ
with tab2:
    st.subheader("Matriz de Eficiencia: Velocidad vs Retorno")
    fig_scatter = px.scatter(
        df[df['Stock_Fisico'] > 0],
        x="Dias_Cobertura",
        y="GMROI",
        size="Ventas_Totales",
        color="Segmento_Mkt",
        hover_name="product_name",
        log_x=True,
        title="Análisis de Burbuja (Tamaño = Ventas)",
        labels={"Dias_Cobertura": "Días para Agotar Stock (Log)", "GMROI": "Retorno de Inversión (Veces)"},
        color_discrete_map={
            '💎 DIAMANTE (Vital)': '#2ECC71',
            '🛡️ CORE (Estándar)': '#F1C40F',
            '💀 HUESO (Obsoleto)': '#E74C3C',
            '📉 COLA (Baja Rotación)': '#95A5A6'
        }
    )
    fig_scatter.add_vline(x=45, line_dash="dash", line_color="grey", annotation_text="Límite Sano")
    st.plotly_chart(fig_scatter, use_container_width=True)

# TAB 3: DIAGNÓSTICO IA
with tab3:
    col_alert, col_filt = st.columns([3, 1])
    with col_filt:
        st.markdown("<br>", unsafe_allow_html=True)
        filtro = st.radio("Filtrar Acción:", ["🚨 URGENTE (Quiebres)", "⚠️ ALERTAS (Riesgo)", "💸 LIQUIDAR (Exceso)", "TODO"])
    
    with col_alert:
        st.subheader("📋 Plan de Acción Generado por IA")
        if filtro == "TODO":
            df_view = df[df['Diagnostico_IA'] != "✅ SALUDABLE"]
        elif "URGENTE" in filtro:
            df_view = df[df['Diagnostico_IA'].str.contains("URGENTE")]
        elif "ALERTAS" in filtro:
            df_view = df[df['Diagnostico_IA'].str.contains("ALERTA")]
        else:
            df_view = df[df['Diagnostico_IA'].str.contains("LIQUIDAR|EXCESO")]
            
        st.dataframe(
            df_view[['product_name', 'Stock_Fisico', 'Dias_Cobertura', 'GMROI', 'Diagnostico_IA']],
            use_container_width=True,
            column_config={
                "Dias_Cobertura": st.column_config.NumberColumn("Días Stock", format="%d d"),
                "GMROI": st.column_config.NumberColumn("ROI", format="%.2fx"),
            }
        )

# TAB 4: CAPITAL ATRAPADO
with tab4:
    dinero_hueso = df[df['Diagnostico_IA'].str.contains("LIQUIDAR")]['Capital_Invertido'].sum()
    st.subheader("📉 Análisis de Pérdidas de Oportunidad")
    
    c_loss1, c_loss2 = st.columns(2)
    with c_loss1:
        st.error(f"💰 Capital Estancado (Huesos): ${dinero_hueso:,.0f}")
        st.markdown("Este es dinero congelado en bodega que podrías usar para comprar más 'Diamantes'.")
        
    with c_loss2:
        top_huesos = df[df['Diagnostico_IA'].str.contains("LIQUIDAR")].sort_values('Capital_Invertido', ascending=False).head(5)
        st.write("**Top 5 Productos que están 'secuestrando' tu capital:**")
        if not top_huesos.empty:
            st.table(top_huesos[['product_name', 'Capital_Invertido']])
        else:
            st.success("¡Tu inventario está limpio! No hay capital atrapado significativo.")

# TAB 5: REPORTES
with tab5:
    st.header("🖨️ Centro de Exportación")
    
    col_r1, col_r2, col_r3 = st.columns(3)
    
    # EXCEL
    with col_r1:
        st.subheader("📊 Excel Data Master")
        def to_excel(df):
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.to_excel(writer, sheet_name='Analisis_Completo', index=False)
                df[df['Diagnostico_IA'].str.contains("URGENTE")].to_excel(writer, sheet_name='Orden_Compra', index=False)
            return output.getvalue()
            
        st.download_button(
            "📥 Descargar Excel (.xlsx)",
            data=to_excel(df),
            file_name=f"Nexus_Data_{datetime.now().date()}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
    # PDF
    with col_r2:
        st.subheader("📄 Reporte Ejecutivo PDF")
        if st.button("Generar Informe Gerencial"):
            pdf_data = create_pdf(df)
            b64 = base64.b64encode(pdf_data).decode()
            href = f'<a href="data:application/octet-stream;base64,{b64}" download="Nexus_Report.pdf" style="text-decoration:none;"><button style="width:100%;padding:10px;background:#E74C3C;color:white;border:none;border-radius:5px;cursor:pointer;">⬇️ Descargar PDF Listo</button></a>'
            st.markdown(href, unsafe_allow_html=True)
            
    # WHATSAPP
    with col_r3:
        st.subheader("📲 Alerta Gerencial")
        msg = f"*REPORTE NEXUS PRO IA {datetime.now().date()}*\n\n"
        msg += f"✅ Ventas: ${df['Ventas_Totales'].sum():,.0f}\n"
        msg += f"🚨 Quiebres Críticos: {len(df[df['Diagnostico_IA'].str.contains('URGENTE')])}\n"
        msg += f"🐢 Dinero Atrapado: ${dinero_hueso:,.0f}\n"
        msg += "\n_Generado por NEXUS PRO IA_"
        
        encoded_msg = urllib.parse.quote(msg)
        st.markdown(f"""
        <a href="https://wa.me/{admin_phone}?text={encoded_msg}" target="_blank">
            <button style="width:100%;padding:10px;background:#25D366;color:white;border:none;border-radius:5px;cursor:pointer;">🚀 Enviar WhatsApp</button>
        </a>
        """, unsafe_allow_html=True)

st.caption("NEXUS PRO IA System v3.0 | Powered by Python & Streamlit")

# --- 8. KPIs POSTGRES ---
def get_pg_engine():
    import os
    pg_url = (
        f"postgresql://{os.getenv('PG_USER')}:{os.getenv('PG_PASSWORD')}"
        f"@{os.getenv('PG_HOST')}:{os.getenv('PG_PORT')}/{os.getenv('PG_DB')}"
    )
    return create_engine(pg_url)

def kpis_postgres():
    engine = get_pg_engine()
    # Productos diferentes
    productos = pd.read_sql("SELECT COUNT(DISTINCT nombre) FROM producto WHERE empresa_id=1", engine).iloc[0,0]
    # Ventas totales
    ventas = pd.read_sql("SELECT COUNT(*) FROM venta_linea WHERE empresa_id=1", engine).iloc[0,0]
    # Clientes diferentes
    clientes = pd.read_sql("SELECT COUNT(DISTINCT nombre) FROM cliente WHERE empresa_id=1", engine).iloc[0,0]
    return productos, ventas, clientes

productos, ventas, clientes = kpis_postgres()
st.info(f"**Productos diferentes:** {productos} | **Ventas totales:** {ventas} | **Clientes diferentes:** {clientes}")
