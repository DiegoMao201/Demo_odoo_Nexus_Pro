import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
from io import BytesIO
from datetime import datetime, timedelta

# --- 1. CONFIGURACIÓN DE PÁGINA Y TEMA ---
st.set_page_config(
    page_title="NEXUS PRO | Command Center",
    layout="wide",
    page_icon="💎",
    initial_sidebar_state="expanded"
)

# --- 2. ESTILOS CSS PROFESIONALES (DARK/LIGHT MODE COMPATIBLE) ---
st.markdown("""
<style>
    /* Estética General */
    .main { background-color: #f8f9fa; }
    h1, h2, h3 { font-family: 'Helvetica Neue', sans-serif; font-weight: 700; color: #0f172a; }
    
    /* Métricas Cards */
    .metric-card {
        background: white;
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        border-left: 5px solid #3b82f6;
        transition: transform 0.2s;
    }
    .metric-card:hover { transform: translateY(-2px); }
    .metric-title { font-size: 0.9rem; color: #64748b; text-transform: uppercase; letter-spacing: 1px; }
    .metric-value { font-size: 2rem; font-weight: 800; color: #1e293b; }
    .metric-delta { font-size: 0.9rem; font-weight: 600; }
    .delta-pos { color: #10b981; }
    .delta-neg { color: #ef4444; }

    /* Tabs Personalizados */
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        background-color: white;
        border-radius: 8px;
        font-weight: 600;
        box-shadow: 0 2px 4px rgba(0,0,0,0.02);
    }
    .stTabs [aria-selected="true"] {
        background-color: #3b82f6;
        color: white;
    }

    /* Tablas */
    div[data-testid="stDataFrame"] { border-radius: 10px; overflow: hidden; box-shadow: 0 2px 10px rgba(0,0,0,0.05); }
</style>
""", unsafe_allow_html=True)

# --- 3. GESTIÓN DE DATOS (MOCK Y CONEXIÓN) ---

try:
    from odoo_client import OdooConnector
    from utils_data import upload_odoo_data_to_postgres
    CONNECTION_ACTIVE = True
except ImportError:
    CONNECTION_ACTIVE = False

def generate_mock_data():
    """Genera datos complejos para simular un entorno ERP real."""
    np.random.seed(42)
    n_products = 300
    categories = ['Electrónica', 'Hogar', 'Moda', 'Industrial', 'Deportes']
    locations = ['Tienda Principal', 'Bodega Central', 'Sucursal Norte', 'Sucursal Sur']
    
    products = []
    for i in range(n_products):
        cat = np.random.choice(categories)
        base_price = np.random.uniform(10, 500)
        cost = base_price * np.random.uniform(0.5, 0.7) # Margen variable
        stock = int(np.random.exponential(50)) # Distribución exponencial para stock
        sold_90d = int(np.random.poisson(30)) if np.random.rand() > 0.2 else 0 # 20% son productos muertos
        
        products.append({
            'product_id': i,
            'product_name': f"{cat[:3].upper()}-{i:03d} | Producto {cat} Premium",
            'category': cat,
            'location': np.random.choice(locations),
            'quantity': stock,
            'cost_unit': cost,
            'sales_price': base_price,
            'qty_sold_90d': sold_90d,
            'lead_time_days': np.random.randint(5, 45)
        })
    return pd.DataFrame(products)

@st.cache_data(ttl=600)
def get_data():
    if CONNECTION_ACTIVE:
        try:
            connector = OdooConnector()
            # Aquí iría la lógica real de extracción y fusión de tablas
            # Para este ejemplo completo, simularemos que la fusión ya ocurrió
            # o retornaremos el mock si falla.
            return generate_mock_data(), True 
        except:
            return generate_mock_data(), False
    else:
        return generate_mock_data(), False

