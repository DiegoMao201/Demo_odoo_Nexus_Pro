import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from odoo_client import OdooConnector
import time

# Configuración de página
st.set_page_config(page_title="GM-DATOVATE | Super BI Odoo", layout="wide", page_icon="📊")

# --- ESTILOS CSS ---
st.markdown("""
<style>
    .metric-card {background-color: #f0f2f6; padding: 20px; border-radius: 10px; border-left: 5px solid #4CAF50;}
    .alert-card {background-color: #ffebee; padding: 15px; border-radius: 5px; border: 1px solid #ffcdd2;}
</style>
""", unsafe_allow_html=True)

# --- FUNCIÓN DE CARGA DE DATOS (CON CACHÉ) ---
@st.cache_data(ttl=300) # Se actualiza cada 5 minutos
def load_data():
    connector = OdooConnector()
    
    with st.spinner('Conectando al núcleo de Odoo... Extrayendo Productos...'):
        df_prod = connector.get_products_detailed()
        
    with st.spinner('Analizando Bodegas (Stock Quant)...'):
        df_stock = connector.get_stock_quants()
        
    with st.spinner('Procesando Histórico de Ventas...'):
        df_sales = connector.get_sales_lines()

    return df_prod, df_stock, df_sales

# --- LÓGICA DE NEGOCIO (EL CEREBRO) ---
def process_data(df_prod, df_stock, df_sales):
    # 1. Enriquecer Stock con datos del producto (Costo, Precio, Categoría)
    # Hacemos merge left para mantener el stock aunque falten datos maestros
    df_stock_full = pd.merge(df_stock, df_prod, on='product_id', how='left')
    
    # Calcular valoración real del inventario
    df_stock_full['valor_inventario_costo'] = df_stock_full['stock_real_ubicacion'] * df_stock_full['standard_price']
    df_stock_full['valor_inventario_venta'] = df_stock_full['stock_real_ubicacion'] * df_stock_full['list_price']

    # 2. Análisis de Ventas por Producto
    sales_summary = df_sales.groupby('product_id').agg({
        'qty_sold': 'sum',
        'revenue': 'sum',
        'date': 'max' # Última fecha de venta
    }).reset_index()
    
    # Calcular venta diaria promedio (asumiendo historial completo cargado, ajustar según filtro fecha)
    dias_analisis = (df_sales['date'].max() - df_sales['date'].min()).days
    if dias_analisis == 0: dias_analisis = 1
    sales_summary['venta_diaria_promedio'] = sales_summary['qty_sold'] / dias_analisis

    # 3. MASTER DATA: Unimos todo en un gran DataFrame Maestro
    df_master = pd.merge(df_prod, sales_summary, on='product_id', how='left')
    df_master['qty_sold'] = df_master['qty_sold'].fillna(0)
    df_master['revenue'] = df_master['revenue'].fillna(0)
    df_master['venta_diaria_promedio'] = df_master['venta_diaria_promedio'].fillna(0)

    # 4. Cálculo de KPIs avanzados
    # Días de Inventario (DOI) = Stock Actual / Venta Diaria
    df_master['dias_inventario'] = df_master.apply(
        lambda row: row['stock_total_teorico'] / row['venta_diaria_promedio'] if row['venta_diaria_promedio'] > 0 else 999, axis=1
    )
    
    # Clasificación de Estado
    def clasificar_stock(row):
        if row['stock_total_teorico'] <= 0: return "Agotado"
        if row['dias_inventario'] < 7: return "Crítico (Reabastecer)"
        if row['dias_inventario'] > 90: return "Sobre-stock"
        return "Saludable"
    
    df_master['estado_inventario'] = df_master.apply(clasificar_stock, axis=1)

    return df_master, df_stock_full, df_sales

# --- INTERFAZ DE USUARIO ---

