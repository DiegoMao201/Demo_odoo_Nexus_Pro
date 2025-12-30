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
import tempfile

# Intentar importar el conector, si no existe, usamos modo DEMO
try:
    from odoo_client import OdooConnector
    CONNECTION_ACTIVE = True
except ImportError:
    CONNECTION_ACTIVE = False

# --- CONFIGURACIÓN PRO ---
st.set_page_config(
    page_title="Nexus Logistics AI | Executive Suite", 
    layout="wide", 
    page_icon="💎",
    initial_sidebar_state="expanded"
)

# Estilos CSS de Alta Gama (Dark/Light mode compatible)
st.markdown("""
<style>
    .metric-card {
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
        border-radius: 15px; 
        padding: 20px; 
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        text-align: center;
        border-left: 5px solid #2E86C1;
    }
    .big-font { font-size: 20px !important; font-weight: bold; color: #2C3E50; }
    .header-style { font-size: 30px; font-weight: 800; color: #1B4F72; }
    .sub-text { font-size: 14px; color: #566573; }
    div[data-testid="stMetricValue"] { font-size: 28px; color: #1B4F72; }
    
    /* Pestañas personalizadas */
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] {
        height: 60px;
        white-space: pre-wrap;
        background-color: #F8F9F9;
        border-radius: 10px 10px 0 0;
        font-weight: 600;
    }
    .stTabs [aria-selected="true"] {
        background-color: #2E86C1;
        color: white;
    }
</style>
""", unsafe_allow_html=True)

# --- 1. GENERADOR DE DATOS DEMO (Para que el script funcione YA) ---
def generate_mock_data():
    """Genera datos realistas para demostración si Odoo falla o no está conectado."""
    categories = ['Electrónica Premium', 'Accesorios', 'Hogar Inteligente', 'Gadgets Obsoletos']
    products = []
    
    # Generar 100 productos
    for i in range(100):
        cat = np.random.choice(categories)
        base_price = np.random.randint(50, 2000)
        cost = base_price * 0.6 # Margen del 40%
        
        # Lógica de simulación: Algunos venden mucho, otros nada
        if cat == 'Electrónica Premium':
            qty = np.random.randint(0, 50) # Poco stock
            sold = np.random.randint(50, 200) # Mucha venta
        elif cat == 'Gadgets Obsoletos':
            qty = np.random.randint(100, 500) # Mucho stock
            sold = np.random.randint(0, 10) # Poca venta
        else:
            qty = np.random.randint(10, 100)
            sold = np.random.randint(10, 100)
            
        products.append({
            'product_name': f"SKU-{i:03d} | {cat} - Item {i}",
            'category': cat,
            'quantity': qty, # Stock actual
            'value': qty * cost, # Valor inventario (Costo)
            'cost_unit': cost,
            'price_unit': base_price,
            'qty_sold': sold, # Ventas periodo
            'revenue': sold * base_price, # Ingresos
            'margin': (sold * base_price) - (sold * cost) # Margen Bruto
        })
    
    return pd.DataFrame(products)

# --- 2. CARGA Y PROCESAMIENTO ---
@st.cache_data(ttl=300)
def get_master_data():
    if CONNECTION_ACTIVE:
        try:
            connector = OdooConnector()
            df_stock = connector.get_stock_data()
            df_sales = connector.get_sales_data()
            # Fusión básica (asumiendo que viene de Odoo real)
            # Aquí deberías adaptar según tu estructura real de Odoo
            # Para este ejemplo, si falla la conexión real, saltamos al except
            return df_stock, df_sales 
        except:
            return generate_mock_data(), None
    else:
        return generate_mock_data(), None

# Sidebar: Control de Mando
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/882/882706.png", width=60)
    st.markdown("## 💎 Nexus Logistics AI")
    st.markdown("<div class='sub-text'>Suite de Inteligencia Comercial</div>", unsafe_allow_html=True)
    st.divider()
    
    # Filtros
    st.subheader("⚙️ Parámetros de Análisis")
    dias_analisis = st.slider("Ventana de Análisis (Días)", 30, 365, 90)
    
    st.divider()
    st.info(f"📅 Analizando últimos {dias_analisis} días de operación.")
    
    admin_phone = st.text_input("📱 WhatsApp Gerencial", "573001234567")
    
    if not CONNECTION_ACTIVE:
        st.warning("⚠️ Modo DEMO Activo (Datos Simulados)")

