import streamlit as st
import xmlrpc.client
import pandas as pd

st.set_page_config(page_title="Auditoría de Datos", layout="wide")

st.title("🕵️ Escáner de Diagnóstico Odoo")
st.markdown("Esta herramienta verifica qué campos existen realmente en tu base de datos para evitar errores en el código final.")

# --- 1. CONEXIÓN (Usando tus secretos configurados) ---
try:
    URL = st.secrets["odoo_connection"]["url"]
    DB = st.secrets["odoo_connection"]["db"]
    USER = st.secrets["odoo_connection"]["username"]
    PWD = st.secrets["odoo_connection"]["password"]
    
    # Conexión XML-RPC
    common = xmlrpc.client.ServerProxy(f'{URL}/xmlrpc/2/common')
    uid = common.authenticate(DB, USER, PWD, {})
    models = xmlrpc.client.ServerProxy(f'{URL}/xmlrpc/2/object')
    
    if uid:
        st.success(f"✅ Conectado exitosamente a la BD: **{DB}**")
    else:
        st.error("❌ Credenciales incorrectas.")
        st.stop()
        
except Exception as e:
    st.error(f"❌ Error de conexión: {e}")
    st.stop()

# --- FUNCIÓN DE AUDITORÍA ---
def auditar_modelo(nombre_modelo, campos_sospechosos):
    st.divider()
    st.subheader(f"📦 Modelo: `{nombre_modelo}`")
    
    try:
        # 1. Obtener todos los campos disponibles
        all_fields = models.execute_kw(DB, uid, PWD, nombre_modelo, 'fields_get', [], {'attributes': ['string', 'type']})
        lista_campos_reales = list(all_fields.keys())
        
        # 2. Verificar los que necesitamos
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**🔍 Verificación de Campos:**")
            campos_validos = []
            for campo in campos_sospechosos:
                if campo in lista_campos_reales:
                    st.markdown(f"✅ `{campo}`: Existe ({all_fields[campo]['type']})")
                    campos_validos.append(campo)
                else:
                    st.markdown(f"❌ `{campo}`: **NO EXISTE**")
        
        # 3. Traer datos de muestra
        with col2:
            st.markdown("**📊 Muestra de Datos (Raw):**")
            data = models.execute_kw(DB, uid, PWD, nombre_modelo, 'search_read', [[]], {'fields': campos_validos, 'limit': 3})
            
            if data:
                df = pd.DataFrame(data)
                # Convertir a string para evitar error de PyArrow con listas
                df = df.astype(str)
                st.dataframe(df, use_container_width=True)
            else:
                st.warning("La tabla está vacía (0 registros).")
                
    except Exception as e:
        st.error(f"No se pudo leer el modelo: {e}")

# --- EJECUTAR AUDITORÍA ---

st.info("Buscando las tablas críticas para tu Dashboard de IA...")

# 1. Auditoría de VENTAS
# Buscamos variantes de fecha y precio para saber cuál usar
auditar_modelo('sale.order.line', [
    'product_id', 
    'product_uom_qty', 
    'qty_delivered',    # A veces se usa esta en vez de uom_qty
    'price_unit', 
    'price_subtotal',
    'date_order',       # El que falló antes
    'create_date',      # El que suele funcionar
    'order_id'
])

# 2. Auditoría de STOCK
# Buscamos variantes de cantidad
auditar_modelo('stock.quant', [
    'product_id', 
    'location_id', 
    'quantity', 
    'inventory_quantity', # A veces se usa esta
    'available_quantity',
    'in_date',
    'inventory_date',
    'value'
])

# 3. Auditoría de PRODUCTOS
auditar_modelo('product.product', [
    'name', 
    'default_code', 
    'list_price', 
    'standard_price', # Costo
    'categ_id'
])
