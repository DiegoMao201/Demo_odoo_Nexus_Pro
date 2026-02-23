import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from odoo_client import OdooConnector # Asegúrate que el archivo se llame odoo_client.py
import io
import time

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="GM-DATOVATE | Super BI Odoo", layout="wide", page_icon="📊", initial_sidebar_state="expanded")

# --- ESTILOS CSS AVANZADOS ---
st.markdown("""
<style>
    .metric-container {display: flex; justify-content: space-between; gap: 1rem; margin-bottom: 2rem;}
    .metric-card {background-color: #ffffff; padding: 20px; border-radius: 10px; border-left: 5px solid #2e6c80; box-shadow: 0 4px 6px rgba(0,0,0,0.1); width: 100%;}
    .metric-title {font-size: 0.9rem; color: #666; font-weight: 600; margin-bottom: 0.5rem;}
    .metric-value {font-size: 1.8rem; color: #1f2937; font-weight: 700;}
    .stDataFrame {border-radius: 10px !important; overflow: hidden !important;}
</style>
""", unsafe_allow_html=True)

# --- FUNCIÓN PARA EXPORTAR EXCEL PROFESIONAL ---
def generar_excel_profesional(df, sheet_name="Reporte"):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
        workbook = writer.book
        worksheet = writer.sheets[sheet_name]
        
        # Formatos
        header_format = workbook.add_format({
            'bold': True, 'text_wrap': True, 'valign': 'center', 'align': 'center',
            'fg_color': '#2e6c80', 'font_color': 'white', 'border': 1
        })
        cell_format = workbook.add_format({'border': 1, 'valign': 'center'})
        money_format = workbook.add_format({'border': 1, 'num_format': '$#,##0.00', 'valign': 'center'})
        
        # Aplicar formato de encabezado y ajustar anchos
        for col_num, value in enumerate(df.columns.values):
            worksheet.write(0, col_num, value, header_format)
            column_len = max(df[value].astype(str).map(len).max(), len(str(value))) + 2
            worksheet.set_column(col_num, col_num, min(column_len, 30), cell_format)
            
            # Formato moneda para columnas específicas
            if any(palabra in str(value).lower() for palabra in ['costo', 'precio', 'ingreso', 'inversion', 'revenue']):
                worksheet.set_column(col_num, col_num, min(column_len, 20), money_format)

    return output.getvalue()

# --- EXTRACCIÓN DE DATOS (CACHÉ) ---
# Se mantiene tu estructura original intacta
@st.cache_data(ttl=300)
def load_data():
    connector = OdooConnector()
    with st.spinner('Conectando al núcleo de Odoo... Extrayendo Productos...'):
        df_prod = connector.get_products_detailed()
    with st.spinner('Analizando Bodegas (Stock Quant)...'):
        df_stock = connector.get_stock_quants()
    with st.spinner('Procesando Histórico de Ventas...'):
        df_sales = connector.get_sales_lines()
    return df_prod, df_stock, df_sales

