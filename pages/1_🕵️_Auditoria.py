import streamlit as st
import pandas as pd
import zipfile
from io import BytesIO

st.set_page_config(page_title="Auditoría de Datos", layout="wide")

st.title("🕵️ Escáner de Diagnóstico Odoo")
st.markdown("Esta herramienta verifica qué campos existen realmente en tu base de datos para evitar errores en el código final.")

# --- 1. CONEXIÓN USANDO OdooConnector ---
try:
    from odoo_client import OdooConnector
    connector = OdooConnector()
    st.success(f"✅ Conectado exitosamente a la BD: **{connector.db}** como **{connector.username}**")
except Exception as e:
    st.error(f"❌ Error de conexión crítico con Odoo: {e}")
    st.stop()

# --- FUNCIÓN DE AUDITORÍA ---
def auditar_modelo(nombre_modelo, campos_sospechosos):
    st.divider()
    st.subheader(f"📦 Modelo: `{nombre_modelo}`")
    try:
        # 1. Obtener todos los campos disponibles
        all_fields = connector.models.execute_kw(
            connector.db, connector.uid, connector.password,
            nombre_modelo, 'fields_get', [], {'attributes': ['string', 'type']}
        )
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
            try:
                data = connector.models.execute_kw(
                    connector.db, connector.uid, connector.password,
                    nombre_modelo, 'search_read', [[]], {'fields': campos_validos, 'limit': 3}
                )
                if data:
                    df = pd.DataFrame(data)
                    df = df.astype(str)
                    st.dataframe(df, use_container_width=True)
                else:
                    st.warning("La tabla está vacía (0 registros).")
            except Exception as e:
                st.error(f"Error al leer datos de muestra: {e}")

    except Exception as e:
        st.error(f"No se pudo auditar el modelo `{nombre_modelo}`: {e}")

# --- EJECUTAR AUDITORÍA ---

st.info("Buscando las tablas críticas para tu Dashboard de IA...")

# 1. Auditoría de VENTAS
auditar_modelo('sale.order.line', [
    'product_id', 
    'product_uom_qty', 
    'qty_delivered',
    'price_unit', 
    'price_subtotal',
    'date_order',
    'create_date',
    'order_id'
])

# 2. Auditoría de STOCK
auditar_modelo('stock.quant', [
    'product_id', 
    'location_id', 
    'quantity', 
    'inventory_quantity',
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
    'standard_price',
    'categ_id'
])

# 4. Auditoría de STOCK LOCATION
auditar_modelo('stock.location', [
    'name', 'usage', 'company_id', 'location_id'
])

# 5. Auditoría de STOCK MOVE
auditar_modelo('stock.move', [
    'product_id', 'location_id', 'location_dest_id', 'state', 'quantity_done', 'date'
])

# 6. Auditoría de PURCHASE ORDER
auditar_modelo('purchase.order', [
    'name', 'partner_id', 'date_order', 'state', 'amount_total'
])

# 7. Auditoría de PURCHASE ORDER LINE
auditar_modelo('purchase.order.line', [
    'order_id', 'product_id', 'product_qty', 'price_unit', 'date_planned'
])

# 8. Auditoría de PRODUCT CATEGORY
auditar_modelo('product.category', [
    'name', 'parent_id'
])

st.header("📚 Explorador de Modelos y Campos Odoo")

