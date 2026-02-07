import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
from io import BytesIO
import time

# --- 1. CONFIGURACIÓN DE PÁGINA Y TEMA (MODO COMANDO) ---
st.set_page_config(
    page_title="NEXUS PRO | Enterprise Command Center",
    layout="wide",
    page_icon="💎",
    initial_sidebar_state="collapsed" # Colapsado para dar máximo espacio al dashboard
)

# --- 2. ESTILOS CSS AVANZADOS (COMPACTO Y PROFESIONAL) ---
st.markdown("""
<style>
    /* Reset y Fuente Base */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;800&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    /* Fondo y Estructura Principal */
    .stApp {
        background-color: #f1f5f9; /* Slate 100 */
    }
    
    /* Encabezados */
    h1, h2, h3 {
        color: #0f172a;
        font-weight: 800;
        letter-spacing: -0.5px;
    }

    /* Métricas Cards (KPIs) - Diseño Compacto */
    div[data-testid="metric-container"] {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        padding: 15px 20px;
        border-radius: 10px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        transition: all 0.2s ease;
    }
    div[data-testid="metric-container"]:hover {
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
        transform: translateY(-2px);
        border-color: #3b82f6;
    }
    div[data-testid="metric-container"] label {
        font-size: 0.8rem;
        text-transform: uppercase;
        color: #64748b;
        font-weight: 600;
    }
    div[data-testid="metric-container"] div[data-testid="stMetricValue"] {
        font-size: 1.8rem;
        color: #1e293b;
        font-weight: 800;
    }

    /* Tablas Editables Premium */
    div[data-testid="stDataEditor"] {
        border-radius: 10px;
        overflow: hidden;
        border: 1px solid #e2e8f0;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }

    /* Botones de Acción */
    .stButton > button {
        border-radius: 8px;
        font-weight: 600;
        border: none;
        transition: all 0.2s;
    }
    .stButton > button:hover {
        transform: scale(1.02);
    }

    /* Tabs Personalizados */
    .stTabs [data-baseweb="tab-list"] {
        gap: 10px;
        background-color: transparent;
        padding-bottom: 10px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 45px;
        background-color: #ffffff;
        border-radius: 8px;
        font-weight: 600;
        color: #64748b;
        border: 1px solid #e2e8f0;
        padding: 0 20px;
    }
    .stTabs [aria-selected="true"] {
        background-color: #2563eb;
        color: #ffffff !important;
        border-color: #2563eb;
    }

    /* Ajustes de Espaciado Global */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
</style>
""", unsafe_allow_html=True)

# --- 3. HELPER FUNCTIONS (FORMATOS) ---
def format_currency(value):
    return f"$ {value:,.2f}"

def format_number(value):
    return f"{value:,.0f}"

# --- 4. GESTIÓN DE DATOS & GENERADOR MOCK (LÓGICA MEJORADA) ---

@st.cache_data(ttl=3600)
def get_data_engine():
    """Genera datos simulados con estructura empresarial real."""
    np.random.seed(42)
    n_products = 500
    
    categories = ['Electrónica', 'Hogar', 'Moda', 'Industrial', 'Deportes', 'Automotriz']
    locations = ['CD Principal (Bogotá)', 'Bodega Norte', 'Tienda Medellín', 'Tienda Cali']
    
    data = []
    for i in range(n_products):
        cat = np.random.choice(categories)
        base_price = np.random.uniform(20, 1500)
        cost = base_price * np.random.uniform(0.4, 0.75) # Margen variable
        stock = int(np.random.exponential(100)) 
        
        # Simulación de venta estacional
        sold_90d = int(np.random.poisson(50)) if np.random.rand() > 0.15 else 0 
        
        data.append({
            'SKU': f"{cat[:3].upper()}-{i:04d}",
            'Producto': f"Item {cat} Premium Modelo {i}",
            'Categoría': cat,
            'Ubicación': np.random.choice(locations),
            'Stock Actual': stock,
            'Costo Unitario': round(cost, 2),
            'Precio Venta': round(base_price, 2),
            'Venta Trimestral': sold_90d,
            'Lead Time (Días)': np.random.randint(5, 60),
            'Proveedor': f"Global Supply {np.random.choice(['Inc.', 'Ltd.', 'S.A.S'])}"
        })
    
    return pd.DataFrame(data)