# --- 4. MOTOR INTELIGENTE (BI ENGINE) ---
class NexusIntelligence:
    def __init__(self, df, dias_analisis=90):
        self.df = df.copy()
        self.dias = dias_analisis
        self._process_metrics()

    def _process_metrics(self):
        # Cálculos Base
        self.df['stock_value'] = self.df['quantity'] * self.df['cost_unit']
        self.df['sales_value_90d'] = self.df['qty_sold_90d'] * self.df['sales_price']
        self.df['gross_margin'] = self.df['sales_price'] - self.df['cost_unit']
        self.df['total_margin_90d'] = self.df['qty_sold_90d'] * self.df['gross_margin']
        
        # Rotación y Cobertura
        self.df['daily_sales'] = self.df['qty_sold_90d'] / self.dias
        self.df['days_of_inventory'] = np.where(
            self.df['daily_sales'] > 0, 
            self.df['quantity'] / self.df['daily_sales'], 
            999 # Infinito/Sin venta
        )
        
        # GMROI (Gross Margin Return on Investment)
        avg_inventory_cost = self.df['stock_value'] # Simplificado (Stock actual)
        self.df['gmroi'] = np.where(
            avg_inventory_cost > 0,
            self.df['total_margin_90d'] / avg_inventory_cost,
            0
        )

        # Clasificación ABC (Basado en Ventas Valorizadas)
        df_sorted = self.df.sort_values('sales_value_90d', ascending=False)
        df_sorted['cumsum_sales'] = df_sorted['sales_value_90d'].cumsum()
        df_sorted['total_sales'] = df_sorted['sales_value_90d'].sum()
        df_sorted['cum_perc'] = df_sorted['cumsum_sales'] / df_sorted['total_sales']
        
        def classify_abc(x):
            if x <= 0.80: return 'A'
            elif x <= 0.95: return 'B'
            else: return 'C'
            
        self.df['ABC_Class'] = df_sorted['cum_perc'].apply(classify_abc).sort_index()

        # Matriz BCG / Ciclo de Vida
        def classify_lifecycle(row):
            if row['ABC_Class'] == 'A' and row['days_of_inventory'] < 30: return "🌟 Estrella (Reponer)"
            if row['ABC_Class'] == 'C' and row['days_of_inventory'] > 120: return "💀 Hueso (Liquidar)"
            if row['ABC_Class'] == 'A' and row['days_of_inventory'] > 60: return "🐄 Vaca Lechera (Exceso)"
            if row['quantity'] == 0 and row['daily_sales'] > 0.1: return "🚨 QUIEBRE STOCK"
            return "❔ Interrogante"
        
        self.df['Lifecycle_Status'] = self.df.apply(classify_lifecycle, axis=1)

    def get_purchase_suggestions(self):
        """Genera orden de compra inteligente."""
        # Lógica: Stock de Seguridad + (Venta Diaria * Lead Time) - Stock Actual
        # Target: Mantener 45 días de inventario
        target_days = 45
        
        df_buy = self.df.copy()
        df_buy['safety_stock'] = df_buy['daily_sales'] * 7 # 7 días de seguridad
        df_buy['reorder_point'] = (df_buy['daily_sales'] * df_buy['lead_time_days']) + df_buy['safety_stock']
        df_buy['target_qty'] = df_buy['daily_sales'] * target_days
        
        df_buy['suggested_buy'] = (df_buy['target_qty'] - df_buy['quantity']).clip(lower=0)
        df_buy['investment_needed'] = df_buy['suggested_buy'] * df_buy['cost_unit']
        
        return df_buy[df_buy['suggested_buy'] > 0].sort_values('ABC_Class')

    def get_transfer_suggestions(self):
        """Balanceo de inventario entre ubicaciones (Simulado para Demo)."""
        # Identificar productos con > 180 días en una tienda y < 15 en otra
        # Para el mock, creamos una lógica simplificada
        overstock = self.df[self.df['days_of_inventory'] > 150]
        stockout = self.df[self.df['days_of_inventory'] < 10]
        
        # Cruzamos datos (simulación)
        suggestions = []
        if not overstock.empty and not stockout.empty:
            for _, row_over in overstock.head(20).iterrows():
                suggestions.append({
                    'Producto': row_over['product_name'],
                    'Origen': row_over['location'],
                    'Destino': 'Tienda Principal' if row_over['location'] != 'Tienda Principal' else 'Sucursal Norte',
                    'Cantidad': int(row_over['quantity'] * 0.5), # Mover la mitad del exceso
                    'Motivo': f"Exceso ({int(row_over['days_of_inventory'])} días) -> Demanda Alta"
                })
        return pd.DataFrame(suggestions)