# Procesamiento de Datos
with st.spinner('⚡ La IA está procesando millones de puntos de datos...'):
    data_raw, _ = get_master_data()
    
    # Si es modo demo, data_raw ya trae todo fusionado. 
    # Si fuera Odoo real, aquí harías el merge (como en tu código original).
    df = data_raw.copy()

    # --- CAMBIO DE TERMINOLOGÍA Y CÁLCULOS POTENTES ---
    
    # 1. Renombrar Columnas Técnicas a Negocio
    df = df.rename(columns={
        'quantity': 'Stock_Actual',
        'qty_sold': 'Unidades_Vendidas',
        'revenue': 'Ventas_Totales',
        'value': 'Valor_Inventario_Costo'
    })

    # 2. Métricas Avanzadas
    df['Venta_Diaria_Promedio'] = df['Unidades_Vendidas'] / dias_analisis
    
    # Días de Inventario (Days of Inventory On Hand - DIOH)
    # Evitamos división por cero asignando 0.001
    df['Dias_Para_Agotar'] = df['Stock_Actual'] / df['Venta_Diaria_Promedio'].replace(0, 0.001)
    
    # GMROI (Gross Margin Return on Investment) - Métrica Clave de Retail
    # Cuánto dinero gano por cada dólar invertido en inventario
    df['GMROI'] = np.where(df['Valor_Inventario_Costo'] > 0, 
                           df['margin'] / df['Valor_Inventario_Costo'], 
                           0)

    # 3. SEGMENTACIÓN DE MARKETING (ADIÓS A, B, C)
    df = df.sort_values('Ventas_Totales', ascending=False)
    df['Ventas_Acumuladas'] = df['Ventas_Totales'].cumsum()
    df['Porcentaje_Pareto'] = df['Ventas_Acumuladas'] / df['Ventas_Totales'].sum()

    def clasificar_producto(perc, stock, dias_agot):
        # Segmentación por Ingresos
        if perc <= 0.80: categoria = "💎 DIAMANTE (Top Seller)"
        elif perc <= 0.95: categoria = "🛡️ CORE (Estándar)"
        else: categoria = "💤 HUESO (Baja Rotación)"
        return categoria

    df['Categoria_Negocio'] = df.apply(lambda x: clasificar_producto(x['Porcentaje_Pareto'], x['Stock_Actual'], x['Dias_Para_Agotar']), axis=1)

    # 4. DIAGNÓSTICO IA (Lógica Avanzada)
    def diagnostico_ia(row):
        # Caso 1: Vende mucho y no hay stock (PÉRDIDA DE DINERO INMEDIATA)
        if row['Stock_Actual'] <= 0 and row['Venta_Diaria_Promedio'] > 0.1:
            return "🚨 URGENTE: Quiebre de Stock (Ventas Perdidas)"
        
        # Caso 2: Diamante a punto de acabarse
        if "DIAMANTE" in row['Categoria_Negocio'] and row['Dias_Para_Agotar'] < 15:
            return "⚠️ ALERTA: Reabastecer Diamante (Riesgo < 15 días)"
            
        # Caso 3: Hueso con demasiado stock (Capital Atrapado)
        if "HUESO" in row['Categoria_Negocio'] and row['Dias_Para_Agotar'] > 180:
            return "💸 LIQUIDAR: Capital Atrapado (>6 meses stock)"
            
        # Caso 4: Producto sano
        return "✅ SALUDABLE"

    df['Diagnostico_IA'] = df.apply(diagnostico_ia, axis=1)
    
    # Cálculo de "Dinero Perdido" (Oportunidad) y "Dinero Estancado"
    dinero_estancado = df[df['Diagnostico_IA'].str.contains("LIQUIDAR")]['Valor_Inventario_Costo'].sum()
    ventas_perdidas_est = df[df['Diagnostico_IA'].str.contains("URGENTE")]['Venta_Diaria_Promedio'].sum() * 30 * df['price_unit'].mean() # Estimado mensual

# --- 3. CLASE PARA GENERAR PDF EJECUTIVO ---
class PDFReport(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 15)
        self.cell(0, 10, 'NEXUS LOGISTICS - REPORTE GERENCIAL EJECUTIVO', 0, 1, 'C')
        self.set_font('Arial', 'I', 10)
        self.cell(0, 10, f'Generado el: {datetime.now().strftime("%d/%m/%Y %H:%M")}', 0, 1, 'C')
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Página {self.page_no()}', 0, 0, 'C')