# --- 5. MOTOR DE INTELIGENCIA DE NEGOCIOS (BI ENGINE) ---
class NexusIntelligence:
    def __init__(self, df, dias_analisis=90):
        self.df = df.copy()
        self.dias = dias_analisis
        self._calculate_kpis()

    def _calculate_kpis(self):
        # 1. Valorizaciones
        self.df['Valor Inventario'] = self.df['Stock Actual'] * self.df['Costo Unitario']
        self.df['Venta Total ($)'] = self.df['Venta Trimestral'] * self.df['Precio Venta']
        self.df['Margen ($)'] = self.df['Precio Venta'] - self.df['Costo Unitario']
        self.df['Utilidad Bruta'] = self.df['Venta Trimestral'] * self.df['Margen ($)']
        
        # 2. Métricas de Rotación
        self.df['Venta Diaria Prom'] = self.df['Venta Trimestral'] / self.dias
        
        # Evitar división por cero
        self.df['Cobertura (Días)'] = np.where(
            self.df['Venta Diaria Prom'] > 0,
            self.df['Stock Actual'] / self.df['Venta Diaria Prom'],
            999 # Stock dormido
        )
        
        # 3. GMROI (Rentabilidad sobre inventario)
        # GMROI = Margen Bruto Total / Costo Promedio Inventario
        self.df['GMROI'] = np.where(
            self.df['Valor Inventario'] > 0,
            self.df['Utilidad Bruta'] / self.df['Valor Inventario'],
            0
        )

        # 4. Clasificación ABC (Pareto) sobre Venta Valorizada
        df_sorted = self.df.sort_values('Venta Total ($)', ascending=False)
        df_sorted['Acumulado'] = df_sorted['Venta Total ($)'].cumsum()
        total_sales = df_sorted['Venta Total ($)'].sum()
        df_sorted['% Acumulado'] = df_sorted['Acumulado'] / total_sales
        
        def classify(x):
            if x <= 0.80: return 'A (Core)'
            elif x <= 0.95: return 'B (Regular)'
            else: return 'C (Cola)'
            
        self.df['Clasificación ABC'] = df_sorted['% Acumulado'].apply(classify).sort_index()

        # 5. Estado del Ciclo de Vida
        def lifecycle(row):
            if row['Stock Actual'] == 0 and row['Venta Diaria Prom'] > 0.1: return "🚨 QUIEBRE (Sin Stock)"
            if row['Clasificación ABC'] == 'A (Core)' and row['Cobertura (Días)'] < 20: return "⚠️ Riesgo Quiebre"
            if row['Cobertura (Días)'] > 180 and row['Valor Inventario'] > 1000: return "💀 Obsoleto/Lento"
            if row['Cobertura (Días)'] > 90 and row['Clasificación ABC'] == 'C (Cola)': return "📉 Sobre-Stock"
            return "✅ Saludable"
        
        self.df['Estado'] = self.df.apply(lifecycle, axis=1)

    def get_purchasing_plan(self, target_days=45):
        """Genera plan de compras editable."""
        df_buy = self.df.copy()
        
        # Lógica: Stock Seguridad + (Venta Diaria * Lead Time) + (Venta Diaria * Dias Objetivo) - Stock Actual
        df_buy['Stock Seguridad'] = df_buy['Venta Diaria Prom'] * 10 # 10 días colchón
        df_buy['Punto Reorden'] = (df_buy['Venta Diaria Prom'] * df_buy['Lead Time (Días)']) + df_buy['Stock Seguridad']
        df_buy['Stock Objetivo'] = df_buy['Venta Diaria Prom'] * target_days
        
        # Cantidad sugerida bruta
        df_buy['Sugerido Sistema'] = (df_buy['Stock Objetivo'] + df_buy['Punto Reorden'] - df_buy['Stock Actual']).clip(lower=0)
        df_buy['Sugerido Sistema'] = df_buy['Sugerido Sistema'].apply(np.ceil) # Redondear hacia arriba
        
        # Filtramos solo lo que necesita compra
        df_buy = df_buy[df_buy['Sugerido Sistema'] > 0].sort_values('Clasificación ABC')
        
        # Columnas para el editor (Usuario final)
        df_buy['Confirmar Compra'] = False # Checkbox
        df_buy['Cantidad a Pedir'] = df_buy['Sugerido Sistema'] # Editable
        
        return df_buy

