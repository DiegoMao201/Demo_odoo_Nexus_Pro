import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np
from odoo_client import OdooConnector

# --- CONFIGURACIÓN DE PÁGINA Y ESTILOS ---
st.set_page_config(
    page_title="NEXUS PRO v3.0 | Centro de Comando Estratégico",
    layout="wide",
    page_icon="💎",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;800&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .stApp { background-color: #f0f2f6; }
    h1, h2, h3 { color: #1e293b; font-weight: 800; letter-spacing: -0.5px; }
    .stTabs [data-baseweb="tab-list"] { gap: 12px; }
    .stTabs [data-baseweb="tab"] {
        height: 48px; background-color: #ffffff; border-radius: 8px; font-weight: 600;
        color: #475569; border: 1px solid #e2e8f0; padding: 0 24px; box-shadow: 0 1px 2px rgba(0,0,0,0.05);
    }
    .stTabs [aria-selected="true"] { background-color: #2563eb; color: #ffffff !important; border-color: #2563eb; }
    div[data-testid="metric-container"] {
        background-color: #ffffff; border: 1px solid #e2e8f0; padding: 20px;
        border-radius: 12px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);
    }
    .block-container { padding-top: 2rem; padding-bottom: 3rem; }
</style>
""", unsafe_allow_html=True)

def format_currency(value):
    return f"$ {value:,.0f}"

def format_number(value):
    return f"{value:,.0f}"

def format_percent(value):
    return f"{value:.1%}"

# --- MOTOR DE INTELIGENCIA DE NEGOCIO v3.0 ---
def process_business_logic(df_stock, df_sales, df_product, df_location, dias_analisis):
    # 1. MAPAS DE ENRIQUECIMIENTO
    prod_map = {p['id']: {'name': p['name'], 'cost': p.get('standard_price', 0)} for _, p in df_product.iterrows()}
    loc_map = dict(zip(df_location['id'], df_location['name']))

    # 2. ENRIQUECER DATAFRAMES
    df_stock['product_name'] = df_stock['product_id'].map(lambda x: prod_map.get(x, {}).get('name'))
    df_stock['cost_unit'] = df_stock['product_id'].map(lambda x: prod_map.get(x, {}).get('cost', 0))
    df_stock['capital_inmovilizado'] = df_stock['quantity'] * df_stock['cost_unit']
    df_stock['location_name'] = df_stock['location_id'].map(loc_map)

    df_sales['product_name'] = df_sales['product_id'].map(lambda x: prod_map.get(x, {}).get('name'))
    df_sales['cost_unit'] = df_sales['product_id'].map(lambda x: prod_map.get(x, {}).get('cost', 0))
    df_sales['cost_of_goods_sold'] = df_sales['qty_sold'] * df_sales['cost_unit']
    df_sales['gross_margin'] = df_sales['revenue'] - df_sales['cost_of_goods_sold']

    # 3. AGREGADOS POR PRODUCTO
    stock_gb = df_stock.groupby('product_id', as_index=False).agg(
        quantity=('quantity', 'sum'),
        capital_inmovilizado=('capital_inmovilizado', 'sum')
    )
    ventas_gb = df_sales.groupby('product_id', as_index=False).agg(
        qty_sold=('qty_sold', 'sum'),
        revenue=('revenue', 'sum'),
        gross_margin=('gross_margin', 'sum'),
        sales_std_dev=('qty_sold', 'std') # Para análisis XYZ
    )
    ventas_gb['sales_std_dev'] = ventas_gb['sales_std_dev'].fillna(0)

    # 4. MERGE FINAL Y KPIs BÁSICOS
    df_final = pd.merge(stock_gb, ventas_gb, on='product_id', how='outer').fillna(0)
    df_final['product_name'] = df_final['product_id'].map(lambda x: prod_map.get(x, {}).get('name'))
    df_final['cost_unit'] = df_final['product_id'].map(lambda x: prod_map.get(x, {}).get('cost', 0))
    df_final.dropna(subset=['product_name'], inplace=True)

    df_final['rotacion_diaria'] = df_final['qty_sold'] / dias_analisis
    df_final['cobertura_dias'] = df_final['quantity'] / df_final['rotacion_diaria'].replace(0, np.nan)
    df_final['cobertura_dias'] = df_final['cobertura_dias'].replace([np.inf, -np.inf], 999).fillna(999)
    df_final['sell_through_rate'] = df_final['qty_sold'] / (df_final['qty_sold'] + df_final['quantity']).replace(0, np.nan)
    df_final['gmroi'] = df_final['gross_margin'] / df_final['capital_inmovilizado'].replace(0, np.nan)

    # 5. ANÁLISIS ABC (Basado en Ingresos)
    df_final = df_final.sort_values(by='revenue', ascending=False)
    df_final['revenue_cumsum'] = df_final['revenue'].cumsum()
    total_revenue = df_final['revenue'].sum()
    df_final['revenue_share'] = df_final['revenue_cumsum'] / total_revenue
    df_final['abc_class'] = np.where(df_final['revenue_share'] <= 0.8, 'A',
                                   np.where(df_final['revenue_share'] <= 0.95, 'B', 'C'))

    # 6. ANÁLISIS XYZ (Basado en Volatilidad de Ventas)
    cv_threshold_y = 0.5 # Coeficiente de variación
    cv_threshold_z = 1.0
    mean_sales = df_final['qty_sold'].mean()
    df_final['coeff_variation'] = df_final['sales_std_dev'] / mean_sales
    df_final['xyz_class'] = np.where(df_final['coeff_variation'] <= cv_threshold_y, 'X',
                                   np.where(df_final['coeff_variation'] <= cv_threshold_z, 'Y', 'Z'))

    df_final['abc_xyz_class'] = df_final['abc_class'] + df_final['xyz_class']

    # 7. DIAGNÓSTICO ESTRATÉGICO MEJORADO
    def diagnostico_estrategico(row):
        clase = row['abc_xyz_class']
        cobertura = row['cobertura_dias']
        stock = row['quantity']
        ventas = row['qty_sold']

        if stock <= 0 and ventas > 0: return "QUIEBRE DE STOCK"
        if clase in ['AX', 'AY', 'BX'] and cobertura < 15: return "RIESGO ALTO: COMPRA URGENTE"
        if clase in ['AZ', 'BY', 'CX'] and cobertura < 7: return "RIESGO MEDIO: REVISAR STOCK"
        if clase in ['CZ', 'CY'] and cobertura > 180: return "EXCESO CRÍTICO: LIQUIDAR"
        if cobertura > 365: return "INVENTARIO OBSOLETO"
        return "GESTIÓN SALUDABLE"
    df_final['diagnostico'] = df_final.apply(diagnostico_estrategico, axis=1)

    # 8. SUGERENCIAS ACCIONABLES
    compras = df_final[df_final['diagnostico'].str.contains("COMPRA|RIESGO")].copy()
    compras['cantidad_sugerida'] = (compras['rotacion_diaria'] * 30 - compras['quantity']).clip(lower=1).astype(int)

    traslados_df = df_stock.groupby(['product_id', 'location_id', 'location_name']).agg(quantity=('quantity', 'sum')).reset_index()
    traslados_df['product_name'] = traslados_df['product_id'].map(lambda x: prod_map.get(x, {}).get('name'))
    traslados_df = pd.merge(traslados_df, df_final[['product_id', 'cobertura_dias']], on='product_id')

    sugerencias_traslado = []
    for prod_id in traslados_df['product_id'].unique():
        prod_locations = traslados_df[traslados_df['product_id'] == prod_id]
        exceso_locs = prod_locations[prod_locations['quantity'] > (prod_locations['quantity'].mean() * 1.5)]
        quiebre_locs = prod_locations[prod_locations['quantity'] == 0]
        if not exceso_locs.empty and not quiebre_locs.empty:
            de = exceso_locs.iloc[0]
            a = quiebre_locs.iloc[0]
            sugerencias_traslado.append({
                'Producto': de['product_name'],
                'Desde (Tienda)': de['location_name'],
                'Stock Origen': de['quantity'],
                'Hacia (Tienda)': a['location_name'],
                'Cantidad a Mover': int(max(1, de['quantity'] * 0.25))
            })
    df_traslados = pd.DataFrame(sugerencias_traslado)

    return {
        'kpi': df_final,
        'traslados': df_traslados,
        'compras': compras
    }

# --- INTERFAZ DE USUARIO (DASHBOARD) ---
def main():
    st.markdown(f"## 💎 **NEXUS PRO v3.0** | Centro de Comando Estratégico")
    st.markdown(f"_{pd.to_datetime('today').strftime('%A, %d de %B de %Y')} | Datos en vivo desde Odoo_")

    with st.sidebar:
        st.title("Configuración de Análisis")
        dias_analisis = st.slider("📅 Ventana Histórica (Días)", 30, 365, 90, help="Define el período para calcular la rotación y la demanda.")
        st.info("Este tablero utiliza análisis ABC-XYZ para una gestión de inventario inteligente y proactiva.")

    # Carga de datos
    try:
        connector = OdooConnector()
        with st.spinner("Conectando con Odoo y extrayendo datos maestros..."):
            df_stock = connector.get_stock_data()
            df_sales = connector.get_sales_data()
            df_product = connector.get_product_data()
            df_location = connector.get_location_data()
    except Exception as e:
        st.error(f"Error fatal al conectar o cargar datos de Odoo: {e}")
        st.stop()

    if df_stock.empty or df_sales.empty or df_product.empty:
        st.error("No se encontraron datos suficientes en Odoo (stock, ventas o productos) para realizar el análisis.")
        st.stop()

    # Procesamiento
    with st.spinner("Aplicando inteligencia de negocio..."):
        bi = process_business_logic(df_stock, df_sales, df_product, df_location, dias_analisis)
        df_final = bi['kpi']

    # --- PESTAÑAS DEL DASHBOARD ---
    tab_general, tab_abc_xyz, tab_acciones = st.tabs([
        "📈 **Visión General**",
        "🧩 **Matriz Estratégica ABC-XYZ**",
        "🎯 **Plan de Acción**"
    ])

    with tab_general:
        st.subheader("Indicadores Clave de Rendimiento (KPIs)")
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("💰 Valor Total del Inventario", format_currency(df_final['capital_inmovilizado'].sum()))
        k2.metric("🔄 Sell-Through Rate Promedio", format_percent(df_final['sell_through_rate'].mean()), help="Porcentaje de inventario vendido en el período.")
        k3.metric("📈 GMROI Promedio", f"{df_final['gmroi'].mean():.2f}x", help="Ganancia Bruta por cada dólar invertido en inventario.")
        k4.metric("📦 SKUs Analizados", format_number(len(df_final)))

        st.markdown("---")
        col1, col2 = st.columns([3, 2])
        with col1:
            st.markdown("#### Cobertura vs. Rotación por Diagnóstico")
            df_final['bubble_size'] = df_final['quantity'].clip(lower=0)
            fig_scatter = px.scatter(
                df_final, x="cobertura_dias", y="rotacion_diaria", size="bubble_size", color="diagnostico",
                hover_name="product_name", size_max=50, height=450,
                labels={"cobertura_dias": "Cobertura (Días)", "rotacion_diaria": "Rotación (Unidades/Día)"}
            )
            st.plotly_chart(fig_scatter, use_container_width=True)
        with col2:
            st.markdown("#### Valor de Inventario por Diagnóstico")
            fig_pie = px.pie(df_final, names='diagnostico', values='capital_inmovilizado', hole=0.5, height=450)
            st.plotly_chart(fig_pie, use_container_width=True)

    with tab_abc_xyz:
        st.subheader("Matriz de Decisión Estratégica ABC-XYZ")
        st.info("Clasifica tus productos para enfocar tus esfuerzos. **A**: Más importantes (80% ingresos). **X**: Demanda más estable.")

        # Crear la matriz para el heatmap
        matrix = df_final.pivot_table(index='abc_class', columns='xyz_class', values='product_id', aggfunc='count').fillna(0)
        matrix = matrix.reindex(index=['A', 'B', 'C'], columns=['X', 'Y', 'Z'])

        fig_matrix = px.imshow(matrix, text_auto=True, aspect="auto", height=500,
                               labels=dict(x="Clase XYZ (Volatilidad)", y="Clase ABC (Importancia)", color="Nº de Productos"),
                               color_continuous_scale=px.colors.sequential.Blues)
        fig_matrix.update_layout(title_text='Cantidad de Productos por Estrategia', title_x=0.5)
        st.plotly_chart(fig_matrix, use_container_width=True)

        st.markdown("#### Explorar Productos por Estrategia")
        selected_class = st.selectbox("Selecciona una clase estratégica para ver los productos:", df_final['abc_xyz_class'].unique())
        st.dataframe(df_final[df_final['abc_xyz_class'] == selected_class][[
            'product_name', 'abc_xyz_class', 'diagnostico', 'quantity', 'cobertura_dias', 'revenue'
        ]].rename(columns={'product_name':'Producto', 'quantity':'Stock', 'revenue':'Ingresos', 'cobertura_dias':'Cobertura (días)'}), use_container_width=True)

    with tab_acciones:
        st.subheader("🎯 Plan de Acción Priorizado")
        st.markdown("Decisiones automáticas basadas en el análisis para optimizar tu inventario.")

        st.markdown("#### 🛒 **Sugerencias de Compra Urgente**")
        st.warning("Estos productos son críticos o están en riesgo de quiebre. Prioriza su reposición.")
        df_compras = bi['compras']
        st.dataframe(df_compras[['product_name', 'abc_xyz_class', 'quantity', 'rotacion_diaria', 'cantidad_sugerida']].rename(columns={
            'product_name':'Producto', 'abc_xyz_class':'Clase', 'quantity':'Stock Actual', 'rotacion_diaria':'Venta Diaria', 'cantidad_sugerida':'Compra Sugerida'
        }), use_container_width=True)

        st.markdown("#### 🚚 **Sugerencias de Traslado entre Tiendas**")
        st.info("Mueve inventario desde ubicaciones con exceso hacia aquellas con quiebre para balancear el stock y evitar ventas perdidas.")
        df_traslados = bi['traslados']
        if not df_traslados.empty:
            st.dataframe(df_traslados, use_container_width=True)
        else:
            st.success("¡Balance perfecto! No se sugieren traslados por el momento.")

if __name__ == "__main__":
    main()