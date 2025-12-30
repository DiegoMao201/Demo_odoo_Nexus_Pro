import streamlit as st
import pandas as pd
from odoo_client import OdooConnector

st.set_page_config(page_title="Inspector Odoo API", layout="wide")
st.title("🕵️ Inspector de Datos Odoo")
st.markdown("Herramienta para descubrir qué campos y datos reales existen en tu API.")

# --- CONEXIÓN ---
@st.cache_resource
def get_connector():
    return OdooConnector()

try:
    odoo = get_connector()
    st.sidebar.success(f"✅ Conectado a: {odoo.db}")
except Exception as e:
    st.error(f"Error de conexión: {e}")
    st.stop()

# --- SELECTOR DE MODELO ---
st.sidebar.header("Explorar Modelo")
opciones_comunes = [
    "sale.order",          # Cabeceras de Pedidos
    "sale.order.line",     # Líneas de productos en pedidos (Donde tuviste el error)
    "product.product",     # Variantes de productos
    "product.template",    # Plantillas de productos
    "res.partner",         # Clientes y Proveedores
    "stock.quant",         # Stock actual
    "stock.picking"        # Albaranes/Traslados
]
model_name = st.sidebar.selectbox("Selecciona o escribe un modelo:", opciones_comunes, index=1)
custom_model = st.sidebar.text_input("O escribe otro modelo manual:", "")
if custom_model:
    model_name = custom_model

# --- FUNCIÓN DE INSPECCIÓN ---
def inspect_model(model):
    try:
        # 1. Obtener Metadatos (Diccionario de campos)
        # fields_get es el método de Odoo que nos dice la estructura de la tabla
        fields_info = odoo.models.execute_kw(
            odoo.db, odoo.uid, odoo.password,
            model, 'fields_get', 
            [], {'attributes': ['string', 'type', 'help']}
        )
        df_structure = pd.DataFrame.from_dict(fields_info, orient='index')
        df_structure = df_structure.reset_index().rename(columns={'index': 'Field Name'})
        
        # 2. Obtener Datos de Muestra (Primeros 5 registros)
        # Traemos todos los campos para ver qué hay
        sample_data = odoo.models.execute_kw(
            odoo.db, odoo.uid, odoo.password,
            model, 'search_read', 
            [[]], {'limit': 5} # Sin filtros, solo 5 registros
        )
        df_sample = pd.DataFrame(sample_data)
        
        return df_structure, df_sample
    except Exception as e:
        return None, str(e)

# --- MOSTRAR RESULTADOS ---
if st.button(f"🔍 Analizar {model_name}"):
    with st.spinner(f"Consultando estructura de {model_name}..."):
        structure, sample = inspect_model(model_name)
        
        if isinstance(sample, str): # Si devolvió un error
            st.error(f"Error consultando el modelo: {sample}")
            st.warning("Consejo: Verifica que el nombre del modelo sea correcto y tengas permisos.")
        else:
            # PESTAÑA 1: ESTRUCTURA (QUÉ CAMPOS EXISTEN)
            st.subheader(f"Estructura de: {model_name}")
            st.info("Usa la columna 'Field Name' en tu código Python.")
            st.dataframe(structure[['Field Name', 'string', 'type']], use_container_width=True, hide_index=True)
            
            # PESTAÑA 2: DATOS REALES (QUÉ CONTIENEN)
            st.subheader("📊 Muestra de Datos (5 registros)")
            if not sample.empty:
                st.dataframe(sample)
            else:
                st.warning("La tabla existe pero está vacía (no tiene registros).")