def crear_pdf(dataframe):
    pdf = PDFReport()
    pdf.add_page()
    
    # Sección 1: Resumen Financiero
    pdf.set_font('Arial', 'B', 12)
    pdf.set_fill_color(200, 220, 255)
    pdf.cell(0, 10, '1. RESUMEN FINANCIERO DE ALTO NIVEL', 1, 1, 'L', 1)
    pdf.ln(5)
    
    pdf.set_font('Arial', '', 11)
    # Datos clave
    val_inv = dataframe['Valor_Inventario_Costo'].sum()
    ventas = dataframe['Ventas_Totales'].sum()
    
    pdf.cell(0, 8, f"Valor Total del Inventario (Costo): ${val_inv:,.2f}", 0, 1)
    pdf.cell(0, 8, f"Ventas del Periodo: ${ventas:,.2f}", 0, 1)
    pdf.cell(0, 8, f"Capital Estancado (Productos Hueso): ${dinero_estancado:,.2f}", 0, 1)
    pdf.ln(10)

    # Sección 2: Sugerencias de la IA
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, '2. ACCIONES CRÍTICAS SUGERIDAS POR IA', 1, 1, 'L', 1)
    pdf.ln(5)
    
    # Filtrar Top 5 Quiebres
    top_quiebres = dataframe[dataframe['Diagnostico_IA'].str.contains("URGENTE")].head(5)
    
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(0, 8, 'A. PRODUCTOS EN QUIEBRE (COMPRA INMEDIATA)', 0, 1)
    pdf.set_font('Arial', '', 9)
    
    if not top_quiebres.empty:
        for idx, row in top_quiebres.iterrows():
            nombre = row['product_name'][:50] # Cortar nombre si es largo
            pdf.cell(0, 6, f"- {nombre} (Dejó de venderse)", 0, 1)
    else:
        pdf.cell(0, 6, "Sin quiebres críticos detectados.", 0, 1)
    
    pdf.ln(5)
    
    # Filtrar Top 5 Liquidaciones
    top_liquidar = dataframe[dataframe['Diagnostico_IA'].str.contains("LIQUIDAR")].sort_values('Valor_Inventario_Costo', ascending=False).head(5)
    
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(0, 8, 'B. SUGERENCIA DE LIQUIDACIÓN (RECUPERAR CAJA)', 0, 1)
    pdf.set_font('Arial', '', 9)
    
    if not top_liquidar.empty:
        for idx, row in top_liquidar.iterrows():
            nombre = row['product_name'][:50]
            valor = row['Valor_Inventario_Costo']
            pdf.cell(0, 6, f"- {nombre} | Atrapado: ${valor:,.0f}", 0, 1)
            
    pdf.ln(10)
    pdf.set_font('Arial', 'I', 8)
    pdf.cell(0, 10, 'Este reporte es generado automáticamente por el motor Nexus Logistics AI.', 0, 1, 'C')
    
    return pdf.output(dest='S').encode('latin-1')

# --- 4. INTERFAZ VISUAL DEL DASHBOARD ---

st.title("📊 Tablero de Mando Gerencial")
st.markdown("Visión estratégica del inventario y ventas en tiempo real.")

# PESTAÑAS MEJORADAS
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "👔 Resumen Ejecutivo", 
    "📈 Matriz de Rentabilidad", 
    "🧠 Diagnóstico IA", 
    "📉 Gestión de Pérdidas",
    "📤 Exportación & Reportes"
])

# --- TAB 1: RESUMEN EJECUTIVO (BOARDROOM VIEW) ---
with tab1:
    st.markdown("### 🏦 Estado de Salud Financiera")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.metric("Ventas Totales", f"${df['Ventas_Totales'].sum():,.0f}", delta="Periodo Actual")
        st.markdown('</div>', unsafe_allow_html=True)
        
    with col2:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.metric("Capital en Bodega", f"${df['Valor_Inventario_Costo'].sum():,.0f}", delta="Costo Activo")
        st.markdown('</div>', unsafe_allow_html=True)

    with col3:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        roi_promedio = df['GMROI'].mean()
        st.metric("GMROI Promedio", f"{roi_promedio:.2f}x", delta="Eficiencia Inversión", delta_color="normal")
        st.markdown('</div>', unsafe_allow_html=True)

    with col4:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        skus_activos = len(df[df['Stock_Actual'] > 0])
        st.metric("Referencias Activas", f"{skus_activos}", delta="SKUs en Bodega")
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("---")
    
    c_chart, c_insight = st.columns([2, 1])
    
    with c_chart:
        st.subheader("Segmentación de Portafolio (Regla 80/20)")
        fig_pie = px.sunburst(
            df, 
            path=['Categoria_Negocio', 'category'], 
            values='Ventas_Totales',
            color='Categoria_Negocio',
            color_discrete_map={
                '💎 DIAMANTE (Top Seller)': '#2ECC71',
                '🛡️ CORE (Estándar)': '#F1C40F',
                '💤 HUESO (Baja Rotación)': '#E74C3C'
            },
            title="Distribución de Ingresos por Tipo de Producto"
        )
        st.plotly_chart(fig_pie, use_container_width=True)
        
    with c_insight:
        st.info("💡 **Insight Gerencial:**")
        st.markdown(f"""
        Tus productos **Diamante** representan el motor de tu empresa. 
        
        Actualmente tienes **{len(df[df['Categoria_Negocio'].contains('DIAMANTE')])} referencias** que sostienen el 80% de la facturación.
        
        **Estrategia:**
        1. Nunca permitir Stockout en Diamantes.
        2. Liquidar agresivamente los Huesos para liberar caja.
        """)