# --- MOTOR DE ANÁLISIS (LÓGICA DE NEGOCIO) ---
def process_data(df_prod, df_stock, df_sales):
    if df_prod.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    # 1. Enriquecer Stock
    if not df_stock.empty:
        df_stock_full = pd.merge(df_stock, df_prod, on='product_id', how='left')
        df_stock_full['valor_inventario_costo'] = df_stock_full['stock_real_ubicacion'] * df_stock_full['standard_price']
        df_stock_full['valor_inventario_venta'] = df_stock_full['stock_real_ubicacion'] * df_stock_full['list_price']
        df_stock_full['location_name'] = df_stock_full['location_name'].fillna('Desconocida')
    else:
        df_stock_full = pd.DataFrame(columns=['product_id', 'stock_real_ubicacion', 'valor_inventario_costo', 'categ_name', 'location_name'])

    # 2. Resumen de Ventas y Análisis ABC
    if not df_sales.empty:
        sales_summary = df_sales.groupby('product_id').agg({'qty_sold': 'sum', 'revenue': 'sum', 'date': 'max'}).reset_index()
        dias_analisis = max((df_sales['date'].max() - df_sales['date'].min()).days, 1)
        sales_summary['venta_diaria_promedio'] = sales_summary['qty_sold'] / dias_analisis
        
        # Clasificación ABC basada en Ingresos (Regla 80/15/5)
        sales_summary = sales_summary.sort_values(by='revenue', ascending=False)
        sales_summary['cum_rev_pct'] = sales_summary['revenue'].cumsum() / sales_summary['revenue'].sum()
        sales_summary['clasificacion_abc'] = pd.cut(sales_summary['cum_rev_pct'], bins=[0, 0.8, 0.95, 1.1], labels=['A (Alto Impacto)', 'B (Medio)', 'C (Baja Rotación)'])
    else:
        sales_summary = pd.DataFrame(columns=['product_id', 'qty_sold', 'revenue', 'venta_diaria_promedio', 'clasificacion_abc'])

    # 3. Master Data
    df_master = pd.merge(df_prod, sales_summary, on='product_id', how='left')
    
    # Rellenar nulos numéricos
    for col in ['qty_sold', 'revenue', 'venta_diaria_promedio']:
        df_master[col] = df_master[col].fillna(0)
        
    # CORRECCIÓN DEL ERROR: Convertir la columna categórica a texto (object) antes de aplicar fillna
    if 'clasificacion_abc' in df_master.columns:
        df_master['clasificacion_abc'] = df_master['clasificacion_abc'].astype(object).fillna('Sin Ventas')
    else:
        df_master['clasificacion_abc'] = 'Sin Ventas'

    # 4. KPIs Avanzados de Inventario
    df_master['dias_inventario'] = df_master.apply(
        lambda row: row['stock_total_teorico'] / row['venta_diaria_promedio'] if row['venta_diaria_promedio'] > 0 else 999, axis=1
    )
    
    def clasificar_stock(row):
        if row['stock_total_teorico'] <= 0: return "🔴 Agotado"
        if row['dias_inventario'] < 10: return "🟠 Crítico (Reabastecer)"
        if row['dias_inventario'] > 90: return "🔵 Sobre-stock"
        return "🟢 Saludable"
    
    df_master['estado_inventario'] = df_master.apply(clasificar_stock, axis=1)
    
    # Asegurar columnas booleanas para selección en UI
    df_master['Seleccionar'] = False

    return df_master, df_stock_full, df_sales