try:
    df_prod, df_stock, df_sales = load_data()
    
    # Procesar lógica
    df_master, df_stock_full, df_sales_raw = process_data(df_prod, df_stock, df_sales)

    # Sidebar: Filtros Globales
    st.sidebar.title("🎛️ Panel de Control")
    st.sidebar.image("https://cdn-icons-png.flaticon.com/512/2892/2892591.png", width=100) # Placeholder logo
    
    categorias = ['Todas'] + list(df_master['categ_name'].unique())
    filtro_categ = st.sidebar.selectbox("Filtrar por Categoría", categorias)
    
    if filtro_categ != 'Todas':
        df_master = df_master[df_master['categ_name'] == filtro_categ]
        df_stock_full = df_stock_full[df_stock_full['categ_name'] == filtro_categ]

    # --- HEADER ---
    st.title("🚀 Dashboard de Inteligencia de Negocios Odoo")
    st.markdown("Vista unificada de Inventario, Ventas y Sugerencias de IA")
    st.markdown("---")

    # --- TABS ---
    tab1, tab2, tab3, tab4 = st.tabs(["📊 KPIs Generales", "📦 Análisis de Inventario", "🚚 Sugerencias de Traslado", "🛒 Sugerencias de Compra"])

    # === TAB 1: KPIs GENERALES ===
    with tab1:
        col1, col2, col3, col4 = st.columns(4)
        
        total_ventas = df_sales_raw['revenue'].sum()
        total_costo_inv = df_stock_full['valor_inventario_costo'].sum()
        total_items = df_stock_full['stock_real_ubicacion'].sum()
        margen_promedio = ((df_master['list_price'] - df_master['standard_price']) / df_master['list_price']).mean() * 100

        col1.metric("Ventas Totales (Periodo)", f"${total_ventas:,.0f}")
        col2.metric("Valor Inventario (Costo)", f"${total_costo_inv:,.0f}")
        col3.metric("Unidades en Stock", f"{total_items:,.0f}")
        col4.metric("Margen Teórico Promedio", f"{margen_promedio:.1f}%")

        st.subheader("Tendencia de Ventas")
        # Agrupar ventas por día
        ventas_diarias = df_sales_raw.groupby(df_sales_raw['date'].dt.date)['revenue'].sum().reset_index()
        fig_ventas = px.line(ventas_diarias, x='date', y='revenue', title="Evolución de Ingresos Diarios", markers=True)
        st.plotly_chart(fig_ventas, use_container_width=True)

        col_a, col_b = st.columns(2)
        with col_a:
            st.subheader("Top 10 Productos Más Vendidos ($)")
            top_prods = df_master.nlargest(10, 'revenue')
            fig_bar = px.bar(top_prods, x='revenue', y='name', orientation='h', color='revenue', title="Top Productos por Ingresos")
            st.plotly_chart(fig_bar, use_container_width=True)
            
        with col_b:
            st.subheader("Distribución de Inventario por Categoría")
            pie_data = df_stock_full.groupby('categ_name')['valor_inventario_costo'].sum().reset_index()
            fig_pie = px.pie(pie_data, values='valor_inventario_costo', names='categ_name', title="Valor de Inventario por Categoría")
            st.plotly_chart(fig_pie, use_container_width=True)

    # === TAB 2: ANÁLISIS DE INVENTARIO ===
    with tab2:
        st.header("Salud del Inventario")
        
        # Filtros rápidos
        col_f1, col_f2 = st.columns(2)
        ver_agotados = col_f1.checkbox("Ver solo Agotados")
        ver_sobrestock = col_f2.checkbox("Ver solo Sobre-stock (>90 días)")
        
        df_view = df_master.copy()
        if ver_agotados:
            df_view = df_view[df_view['stock_total_teorico'] <= 0]
        if ver_sobrestock:
            df_view = df_view[df_view['dias_inventario'] > 90]

        # Tabla Interactiva
        st.dataframe(
            df_view[['default_code', 'name', 'categ_name', 'stock_total_teorico', 'venta_diaria_promedio', 'dias_inventario', 'estado_inventario']],
            column_config={
                "dias_inventario": st.column_config.NumberColumn("Días Cobertura", format="%.1f días"),
                "venta_diaria_promedio": st.column_config.NumberColumn("Rotación Diaria", format="%.2f u/día"),
                "stock_total_teorico": st.column_config.NumberColumn("Stock Total"),
            },
            use_container_width=True,
            hide_index=True
        )
        
        st.info("💡 **Tips:** 'Días Cobertura' indica cuánto durará tu stock actual al ritmo de ventas actual. Si es infinito (999), es porque el producto no rota.")

    # === TAB 3: SUGERENCIAS DE TRASLADO (INTELIGENCIA) ===
    with tab3:
        st.header("🚚 Optimización Multi-Bodega")
        st.markdown("El sistema busca productos que estén **agotados en una ubicación** pero tengan **exceso en otra**.")
        
        # Algoritmo de Sugerencia de Traslado
        # 1. Pivotear stock por ubicación
        stock_pivot = df_stock_full.pivot_table(index=['product_id', 'name', 'default_code'], columns='location_name', values='stock_real_ubicacion', fill_value=0).reset_index()
        
        # Obtenemos lista de bodegas
        bodegas = [c for c in stock_pivot.columns if c not in ['product_id', 'name', 'default_code']]
        
        if len(bodegas) < 2:
            st.warning("⚠️ Necesitas al menos 2 ubicaciones/bodegas internas con stock para sugerir traslados.")
        else:
            sugerencias = []
            
            # Recorremos productos
            for index, row in stock_pivot.iterrows():
                for bodega_origen in bodegas:
                    for bodega_destino in bodegas:
                        if bodega_origen == bodega_destino: continue
                        
                        qty_origen = row[bodega_origen]
                        qty_destino = row[bodega_destino]
                        
                        # LOGICA: Si origen tiene mucho (>10) y destino tiene 0 o muy poco (<2)
                        if qty_origen > 10 and qty_destino < 2:
                            sugerencias.append({
                                'Producto': row['name'],
                                'Ref': row['default_code'],
                                'Desde (Origen)': bodega_origen,
                                'Hacia (Destino)': bodega_destino,
                                'Cantidad a Mover': int(qty_origen * 0.2), # Sugerir mover el 20%
                                'Stock Origen': qty_origen,
                                'Stock Destino': qty_destino
                            })
            
            if sugerencias:
                df_sugerencias = pd.DataFrame(sugerencias)
                st.success(f"✅ Se encontraron {len(df_sugerencias)} oportunidades de balanceo de inventario.")
                st.dataframe(df_sugerencias, use_container_width=True)
            else:
                st.info("El inventario parece estar bien balanceado entre bodegas.")

    # === TAB 4: SUGERENCIAS DE COMPRA ===
    with tab4:
        st.header("🛒 Reabastecimiento Inteligente")
        
        # Lógica: Productos con stock < punto de reorden (asumamos 5 por defecto o basado en venta)
        # Sugerencia = (Venta Diaria * 30 días) - Stock Actual
        
        compras_df = df_master.copy()
        
        # Calculamos Stock Ideal para 30 días
        compras_df['stock_ideal'] = compras_df['venta_diaria_promedio'] * 30
        compras_df['cantidad_sugerida'] = compras_df['stock_ideal'] - compras_df['stock_total_teorico']
        
        # Filtramos solo los que necesitan compra positiva y tienen rotación
        filtro_compras = (compras_df['cantidad_sugerida'] > 0) & (compras_df['venta_diaria_promedio'] > 0)
        df_a_comprar = compras_df[filtro_compras].sort_values(by='cantidad_sugerida', ascending=False)
        
        # Costo estimado de la compra
        df_a_comprar['inversion_estimada'] = df_a_comprar['cantidad_sugerida'] * df_a_comprar['standard_price']
        
        total_inversion = df_a_comprar['inversion_estimada'].sum()
        
        st.metric("Inversión Requerida para 30 días de Stock", f"${total_inversion:,.0f}")
        
        st.dataframe(
            df_a_comprar[['default_code', 'name', 'x_studio_ref_madre', 'stock_total_teorico', 'venta_diaria_promedio', 'cantidad_sugerida', 'standard_price', 'inversion_estimada']],
             column_config={
                "venta_diaria_promedio": st.column_config.NumberColumn("Venta/Día", format="%.2f"),
                "cantidad_sugerida": st.column_config.NumberColumn("A Pedir", format="%.0f u"),
                "inversion_estimada": st.column_config.NumberColumn("Costo Estimado", format="$ %.2f"),
            },
            hide_index=True,
            use_container_width=True
        )

except Exception as e:
    st.error(f"Ocurrió un error en la ejecución del dashboard: {e}")
    st.write("Detalle técnico:", e)