# --- TAB 2: MATRIZ DE RENTABILIDAD ---
with tab2:
    st.subheader("🔎 Análisis Cruzado: Rotación vs Rentabilidad")
    
    # Scatter Plot avanzado
    fig_matrix = px.scatter(
        df[df['Stock_Actual'] > 0],
        x="Dias_Para_Agotar",
        y="GMROI",
        size="Ventas_Totales",
        color="Categoria_Negocio",
        hover_name="product_name",
        log_x=True,
        title="Matriz de Eficiencia: ¿Qué tan rápido recupero mi inversión?",
        labels={
            "Dias_Para_Agotar": "Días de Cobertura (Log)",
            "GMROI": "Retorno sobre Inversión (x veces)"
        },
        height=500,
        color_discrete_map={
            '💎 DIAMANTE (Top Seller)': '#2ECC71',
            '🛡️ CORE (Estándar)': '#F1C40F',
            '💤 HUESO (Baja Rotación)': '#E74C3C'
        }
    )
    # Cuadrantes estratégicos
    fig_matrix.add_vline(x=45, line_dash="dot", line_color="grey", annotation_text="Límite Saludable (45 días)")
    fig_matrix.add_hline(y=1, line_dash="dot", line_color="grey", annotation_text="Punto Equilibrio")
    
    st.plotly_chart(fig_matrix, use_container_width=True)
    st.caption("Nota: El tamaño de la burbuja representa el volumen de ventas total.")

# --- TAB 3: DIAGNÓSTICO IA ---
with tab3:
    st.header("🧠 El Cerebro Digital Sugiere:")
    
    col_kpi1, col_kpi2, col_kpi3 = st.columns(3)
    col_kpi1.error(f"🚨 {len(df[df['Diagnostico_IA'].contains('URGENTE')])} Productos en Quiebre")
    col_kpi2.warning(f"⚠️ {len(df[df['Diagnostico_IA'].contains('ALERTA')])} Diamantes en Riesgo")
    col_kpi3.info(f"💸 {len(df[df['Diagnostico_IA'].contains('LIQUIDAR')])} Candidatos a Liquidación")
    
    st.divider()
    
    filtro_ia = st.selectbox("Filtrar Recomendación:", 
                             ["🚨 Ver Urgencias (Quiebres)", 
                              "⚠️ Ver Alertas (Riesgo Stock)", 
                              "💸 Ver Para Liquidar (Exceso)", 
                              "Todo el Inventario"])
    
    df_show = df.copy()
    if "Urgencias" in filtro_ia:
        df_show = df[df['Diagnostico_IA'].str.contains("URGENTE")]
    elif "Alertas" in filtro_ia:
        df_show = df[df['Diagnostico_IA'].str.contains("ALERTA")]
    elif "Liquidar" in filtro_ia:
        df_show = df[df['Diagnostico_IA'].str.contains("LIQUIDAR")]
        
    st.dataframe(
        df_show[['product_name', 'Stock_Actual', 'Venta_Diaria_Promedio', 'Dias_Para_Agotar', 'Diagnostico_IA']],
        use_container_width=True,
        column_config={
            "Stock_Actual": st.column_config.NumberColumn("Stock", format="%d u"),
            "Venta_Diaria_Promedio": st.column_config.NumberColumn("Velocidad Venta", format="%.1f u/día"),
            "Dias_Para_Agotar": st.column_config.ProgressColumn("Cobertura (Días)", min_value=0, max_value=180, format="%d días"),
        }
    )

