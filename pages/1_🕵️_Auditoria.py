import streamlit as st
import pandas as pd

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
