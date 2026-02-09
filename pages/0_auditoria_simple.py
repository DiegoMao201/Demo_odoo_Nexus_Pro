import streamlit as st
import pandas as pd
from odoo_client import OdooConnector

st.set_page_config(page_title="Auditoría Simple Odoo", layout="wide")
st.title("🔎 Auditoría Simple de Modelos Odoo")

MODELOS = [
    ("product.template", "Productos (product.template)"),
    ("sale.order.line", "Líneas de Venta (sale.order.line)")
]

try:
    connector = OdooConnector()
    st.success(f"Conectado a la BD: {connector.db} como {connector.username}")
except Exception as e:
    st.error(f"Error de conexión: {e}")
    st.stop()

for modelo, nombre in MODELOS:
    st.header(f"📦 {nombre} — `{modelo}`")
    try:
        # Lista de campos
        fields = connector.models.execute_kw(
            connector.db, connector.uid, connector.password,
            modelo, 'fields_get', [], {'attributes': ['string', 'type']}
        )
        campos = pd.DataFrame([
            {"Campo": k, "Tipo": v["type"], "Descripción": v["string"]}
            for k, v in fields.items()
        ])
        st.subheader("Lista de campos")
        st.dataframe(campos, use_container_width=True)

        # Preview de datos
        data = connector.models.execute_kw(
            connector.db, connector.uid, connector.password,
            modelo, 'search_read', [[]], {'fields': list(fields.keys()), 'limit': 10}
        )
        if data:
            df = pd.DataFrame(data)
            # Procesa campos many2one para mostrar solo el nombre
            for col in df.columns:
                if df[col].apply(lambda x: isinstance(x, list)).any():
                    df[col] = df[col].apply(lambda x: x[1] if isinstance(x, list) and len(x) > 1 else x)
            st.subheader("Preview de datos (primeros 10)")
            st.dataframe(df, use_container_width=True)
        else:
            st.warning("No hay datos en este modelo.")
    except Exception as e:
        st.error(f"Error al auditar {modelo}: {e}")