if st.button("🔍 Listar todos los modelos y campos disponibles"):
    with st.spinner("Consultando modelos y campos, esto puede tardar unos segundos..."):
        try:
            # 1. Obtener todos los modelos
            ir_model_data = connector.models.execute_kw(
                connector.db, connector.uid, connector.password,
                'ir.model', 'search_read', [[]], {'fields': ['model', 'name'], 'limit': 2000}
            )
            modelos = sorted(ir_model_data, key=lambda x: x['model'])
            st.success(f"Se encontraron {len(modelos)} modelos en Odoo.")

            # 2. Para cada modelo, obtener los campos
            resumen = []
            for modelo in modelos:
                try:
                    fields = connector.models.execute_kw(
                        connector.db, connector.uid, connector.password,
                        modelo['model'], 'fields_get', [], {'attributes': ['string', 'type']}
                    )
                    for campo, props in fields.items():
                        resumen.append({
                            "Modelo": modelo['model'],
                            "Nombre Modelo": modelo['name'],
                            "Campo": campo,
                            "Descripción": props.get('string', ''),
                            "Tipo": props.get('type', '')
                        })
                except Exception as e:
                    resumen.append({
                        "Modelo": modelo['model'],
                        "Nombre Modelo": modelo['name'],
                        "Campo": "ERROR",
                        "Descripción": f"Error: {e}",
                        "Tipo": ""
                    })

            df_resumen = pd.DataFrame(resumen)
            st.dataframe(df_resumen, use_container_width=True)
            st.info("Puedes filtrar y buscar en la tabla para investigar cualquier modelo o campo.")
        except Exception as e:
            st.error(f"Error al consultar modelos y campos: {e}")

st.header("🔎 Auditoría Profunda de Modelos Clave Odoo")

# Modelos clave para tu BI
modelos_clave = [
    ('sale.order.line', 'Líneas de Venta'),
    ('stock.quant', 'Stock por Ubicación'),
    ('product.product', 'Productos'),
    ('res.partner', 'Clientes/Proveedores'),
    ('stock.location', 'Ubicaciones'),
    ('stock.move', 'Movimientos de Stock'),
    ('purchase.order', 'Órdenes de Compra'),
    ('purchase.order.line', 'Líneas de Orden de Compra'),
    ('product.category', 'Categorías de Producto'),
]

try:
    from odoo_client import OdooConnector
    connector = OdooConnector()
    st.success(f"✅ Conectado exitosamente a la BD: **{connector.db}** como **{connector.username}**")
except Exception as e:
    st.error(f"❌ Error de conexión crítico con Odoo: {e}")
    st.stop()

for modelo, nombre in modelos_clave:
    st.divider()
    st.subheader(f"📦 Modelo: `{modelo}` ({nombre})")
    try:
        # Mostrar todos los campos
        all_fields = connector.models.execute_kw(
            connector.db, connector.uid, connector.password,
            modelo, 'fields_get', [], {'attributes': ['string', 'type']}
        )
        campos = []
        for campo, props in all_fields.items():
            campos.append({
                "Campo": campo,
                "Descripción": props.get('string', ''),
                "Tipo": props.get('type', '')
            })
        df_campos = pd.DataFrame(campos)
        st.dataframe(df_campos, use_container_width=True)
        st.info(f"Total de campos en `{modelo}`: {len(df_campos)}")

        # --- NUEVO BLOQUE: Muestra de datos reales ---
        st.markdown("**📊 Muestra de Datos Reales:**")
        try:
            # Trae hasta 10 registros y todos los campos
            data = connector.models.execute_kw(
                connector.db, connector.uid, connector.password,
                modelo, 'search_read', [[]], {'fields': list(all_fields.keys()), 'limit': 10}
            )
            if data:
                df_data = pd.DataFrame(data)
                # Procesa campos Many2one: si es lista, muestra solo el nombre
                for col in df_data.columns:
                    if df_data[col].apply(lambda x: isinstance(x, list)).any():
                        df_data[col] = df_data[col].apply(lambda x: x[1] if isinstance(x, list) and len(x) > 1 else x)
                st.dataframe(df_data, use_container_width=True)
            else:
                st.warning("La tabla está vacía (0 registros).")
        except Exception as e:
            st.error(f"Error al leer datos reales: {e}")

    except Exception as e:
        st.error(f"No se pudo auditar el modelo `{modelo}`: {e}")

st.header("🔬 Diagnóstico de Stock y Ventas")

df_stock = connector.get_stock_data()
df_sales = connector.get_sales_data()

st.subheader("Stock (primeros 10 registros)")
st.dataframe(df_stock.head(10))
st.write("Total productos con stock:", df_stock['product_name'].nunique())
st.write("Suma total de stock:", df_stock['quantity'].sum())