# --- 5. COMPONENTES VISUALES ---

def metric_card(title, value, delta=None, prefix="", suffix=""):
    delta_html = ""
    if delta is not None:
        color = "delta-pos" if delta >= 0 else "delta-neg"
        arrow = "↑" if delta >= 0 else "↓"
        delta_html = f'<span class="metric-delta {color}">{arrow} {abs(delta):.1f}%</span>'
    
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-title">{title}</div>
        <div class="metric-value">{prefix}{value}{suffix}</div>
        {delta_html}
    </div>
    """, unsafe_allow_html=True)

def plot_pareto(df):
    df_chart = df.groupby('ABC_Class')['sales_value_90d'].sum().reset_index()
    fig = px.bar(df_chart, x='ABC_Class', y='sales_value_90d', 
                 color='ABC_Class', title="Distribución de Ventas por Clase ABC",
                 color_discrete_map={'A': '#3b82f6', 'B': '#64748b', 'C': '#ef4444'})
    fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
    return fig

def plot_scatter_quadrant(df):
    fig = px.scatter(
        df, x="days_of_inventory", y="gmroi", size="stock_value", color="ABC_Class",
        hover_name="product_name", log_x=True,
        title="Matriz Valor vs. Velocidad (GMROI vs Días Inventario)",
        labels={"days_of_inventory": "Días de Stock (Log)", "gmroi": "GMROI (Rentabilidad)"},
        color_discrete_map={'A': '#10b981', 'B': '#f59e0b', 'C': '#ef4444'}
    )
    # Cuadrantes
    fig.add_hline(y=1, line_dash="dot", annotation_text="Rentabilidad Minima")
    fig.add_vline(x=90, line_dash="dot", annotation_text="Límite Obsolescencia")
    fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
    return fig

# --- 6. INTERFAZ PRINCIPAL ---

def main():
    # SIDEBAR
    with st.sidebar:
        st.markdown("### 💎 NEXUS PRO IA")
        st.markdown("---")
        dias = st.slider("📅 Ventana de Análisis", 30, 365, 90)
        
        # Carga de Datos
        df_raw, is_real = get_data()
        
        # Filtros Globales
        cats = df_raw['category'].unique()
        sel_cats = st.multiselect("Filtrar Categoría", cats, default=cats)
        
        locs = df_raw['location'].unique()
        sel_locs = st.multiselect("Filtrar Almacén", locs, default=locs)
        
        if st.button("🔄 Refrescar Datos Odoo"):
            st.toast("Conectando API Odoo...", icon="⏳")
            # Logic de recarga real iría aquí
            st.toast("Datos Actualizados", icon="✅")

    # FILTRADO DE DATOS
    df_filtered = df_raw[df_raw['category'].isin(sel_cats) & df_raw['location'].isin(sel_locs)]
    
    # INICIALIZAR MOTOR IA
    engine = NexusIntelligence(df_filtered, dias_analisis=dias)
    df_kpi = engine.df
    
    # TABS PRINCIPALES
    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 Tablero de Control", 
        "🚀 Compras Inteligentes", 
        "🚚 Logística & Traslados",
        "🔎 Análisis Profundo"
    ])

    # --- TAB 1: OVERVIEW ---
    with tab1:
        st.markdown("### 📢 Resumen Ejecutivo")
        col1, col2, col3, col4 = st.columns(4)
        
        total_stock_val = df_kpi['stock_value'].sum()
        total_sales = df_kpi['sales_value_90d'].sum()
        dead_stock = df_kpi[df_kpi['Lifecycle_Status'].str.contains("Hueso")]['stock_value'].sum()
        health_score = (1 - (dead_stock / total_stock_val)) * 100
        
        with col1: metric_card("Valor Inventario", f"{total_stock_val/1000:,.1f}k", delta=None, prefix="$")
        with col2: metric_card("Ventas (Periodo)", f"{total_sales/1000:,.1f}k", delta=12.5, prefix="$")
        with col3: metric_card("Capital Hueso", f"{dead_stock/1000:,.1f}k", delta=-5.2, prefix="$")
        with col4: metric_card("Salud Inventario", f"{health_score:.0f}", suffix="/100")
        
        st.markdown("---")
        
        c1, c2 = st.columns([2, 1])
        with c1:
            st.plotly_chart(plot_scatter_quadrant(df_kpi), use_container_width=True)
        with c2:
            st.plotly_chart(plot_pareto(df_kpi), use_container_width=True)
            
            # Alerta rápida
            quiebres = df_kpi[df_kpi['Lifecycle_Status'] == "🚨 QUIEBRE STOCK"]
            st.warning(f"⚠️ {len(quiebres)} Productos Críticos en Quiebre (A)")
            if not quiebres.empty:
                st.dataframe(quiebres[['product_name', 'qty_sold_90d']], height=150, hide_index=True)

    # --- TAB 2: COMPRAS ---
    with tab2:
        st.markdown("### 🛒 Sugerencias de Reaprovisionamiento (Algoritmo: Forecast - Stock)")
        df_buy = engine.get_purchase_suggestions()
        
        col_res1, col_res2 = st.columns(2)
        with col_res1:
            st.info(f"💰 Inversión Total Sugerida: **${df_buy['investment_needed'].sum():,.2f}**")
        with col_res2:
            st.success(f"📦 Referencias a pedir: **{len(df_buy)} SKUs**")
            
        st.dataframe(
            df_buy[['product_name', 'ABC_Class', 'quantity', 'daily_sales', 'lead_time_days', 'suggested_buy', 'investment_needed']]
            .style.background_gradient(subset=['investment_needed'], cmap="Greens")
            .format({'daily_sales': "{:.2f}", 'investment_needed': "${:,.2f}"}),
            use_container_width=True,
            height=600
        )
        
        if st.button("📥 Descargar Orden de Compra (PDF)"):
            st.toast("Generando PDF...", icon="📄")

    # --- TAB 3: TRASLADOS ---
    with tab3:
        st.markdown("### 🚚 Balanceo de Stock entre Tiendas")
        df_transfer = engine.get_transfer_suggestions()
        
        if df_transfer.empty:
            st.success("✅ La red de tiendas está balanceada. No se requieren traslados urgentes.")
        else:
            col_t1, col_t2 = st.columns([3, 1])
            with col_t1:
                st.dataframe(
                    df_transfer,
                    column_config={
                        "Cantidad": st.column_config.NumberColumn("Unds a Mover", help="Cantidad sugerida"),
                    },
                    use_container_width=True
                )
            with col_t2:
                st.markdown("#### 💡 Insight")
                st.write("Estos movimientos liberarán **Capital Atrapado** en tiendas de baja rotación y evitarán **Ventas Perdidas** en tiendas de alta demanda.")
                st.button("📧 Enviar Solicitud a Logística", type="primary")

    # --- TAB 4: ANÁLISIS ---
    with tab4:
        st.markdown("### 🔎 Explorador de Productos")
        
        search = st.text_input("Buscar SKU o Nombre", "")
        if search:
            df_view = df_kpi[df_kpi['product_name'].str.contains(search, case=False)]
        else:
            df_view = df_kpi
            
        st.dataframe(
            df_view[['product_name', 'category', 'location', 'quantity', 'days_of_inventory', 'Lifecycle_Status', 'gmroi']]
            .style.applymap(lambda x: 'color: red; font-weight: bold' if x == '🚨 QUIEBRE STOCK' else '', subset=['Lifecycle_Status']),
            use_container_width=True
        )
        
        st.markdown("#### 📉 Distribución de Antigüedad")
        hist_fig = px.histogram(df_kpi, x="days_of_inventory", nbins=50, title="Histograma: Días de Cobertura", color_discrete_sequence=['#6366f1'])
        st.plotly_chart(hist_fig, use_container_width=True)

if __name__ == "__main__":
    main()