# ==========================================
# --- INTERFAZ DE USUARIO (DASHBOARD) ---
# ==========================================
try:
    df_prod, df_stock, df_sales = load_data()
    df_master_raw, df_stock_full_raw, df_sales_raw = process_data(df_prod, df_stock, df_sales)
    
    if df_master_raw.empty:
        st.error("🚨 Base de datos vacía o error de conexión. Verifica Odoo.")
        st.stop()

    # --- SIDEBAR: FILTROS GLOBALES ---
    with st.sidebar:
        st.title("🎛️ Centro de Mando")
        st.markdown("Filtros globales para todo el sistema.")
        
        categorias = ['Todas'] + sorted([str(x) for x in df_master_raw['categ_name'].dropna().unique()])
        filtro_categ = st.selectbox("📌 Filtrar por Categoría", categorias)
        
        clases_abc = ['Todas'] + list(df_master_raw['clasificacion_abc'].unique())
        filtro_abc = st.selectbox("📊 Clasificación ABC", clases_abc)
        
        st.markdown("---")
        st.markdown("⚙️ *Desarrollado por GM-Datovate*")

    # Aplicar filtros globales
    df_master = df_master_raw.copy()
    df_stock_full = df_stock_full_raw.copy()

    if filtro_categ != 'Todas':
        df_master = df_master[df_master['categ_name'] == filtro_categ]
        if not df_stock_full.empty: 
            df_stock_full = df_stock_full[df_stock_full['categ_name'] == filtro_categ]
    
    if filtro_abc != 'Todas':
        df_master = df_master[df_master['clasificacion_abc'] == filtro_abc]

    # --- ENCABEZADO PRINCIPAL ---
    st.title("🚀 Super BI Odoo | Inteligencia de Negocios")
    st.markdown("Análisis avanzado, balanceo algorítmico y sugerencias de compra interactivas.")
    
    # --- PESTAÑAS ---
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Visión Ejecutiva", "📦 Gestión de Inventario", "🚚 Traslados Inteligentes", "🛒 Panel de Compras"])

    # === TAB 1: VISIÓN EJECUTIVA (KPIs y Gráficos) ===
    with tab1:
        st.markdown("### 📈 Indicadores Clave de Rendimiento (KPIs)")
        
        # Calcular KPIs
        t_ventas = df_master['revenue'].sum()
        t_costo_inv = sum(df_stock_full['valor_inventario_costo'].dropna()) if not df_stock_full.empty else 0
        t_items = df_master['stock_total_teorico'].sum()
        margen_prom = ((df_master['list_price'] - df_master['standard_price']) / df_master['list_price'].replace(0, 1)).mean() * 100

        # Renderizar Tarjetas HTML
        st.markdown(f"""
        <div class="metric-container">
            <div class="metric-card"><div class="metric-title">Ingresos Totales (Filtro Actual)</div><div class="metric-value">${t_ventas:,.0f}</div></div>
            <div class="metric-card"><div class="metric-title">Capital Inmovilizado (Costo)</div><div class="metric-value">${t_costo_inv:,.0f}</div></div>
            <div class="metric-card"><div class="metric-title">Unidades Físicas (Stock)</div><div class="metric-value">{t_items:,.0f}</div></div>
            <div class="metric-card"><div class="metric-title">Margen Teórico Promedio</div><div class="metric-value">{margen_prom:.1f}%</div></div>
        </div>
        """, unsafe_allow_html=True)

        colA, colB = st.columns(2)
        with colA:
            st.markdown("#### Top 10 Productos Estrella (Ingresos)")
            top10 = df_master.nlargest(10, 'revenue')
            fig1 = px.bar(top10, x='revenue', y='name', orientation='h', color='clasificacion_abc', 
                          color_discrete_map={'A (Alto Impacto)': '#2ca02c', 'B (Medio)': '#ff7f0e', 'C (Baja Rotación)': '#d62728', 'Sin Ventas': '#7f7f7f'},
                          labels={'revenue': 'Ingresos ($)', 'name': 'Producto'})
            fig1.update_layout(yaxis={'categoryorder':'total ascending'})
            st.plotly_chart(fig1, use_container_width=True)

        with colB:
            st.markdown("#### Composición del Inventario (Valor $)")
            if not df_stock_full.empty:
                pie_data = df_stock_full.groupby('location_name')['valor_inventario_costo'].sum().reset_index()
                fig2 = px.pie(pie_data, values='valor_inventario_costo', names='location_name', hole=0.4)
                fig2.update_traces(textposition='inside', textinfo='percent+label')
                st.plotly_chart(fig2, use_container_width=True)
            else:
                st.info("Sin datos de ubicaciones.")

    # === TAB 2: GESTIÓN DE INVENTARIO ===
    with tab2:
        st.markdown("### 📦 Salud Detallada del Inventario")
        c1, c2, c3 = st.columns(3)
        f_estado = c1.selectbox("Filtrar por Estado", ["Todos"] + list(df_master['estado_inventario'].unique()))
        
        df_inv_view = df_master.copy()
        if f_estado != "Todos":
            df_inv_view = df_inv_view[df_inv_view['estado_inventario'] == f_estado]

        columnas_ver = ['Seleccionar', 'default_code', 'name', 'categ_name', 'stock_total_teorico', 'venta_diaria_promedio', 'dias_inventario', 'estado_inventario', 'clasificacion_abc']
        
        # Tabla Editable (Permite seleccionar filas)
        edited_inv = st.data_editor(
            df_inv_view[columnas_ver],
            column_config={
                "Seleccionar": st.column_config.CheckboxColumn("Seleccionar", default=False),
                "dias_inventario": st.column_config.NumberColumn("Días Cobertura", format="%.1f"),
                "venta_diaria_promedio": st.column_config.NumberColumn("Rotación/Día", format="%.2f"),
                "estado_inventario": "Salud de Stock"
            },
            disabled=['default_code', 'name', 'categ_name', 'stock_total_teorico', 'venta_diaria_promedio', 'dias_inventario', 'estado_inventario', 'clasificacion_abc'],
            use_container_width=True, hide_index=True, key="inv_editor"
        )

        # Descargar lo seleccionado
        seleccion_inv = edited_inv[edited_inv['Seleccionar'] == True]
        if not seleccion_inv.empty:
            excel_data = generar_excel_profesional(seleccion_inv.drop(columns=['Seleccionar']), "Inventario_Seleccionado")
            st.download_button(label="📥 Descargar Filas Seleccionadas (Excel)", data=excel_data, file_name=f"Inventario_Status_{time.strftime('%Y%m%d')}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    # === TAB 3: TRASLADOS INTELIGENTES ===
    with tab3:
        st.markdown("### 🚚 Motor de Rebalanceo de Bodegas")
        st.markdown("Identifica productos estancados en una ubicación que urgen en otra.")
        
        if df_stock_full.empty:
            st.warning("No hay datos de múltiples bodegas.")
        else:
            bodegas_disp = sorted([str(x) for x in df_stock_full['location_name'].dropna().unique()])
            
            c_orig, c_dest = st.columns(2)
            bodega_origen_filtro = c_orig.selectbox("📍 Filtrar Origen (Donde sobra)", ["Todas"] + bodegas_disp)
            bodega_destino_filtro = c_dest.selectbox("🎯 Filtrar Destino (Donde falta)", ["Todas"] + bodegas_disp)

            stock_pivot = df_stock_full.pivot_table(index=['product_id', 'name', 'default_code'], columns='location_name', values='stock_real_ubicacion', fill_value=0).reset_index()
            bodegas_cols = [c for c in stock_pivot.columns if c not in ['product_id', 'name', 'default_code']]
            
            sugerencias = []
            for _, row in stock_pivot.iterrows():
                for b_origen in bodegas_cols:
                    for b_destino in bodegas_cols:
                        if b_origen == b_destino: continue
                        
                        # Respetar filtros del usuario
                        if bodega_origen_filtro != "Todas" and b_origen != bodega_origen_filtro: continue
                        if bodega_destino_filtro != "Todas" and b_destino != bodega_destino_filtro: continue

                        q_origen = row[b_origen]
                        q_destino = row[b_destino]
                        
                        # ALGORITMO: Sobra en origen (>5), falta en destino (0 o 1)
                        if q_origen >= 5 and q_destino <= 1:
                            sugerencias.append({
                                'Aprobar': False,
                                'Referencia': row['default_code'],
                                'Producto': row['name'],
                                'Bodega Origen': b_origen,
                                'Bodega Destino': b_destino,
                                'Stock Origen': q_origen,
                                'Stock Destino': q_destino,
                                'Cant. Sugerida (Editar)': int(q_origen * 0.3) # Sugiere mover el 30%
                            })
            
            if sugerencias:
                df_sug = pd.DataFrame(sugerencias)
                st.success(f"✅ Motor encontró {len(df_sug)} oportunidades de balanceo.")
                
                # Tabla Editable (Checkboxes y cantidades)
                edited_transfers = st.data_editor(
                    df_sug,
                    column_config={
                        "Aprobar": st.column_config.CheckboxColumn("¿Aprobar?", default=False),
                        "Cant. Sugerida (Editar)": st.column_config.NumberColumn("Cantidad a Mover", min_value=1, step=1)
                    },
                    disabled=['Referencia', 'Producto', 'Bodega Origen', 'Bodega Destino', 'Stock Origen', 'Stock Destino'],
                    use_container_width=True, hide_index=True
                )
                
                # Lógica de descarga
                aprobados_trans = edited_transfers[edited_transfers['Aprobar'] == True]
                if not aprobados_trans.empty:
                    st.info(f"Tienes {len(aprobados_trans)} traslados aprobados listos para exportar.")
                    excel_trans = generar_excel_profesional(aprobados_trans.drop(columns=['Aprobar']), "Orden_Traslado")
                    st.download_button(label="📥 Generar Orden de Traslado (Excel)", data=excel_trans, file_name=f"Traslados_Aprobados_{time.strftime('%Y%m%d')}.xlsx", mime="application/vnd.ms-excel")
            else:
                st.info("👍 No se encontraron desbalances críticos con los filtros seleccionados.")

    # === TAB 4: PANEL DE COMPRAS ===
    with tab4:
        st.markdown("### 🛒 Creador de Órdenes de Compra (Basado en IA/Rotación)")
        
        # Parámetros dinámicos
        col_p1, col_p2 = st.columns(2)
        dias_cobertura = col_p1.slider("🎯 Meta: Días de inventario a cubrir", min_value=15, max_value=120, value=30, step=5)
        solo_abc = col_p2.multiselect("Filtrar por Importancia (ABC)", ['A (Alto Impacto)', 'B (Medio)', 'C (Baja Rotación)'], default=['A (Alto Impacto)', 'B (Medio)'])

        df_compras = df_master[df_master['clasificacion_abc'].isin(solo_abc)].copy()
        
        # Fórmula: (Venta Diaria * Días Meta) - Stock Actual
        df_compras['stock_ideal'] = df_compras['venta_diaria_promedio'] * dias_cobertura
        df_compras['faltante'] = df_compras['stock_ideal'] - df_compras['stock_total_teorico']
        
        # Filtrar solo lo que requiere compra y redondear
        df_compras = df_compras[(df_compras['faltante'] > 0) & (df_compras['venta_diaria_promedio'] > 0)].copy()
        df_compras['cant_pedir'] = df_compras['faltante'].apply(lambda x: int(round(x, 0)))
        
        if df_compras.empty:
            st.success("🎉 Tu inventario está perfectamente cubierto para los parámetros seleccionados.")
        else:
            # Preparar dataframe para edición
            df_compras_ui = df_compras[['default_code', 'name', 'clasificacion_abc', 'stock_total_teorico', 'venta_diaria_promedio', 'standard_price', 'cant_pedir']].copy()
            df_compras_ui.insert(0, 'Aprobar Compra', False)
            df_compras_ui['Inversión Fila ($)'] = df_compras_ui['cant_pedir'] * df_compras_ui['standard_price']
            
            st.markdown(f"**Requerimientos detectados:** {len(df_compras_ui)} productos.")
            
            edited_purchases = st.data_editor(
                df_compras_ui,
                column_config={
                    "Aprobar Compra": st.column_config.CheckboxColumn("Aprobar", default=False),
                    "cant_pedir": st.column_config.NumberColumn("Cantidad a Pedir (Editar)", min_value=0, step=1),
                    "venta_diaria_promedio": st.column_config.NumberColumn("Venta/Día", format="%.2f"),
                    "standard_price": st.column_config.NumberColumn("Costo Unitario", format="$%.2f"),
                    "Inversión Fila ($)": st.column_config.NumberColumn("Costo Total", format="$%.2f")
                },
                disabled=['default_code', 'name', 'clasificacion_abc', 'stock_total_teorico', 'venta_diaria_promedio', 'standard_price', 'Inversión Fila ($)'],
                use_container_width=True, hide_index=True
            )
            
            # Recalcular la inversión total en tiempo real según las ediciones del usuario
            inversion_total = (edited_purchases['cant_pedir'] * edited_purchases['standard_price']).sum()
            st.metric("💰 Proyección Total de la Inversión (En Pantalla)", f"${inversion_total:,.0f}")
            
            aprobados_compra = edited_purchases[edited_purchases['Aprobar Compra'] == True]
            if not aprobados_compra.empty:
                inv_aprobada = (aprobados_compra['cant_pedir'] * aprobados_compra['standard_price']).sum()
                st.success(f"🛒 Has aprobado {len(aprobados_compra)} productos por un total de **${inv_aprobada:,.0f}**.")
                
                excel_compras = generar_excel_profesional(aprobados_compra.drop(columns=['Aprobar Compra']), "Sugerencia_Compras")
                st.download_button(label="📥 Generar Orden de Compra (Excel)", data=excel_compras, file_name=f"Orden_Compra_{time.strftime('%Y%m%d')}.xlsx", mime="application/vnd.ms-excel")

except Exception as e:
    st.error(f"Ocurrió un error crítico: {e}")
    st.write("Detalle técnico:", e)