# --- TAB 4: GESTIÓN DE PÉRDIDAS (CAPITAL TRAP) ---
with tab4:
    st.subheader("📉 ¿Dónde estoy perdiendo dinero?")
    
    c_loss1, c_loss2 = st.columns(2)
    
    with c_loss1:
        st.markdown("#### 🐢 Capital Atrapado (Inventario Lento)")
        st.markdown(f"<h2 style='color: #E74C3C'>${dinero_estancado:,.0f}</h2>", unsafe_allow_html=True)
        st.write("Dinero invertido en productos 'Hueso' con cobertura > 180 días. Este dinero no está circulando.")
        
    with c_loss2:
        st.markdown("#### 🛑 Ventas Perdidas Estimadas (Mensual)")
        st.markdown(f"<h2 style='color: #E74C3C'>${ventas_perdidas_est:,.0f}</h2>", unsafe_allow_html=True)
        st.write("Ingresos que DEJAMOS de recibir por no tener stock en productos de alta rotación (Quiebres).")

    # Gráfico de barras de los productos que más retienen capital
    top_huesos = df[df['Diagnostico_IA'].str.contains("LIQUIDAR")].sort_values('Valor_Inventario_Costo', ascending=False).head(10)
    
    if not top_huesos.empty:
        fig_trap = px.bar(top_huesos, x='Valor_Inventario_Costo', y='product_name', orientation='h',
                          title="Top 10 Productos Atrapando Capital (Urge Liquidar)",
                          color='Valor_Inventario_Costo', color_continuous_scale='Reds')
        st.plotly_chart(fig_trap, use_container_width=True)
    else:
        st.success("¡Excelente! No tienes capital atrapado significativo.")

# --- TAB 5: EXPORTACIÓN Y REPORTES ---
with tab5:
    st.header("🖨️ Centro de Reportes Corporativos")
    
    col_pdf, col_excel, col_wa = st.columns(3)
    
    # 1. EXCEL MAESTRO
    def generate_excel(df):
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='Master Data', index=False)
            df[df['Diagnostico_IA'].str.contains("URGENTE")].to_excel(writer, sheet_name='A_Comprar', index=False)
            df[df['Diagnostico_IA'].str.contains("LIQUIDAR")].to_excel(writer, sheet_name='A_Liquidar', index=False)
            
            # Formato condicional básico
            workbook = writer.book
            worksheet = writer.sheets['Master Data']
            money_fmt = workbook.add_format({'num_format': '$#,##0'})
            worksheet.set_column('E:H', 15, money_fmt)
            
        return output.getvalue()
        
    with col_excel:
        st.subheader("📊 Data Cruda (Excel)")
        st.markdown("Descarga el dataset completo con todas las métricas calculadas para tu equipo de análisis.")
        excel_data = generate_excel(df)
        st.download_button(
            label="📥 Descargar Excel (.xlsx)",
            data=excel_data,
            file_name=f"Nexus_Data_{datetime.now().date()}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    # 2. PDF EJECUTIVO
    with col_pdf:
        st.subheader("📄 Reporte PDF Gerencial")
        st.markdown("Genera un resumen ejecutivo formal listo para imprimir y presentar en juntas directivas.")
        
        if st.button("Generar PDF Ejecutivo"):
            with st.spinner("Redactando informe..."):
                pdf_bytes = crear_pdf(df)
                b64 = base64.b64encode(pdf_bytes).decode()
                href = f'<a href="data:application/octet-stream;base64,{b64}" download="Reporte_Gerencial_Nexus.pdf" style="text-decoration:none;"><button style="background-color:#E74C3C;color:white;padding:10px;border:none;border-radius:5px;cursor:pointer;width:100%">📄 Descargar PDF Listo</button></a>'
                st.markdown(href, unsafe_allow_html=True)

    # 3. WHATSAPP BOT
    with col_wa:
        st.subheader("📲 Alerta Rápida")
        st.markdown("Envía las métricas críticas directamente al WhatsApp del Gerente.")
        
        msg = f"*NEXUS REPORT - {datetime.now().date()}*\n\n"
        msg += f"💰 Ventas: ${df['Ventas_Totales'].sum():,.0f}\n"
        msg += f"🐢 Cap. Atrapado: ${dinero_estancado:,.0f}\n"
        msg += f"🚨 Quiebres Críticos: {len(df[df['Diagnostico_IA'].str.contains('URGENTE')])}\n\n"
        msg += "_Enviado desde Nexus AI_"
        
        encoded_msg = urllib.parse.quote(msg)
        wa_link = f"https://wa.me/{admin_phone}?text={encoded_msg}"
        
        st.markdown(f"""
            <a href="{wa_link}" target="_blank">
                <button style="background-color:#25D366;color:white;border:none;padding:10px;border-radius:5px;width:100%;cursor:pointer;">
                    🚀 Enviar a WhatsApp
                </button>
            </a>
        """, unsafe_allow_html=True)

st.divider()
st.caption("Nexus Logistics AI System v3.0 Ultra | Powered by Python & Streamlit")