st.subheader("Ventas (primeros 10 registros)")
st.dataframe(df_sales.head(10))
st.write("Total productos con ventas:", df_sales['product_name'].nunique())
st.write("Suma total de ventas:", df_sales['qty_sold'].sum())

st.header("⬇️ Exportar datos reales de modelos clave a CSV (ZIP)")

if st.button("Exportar todos los modelos a ZIP (CSV por modelo)"):
    with st.spinner("Extrayendo y exportando datos reales..."):
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            for modelo, nombre in modelos_clave:
                try:
                    all_fields = connector.models.execute_kw(
                        connector.db, connector.uid, connector.password,
                        modelo, 'fields_get', [], {'attributes': ['string', 'type']}
                    )
                    data = connector.models.execute_kw(
                        connector.db, connector.uid, connector.password,
                        modelo, 'search_read', [[]], {'fields': list(all_fields.keys()), 'limit': 1000}
                    )
                    if data:
                        df_data = pd.DataFrame(data)
                        # Procesa campos Many2one: si es lista, muestra solo el nombre
                        for col in df_data.columns:
                            if df_data[col].apply(lambda x: isinstance(x, list)).any():
                                df_data[col] = df_data[col].apply(lambda x: x[1] if isinstance(x, list) and len(x) > 1 else x)
                        # Guarda el CSV en el ZIP
                        csv_bytes = df_data.to_csv(index=False).encode("utf-8")
                        zf.writestr(f"{modelo.replace('.', '_')}.csv", csv_bytes)
                except Exception as e:
                    # Si falla un modelo, lo salta y sigue
                    continue
        zip_buffer.seek(0)
        st.download_button(
            label="📦 Descargar ZIP con todos los CSV",
            data=zip_buffer,
            file_name="auditoria_modelos_odoo.zip",
            mime="application/zip"
        )
        st.success("¡Listo! Descarga el ZIP y descomprímelo para ver cada modelo en un CSV separado.")

st.header("🔎 Diagnóstico directo de DataFrames para BI Engine")

# Extrae los DataFrames usando el mismo método que el dashboard principal
try:
    df_stock = connector.get_stock_data()
    df_sales = connector.get_sales_data()
    df_product = connector.get_product_data()
    df_location = connector.get_location_data()
    df_moves = connector.get_stock_move_data()
    df_clients = connector.get_partner_data()
    df_purchases = connector.get_purchase_order_line_data()

    st.subheader("Stock (DataFrame crudo)")
    st.dataframe(df_stock.head(10))
    st.write("Shape:", df_stock.shape)
    st.write("Columnas:", df_stock.columns.tolist())

    st.subheader("Ventas (DataFrame crudo)")
    st.dataframe(df_sales.head(10))
    st.write("Shape:", df_sales.shape)
    st.write("Columnas:", df_sales.columns.tolist())

    st.subheader("Productos (DataFrame crudo)")
    st.dataframe(df_product.head(10))
    st.write("Shape:", df_product.shape)
    st.write("Columnas:", df_product.columns.tolist())

    st.subheader("Ubicaciones (DataFrame crudo)")
    st.dataframe(df_location.head(10))
    st.write("Shape:", df_location.shape)
    st.write("Columnas:", df_location.columns.tolist())

    st.subheader("Movimientos de Stock (DataFrame crudo)")
    st.dataframe(df_moves.head(10))
    st.write("Shape:", df_moves.shape)
    st.write("Columnas:", df_moves.columns.tolist())

    st.subheader("Clientes (DataFrame crudo)")
    st.dataframe(df_clients.head(10))
    st.write("Shape:", df_clients.shape)
    st.write("Columnas:", df_clients.columns.tolist())

    st.subheader("Compras (DataFrame crudo)")
    st.dataframe(df_purchases.head(10))
    st.write("Shape:", df_purchases.shape)
    st.write("Columnas:", df_purchases.columns.tolist())

except Exception as e:
    st.error(f"Error al extraer DataFrames crudos: {e}")