# --- 6. INTERFAZ DE USUARIO PRINCIPAL ---

def main():
    # --- HEADER & SIDEBAR ---
    with st.sidebar:
        st.title("NEXUS PRO v2.0")
        st.markdown("---")
        st.caption("PARAMETROS DEL SISTEMA")
        
        dias_analisis = st.slider("📅 Ventana Histórica (Días)", 30, 365, 90)
        dias_cobertura = st.number_input("🎯 Objetivo Cobertura (Días)", min_value=15, value=45)
        
        st.markdown("---")
        st.caption("FILTROS GLOBALES")
        
        # Carga Inicial
        df_raw = get_data_engine()
        
        f_cats = st.multiselect("Categoría", df_raw['Categoría'].unique(), default=df_raw['Categoría'].unique())
        f_locs = st.multiselect("Ubicación", df_raw['Ubicación'].unique(), default=df_raw['Ubicación'].unique())
        
        st.markdown("---")
        st.info("💡 Modo Edición Habilitado\nLos cambios en tablas afectan los cálculos de totales en tiempo real.")

    # --- FILTRADO Y PROCESAMIENTO ---
    df_filtered = df_raw[
        (df_raw['Categoría'].isin(f_cats)) & 
        (df_raw['Ubicación'].isin(f_locs))
    ]
    
    # Instanciar Motor BI
    engine = NexusIntelligence(df_filtered, dias_analisis)
    df_final = engine.df

    # --- KPI SECTION (TOP ROW) ---
    st.markdown(f"## 🚀 Tablero de Comando | {pd.to_datetime('today').strftime('%Y-%m-%d')}")
    
    kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
    
    total_inv = df_final['Valor Inventario'].sum()
    total_sales = df_final['Venta Total ($)'].sum()
    margin_avg = df_final['GMROI'].mean()
    sku_count = len(df_final)
    critical_stock = len(df_final[df_final['Estado'].str.contains("QUIEBRE")])

    with kpi1: st.metric("Valor Inventario", format_currency(total_inv), delta="2.4%")
    with kpi2: st.metric("Venta Periodo", format_currency(total_sales), delta="12%")
    with kpi3: st.metric("Rentabilidad (GMROI)", f"{margin_avg:.2f}", delta="-0.5")
    with kpi4: st.metric("SKUs Activos", format_number(sku_count))
    with kpi5: st.metric("Alertas Quiebre", str(critical_stock), delta="-3", delta_color="inverse")

    st.markdown("---")

    # --- TABS DE NAVEGACIÓN ---
    tab_dashboard, tab_compras, tab_traslados, tab_data = st.tabs([
        "📊 Inteligencia de Mercado", 
        "🛒 Planeación de Compras (Editable)", 
        "🚚 Logística & Distribución",
        "🔎 Explorador de Datos"
    ])

    # ------------------------------------------------------------------
    # TAB 1: DASHBOARD VISUAL
    # ------------------------------------------------------------------
    with tab_dashboard:
        col_charts_1, col_charts_2 = st.columns([2, 1])
        
        with col_charts_1:
            st.markdown("### 📈 Matriz de Desempeño (Stock vs Rentabilidad)")
            fig_scatter = px.scatter(
                df_final, 
                x="Cobertura (Días)", 
                y="GMROI", 
                size="Valor Inventario", 
                color="Clasificación ABC",
                hover_name="Producto",
                log_x=True,
                color_discrete_map={'A (Core)': '#22c55e', 'B (Regular)': '#f59e0b', 'C (Cola)': '#ef4444'},
                height=450
            )
            fig_scatter.add_vline(x=90, line_dash="dot", line_color="gray", annotation_text="Límite Obsolescencia")
            fig_scatter.add_hline(y=1.5, line_dash="dot", line_color="gray", annotation_text="Objetivo GMROI")
            st.plotly_chart(fig_scatter, use_container_width=True)

        with col_charts_2:
            st.markdown("### 🥧 Distribución Valorizada")
            fig_pie = px.pie(
                df_final, 
                names='Estado', 
                values='Valor Inventario', 
                hole=0.4,
                color_discrete_sequence=px.colors.qualitative.Prism
            )
            fig_pie.update_layout(showlegend=False, height=450)
            st.plotly_chart(fig_pie, use_container_width=True)

    # ------------------------------------------------------------------
    # TAB 2: COMPRAS INTERACTIVAS (CORE FEATURE)
    # ------------------------------------------------------------------
    with tab_compras:
        st.markdown("### 📝 Generador de Órdenes de Compra")
        st.caption("Seleccione los productos ('Confirmar Compra') y ajuste la 'Cantidad a Pedir' según su criterio experto.")
        
        # Obtener sugerencias base
        df_suggestions = engine.get_purchasing_plan(target_days=dias_cobertura)
        
        # CONFIGURACIÓN DEL EDITOR DE DATOS
        edited_df = st.data_editor(
            df_suggestions[[
                'Confirmar Compra', 'SKU', 'Producto', 'Proveedor', 'Clasificación ABC', 
                'Stock Actual', 'Venta Diaria Prom', 'Lead Time (Días)', 
                'Sugerido Sistema', 'Cantidad a Pedir', 'Costo Unitario'
            ]],
            column_config={
                "Confirmar Compra": st.column_config.CheckboxColumn(
                    "Seleccionar",
                    help="Marcar para incluir en la Orden de Compra",
                    default=False,
                ),
                "Cantidad a Pedir": st.column_config.NumberColumn(
                    "Cant. Final",
                    help="Modifique este valor si desea ajustar la sugerencia del sistema",
                    min_value=1,
                    step=1,
                    format="%d"
                ),
                "Costo Unitario": st.column_config.NumberColumn(format="$ %.2f"),
                "Venta Diaria Prom": st.column_config.NumberColumn(format="%.2f"),
                "Sugerido Sistema": st.column_config.NumberColumn(disabled=True) # Campo solo lectura para referencia
            },
            use_container_width=True,
            height=500,
            hide_index=True,
            key="editor_compras" # Key único para mantener estado
        )
        
        # CÁLCULOS DINÁMICOS SOBRE LA TABLA EDITADA
        # Filtramos solo lo que el usuario seleccionó
        items_seleccionados = edited_df[edited_df['Confirmar Compra'] == True].copy()
        
        if not items_seleccionados.empty:
            items_seleccionados['Total Línea'] = items_seleccionados['Cantidad a Pedir'] * items_seleccionados['Costo Unitario']
            total_inversion = items_seleccionados['Total Línea'].sum()
            total_unidades = items_seleccionados['Cantidad a Pedir'].sum()
            proveedores_count = items_seleccionados['Proveedor'].nunique()
            
            st.markdown("---")
            c1, c2, c3, c4 = st.columns([2, 2, 2, 2])
            with c1: 
                st.metric("💰 Inversión Total Aprobada", format_currency(total_inversion))
            with c2: 
                st.metric("📦 Unidades a Pedir", format_number(total_unidades))
            with c3:
                st.metric("🏭 Proveedores", str(proveedores_count))
            with c4:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("✅ GENERAR ORDEN DE COMPRA", type="primary", use_container_width=True):
                    with st.spinner("Procesando orden con ERP..."):
                        time.sleep(1.5) # Simulación proceso
                    st.success(f"Orden generada exitosamente por {format_currency(total_inversion)}")
                    st.balloons()
                    
                    # Preview de descarga
                    csv = items_seleccionados.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="📥 Descargar CSV para ERP",
                        data=csv,
                        file_name='orden_compra_nexus.csv',
                        mime='text/csv',
                    )
        else:
            st.info("👋 Seleccione productos en la columna 'Seleccionar' para calcular la inversión.")

    # ------------------------------------------------------------------
    # TAB 3: LOGÍSTICA (TRASLADOS)
    # ------------------------------------------------------------------
    with tab_traslados:
        st.markdown("### 🔄 Balanceo de Inventario (Inter-Sucursales)")
        
        # Identificar Excesos y Faltantes
        overstock = df_final[df_final['Estado'] == "📉 Sobre-Stock"].copy()
        lowstock = df_final[df_final['Estado'].isin(["🚨 QUIEBRE (Sin Stock)", "⚠️ Riesgo Quiebre"])].copy()
        
        col_log1, col_log2 = st.columns(2)
        
        with col_log1:
            st.error(f"📍 Puntos Críticos (Necesitan Stock): {len(lowstock)} SKUs")
            st.dataframe(
                lowstock[['SKU', 'Producto', 'Ubicación', 'Stock Actual', 'Venta Diaria Prom']], 
                use_container_width=True, 
                height=300,
                hide_index=True
            )
            
        with col_log2:
            st.warning(f"📦 Excesos Disponibles para Traslado: {len(overstock)} SKUs")
            st.dataframe(
                overstock[['SKU', 'Producto', 'Ubicación', 'Stock Actual', 'Cobertura (Días)']], 
                use_container_width=True, 
                height=300,
                hide_index=True
            )
        
        st.markdown("#### 🛠️ Creador de Manifiesto de Traslado")
        # Simulación de una herramienta de drag-and-drop simple con data_editor
        if not overstock.empty:
            df_traslado = overstock.head(10).copy() # Tomamos top 10 candidatos
            df_traslado['Destino Sugerido'] = "Tienda Principal" # Default
            df_traslado['Cantidad a Mover'] = (df_traslado['Stock Actual'] * 0.2).astype(int)
            
            st.data_editor(
                df_traslado[['SKU', 'Producto', 'Ubicación', 'Destino Sugerido', 'Cantidad a Mover']],
                column_config={
                    "Destino Sugerido": st.column_config.SelectboxColumn(
                        "Ubicación Destino",
                        options=list(df_raw['Ubicación'].unique()),  # <-- aquí el cambio
                        required=True
                    ),
                    "Cantidad a Mover": st.column_config.NumberColumn(min_value=1)
                },
                use_container_width=True,
                hide_index=True,
                key="editor_traslados"
            )
            st.button("🚛 Confirmar Traslados", type="secondary")

    # ------------------------------------------------------------------
    # TAB 4: DATA EXPLORER
    # ------------------------------------------------------------------
    with tab_data:
        st.markdown("### 🔎 Base de Datos Maestra")
        
        # Buscador en tiempo real
        col_search, col_down = st.columns([4, 1])
        with col_search:
            search_term = st.text_input("🔍 Buscar SKU o Producto...", placeholder="Escriba aquí...")
        
        if search_term:
            df_display = df_final[
                df_final['Producto'].str.contains(search_term, case=False) | 
                df_final['SKU'].str.contains(search_term, case=False)
            ]
        else:
            df_display = df_final
            
        st.dataframe(
            df_display,
            column_config={
                "Valor Inventario": st.column_config.NumberColumn(format="$ %.2f"),
                "Venta Total ($)": st.column_config.NumberColumn(format="$ %.2f"),
                "Margen ($)": st.column_config.NumberColumn(format="$ %.2f"),
                "GMROI": st.column_config.NumberColumn(format="%.2f x"),
            },
            use_container_width=True,
            height=600,
            hide_index=True
        )
        
        with col_down:
            st.markdown("<br>", unsafe_allow_html=True)
            st.download_button(
                "📥 Exportar Excel",
                data=df_display.to_csv(index=False).encode('utf-8'),
                file_name="nexus_full_data.csv",
                mime='text/csv'
            )

if __name__ == "__main__":
    main()