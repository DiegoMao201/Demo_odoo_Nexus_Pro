import xmlrpc.client
import pandas as pd
import streamlit as st
import os

# --- CONFIGURACIÓN RÁPIDA (Copia tus credenciales aquí si no las lee del env) ---
URL = os.getenv("URL")
DB = os.getenv("DB")
USERNAME = os.getenv("USERNAME")
PASSWORD = os.getenv("PASSWORD")

st.set_page_config(layout="wide", page_title="🕵️ Detective de Stock Odoo")
st.title("🕵️ Diagnóstico Forense de Inventario Odoo")

if not URL:
    st.error("Configura las variables de entorno o edita el script con tus credenciales.")
    st.stop()

try:
    # Conexión
    common = xmlrpc.client.ServerProxy(f'{URL}/xmlrpc/2/common')
    uid = common.authenticate(DB, USERNAME, PASSWORD, {})
    models = xmlrpc.client.ServerProxy(f'{URL}/xmlrpc/2/object')
    
    if not uid:
        st.error("❌ Credenciales rechazadas.")
        st.stop()
        
    st.success(f"✅ Conectado exitosamente con UID: {uid}")

    # 1. VERIFICAR COMPAÑÍAS
    st.subheader("1. Mapa de Compañías Disponibles")
    companies = models.execute_kw(DB, uid, PASSWORD, 'res.company', 'search_read', [[]], {'fields': ['id', 'name']})
    df_companies = pd.DataFrame(companies)
    st.write(df_companies)
    
    # 2. BUSCAR STOCK REAL (SIN FILTROS DE UBICACIÓN)
    st.subheader("2. Muestra de Stock Físico Real (stock.quant > 0)")
    st.info("Buscando en TODAS las ubicaciones (Internas, Clientes, Tránsito, etc)...")
    
    # Buscamos cualquier quant con cantidad positiva
    domain_stock = [['quantity', '>', 0]]
    fields_stock = ['product_id', 'location_id', 'quantity', 'company_id', 'in_date']
    
    # Traemos 500 registros para ver dónde están
    stock_data = models.execute_kw(DB, uid, PASSWORD, 'stock.quant', 'search_read', [domain_stock], {'fields': fields_stock, 'limit': 500})
    
    if stock_data:
        df_stock = pd.DataFrame(stock_data)
        
        # Limpiar datos para lectura fácil
        if not df_stock.empty:
            df_stock['Producto'] = df_stock['product_id'].apply(lambda x: x[1] if isinstance(x, list) else x)
            df_stock['Ubicación'] = df_stock['location_id'].apply(lambda x: x[1] if isinstance(x, list) else x)
            df_stock['Compañía Dueña'] = df_stock['company_id'].apply(lambda x: x[1] if isinstance(x, list) else 'Sin Cía')
            
            st.dataframe(df_stock[['Producto', 'quantity', 'Ubicación', 'Compañía Dueña', 'in_date']], use_container_width=True)
            
            # Análisis rápido
            st.write("### 🔎 Pistas encontradas:")
            ubicaciones_encontradas = df_stock['Ubicación'].unique()
            st.write(f"**El stock aparece en estas ubicaciones:** {list(ubicaciones_encontradas)}")
            
            companias_encontradas = df_stock['Compañía Dueña'].unique()
            st.write(f"**El stock pertenece a estas compañías:** {list(companias_encontradas)}")
    else:
        st.error("😱 Odoo devolvió 0 registros en stock.quant con cantidad > 0.")
        st.markdown("""
        **Posibles causas extremas:**
        1. Base de datos equivocada (Revisa la variable `DB`).
        2. El usuario no tiene permisos de lectura sobre Inventario.
        3. Realmente no han cargado saldos iniciales.
        """)

    # 3. VERIFICAR VENTAS (Para ver si hay movimiento)
    st.subheader("3. Últimas 50 Líneas de Venta")
    sales_data = models.execute_kw(DB, uid, PASSWORD, 'sale.order.line', 'search_read', [[]], {'fields': ['order_id', 'product_id', 'product_uom_qty', 'state'], 'limit': 50})
    if sales_data:
        df_sales = pd.DataFrame(sales_data)
        df_sales['Producto'] = df_sales['product_id'].apply(lambda x: x[1] if isinstance(x, list) else x)
        df_sales['Pedido'] = df_sales['order_id'].apply(lambda x: x[1] if isinstance(x, list) else x)
        st.dataframe(df_sales[['Pedido', 'Producto', 'product_uom_qty', 'state']])
    else:
        st.warning("No se encontraron líneas de venta.")

except Exception as e:
    st.error(f"Error de sistema: {e}")