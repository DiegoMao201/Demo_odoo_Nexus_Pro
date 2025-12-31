import xmlrpc.client
import pandas as pd
import streamlit as st
import os  # <--- IMPORTANTE: Librería necesaria para leer Coolify

class OdooConnector:
    def __init__(self):
        try:
            # --- CAMBIO IMPORTANTE PARA COOLIFY ---
            # En lugar de st.secrets, leemos las Variables de Entorno
            self.url = os.getenv("URL")
            self.db = os.getenv("DB")
            self.username = os.getenv("USERNAME")
            self.password = os.getenv("PASSWORD")

            # Verificamos que las credenciales existan antes de intentar conectar
            if not self.url or not self.db or not self.username or not self.password:
                st.error("❌ Error: Faltan credenciales. Por favor configura URL, DB, USERNAME y PASSWORD en las Variables de Entorno de Coolify.")
                st.stop()

            # Conexión a Odoo
            common = xmlrpc.client.ServerProxy(f'{self.url}/xmlrpc/2/common')
            self.uid = common.authenticate(self.db, self.username, self.password, {})
            self.models = xmlrpc.client.ServerProxy(f'{self.url}/xmlrpc/2/object')
            
            if not self.uid:
                st.error("❌ Credenciales inválidas: Odoo rechazó la conexión.")
                st.stop()
                
        except Exception as e:
            st.error(f"❌ Error de conexión crítico: {e}")
            st.stop()

    def get_stock_data(self):
        """Trae stock valorizado y cantidades"""
        try:
            domain = [['location_id.usage', '=', 'internal']]
            fields = ['product_id', 'quantity', 'value', 'location_id']
            # Ejecutamos la consulta
            data = self.models.execute_kw(self.db, self.uid, self.password, 'stock.quant', 'search_read', [domain], {'fields': fields, 'limit': 5000})
            
            if data:
                df = pd.DataFrame(data)
                # Limpieza de datos
                df['product_name'] = df['product_id'].apply(lambda x: x[1] if isinstance(x, list) else 'Desc.')
                df['location_name'] = df['location_id'].apply(lambda x: x[1] if isinstance(x, list) else 'Desc.')
                df['quantity'] = pd.to_numeric(df['quantity'].fillna(0))
                df['value'] = pd.to_numeric(df['value'].fillna(0))
                return df[['product_name', 'quantity', 'value', 'location_name']]
            return pd.DataFrame()
        except Exception as e:
            st.warning(f"Error obteniendo stock: {e}")
            return pd.DataFrame()

    def get_sales_data(self):
        """Trae histórico de ventas"""
        try:
            domain = [['state', 'in', ['sale', 'done']]]
            fields = ['product_id', 'product_uom_qty', 'price_subtotal', 'create_date']
            # Ejecutamos la consulta
            data = self.models.execute_kw(self.db, self.uid, self.password, 'sale.order.line', 'search_read', [domain], {'fields': fields, 'limit': 5000})
            
            if data:
                df = pd.DataFrame(data)
                # Limpieza de datos
                df['product_name'] = df['product_id'].apply(lambda x: x[1] if isinstance(x, list) else 'Desc.')
                df['date'] = pd.to_datetime(df['create_date'])
                df['qty_sold'] = pd.to_numeric(df['product_uom_qty'].fillna(0))
                df['revenue'] = pd.to_numeric(df['price_subtotal'].fillna(0))
                return df[['product_name', 'date', 'qty_sold', 'revenue']]
            return pd.DataFrame()
        except Exception as e:
            st.warning(f"Error obteniendo ventas: {e}")
            return pd.DataFrame()

# --- BLOQUE PRINCIPAL PARA PROBAR QUE FUNCIONA ---
# (Esto solo corre si ejecutas el script directamente, útil para Streamlit)
if __name__ == "__main__":
    st.title("📊 Monitor Odoo - NexusPro")
    
    connector = OdooConnector()
    
    st.subheader("📦 Stock Actual")
    df_stock = connector.get_stock_data()
    if not df_stock.empty:
        st.dataframe(df_stock)
    else:
        st.info("No hay datos de stock o no se pudo conectar.")

    st.subheader("💰 Ventas Recientes")
    df_sales = connector.get_sales_data()
    if not df_sales.empty:
        st.dataframe(df_sales)
    else:
        st.info("No hay datos de ventas o no se pudo conectar.")
