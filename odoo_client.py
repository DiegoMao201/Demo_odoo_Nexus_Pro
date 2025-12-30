import xmlrpc.client
import pandas as pd
import streamlit as st

class OdooConnector:
    def __init__(self):
        try:
            secrets = st.secrets["odoo_connection"]
            self.url = secrets["url"]
            self.db = secrets["db"]
            self.username = secrets["username"]
            self.password = secrets["password"]
            
            common = xmlrpc.client.ServerProxy(f'{self.url}/xmlrpc/2/common')
            self.uid = common.authenticate(self.db, self.username, self.password, {})
            self.models = xmlrpc.client.ServerProxy(f'{self.url}/xmlrpc/2/object')
            
            if not self.uid:
                st.error("Credenciales inválidas.")
                st.stop()
        except Exception as e:
            st.error(f"Error conexión: {e}")
            st.stop()

    def get_stock_data(self):
        """Trae stock valorizado y cantidades"""
        try:
            domain = [['location_id.usage', '=', 'internal']]
            fields = ['product_id', 'quantity', 'value', 'location_id']
            data = self.models.execute_kw(self.db, self.uid, self.password, 'stock.quant', 'search_read', [domain], {'fields': fields, 'limit': 5000})
            
            if data:
                df = pd.DataFrame(data)
                df['product_name'] = df['product_id'].apply(lambda x: x[1] if isinstance(x, list) else 'Desc.')
                df['location_name'] = df['location_id'].apply(lambda x: x[1] if isinstance(x, list) else 'Desc.')
                df['quantity'] = pd.to_numeric(df['quantity'].fillna(0))
                df['value'] = pd.to_numeric(df['value'].fillna(0))
                return df[['product_name', 'quantity', 'value', 'location_name']]
            return pd.DataFrame()
        except Exception:
            return pd.DataFrame()

    def get_sales_data(self):
        """Trae histórico de ventas"""
        try:
            domain = [['state', 'in', ['sale', 'done']]]
            fields = ['product_id', 'product_uom_qty', 'price_subtotal', 'create_date']
            data = self.models.execute_kw(self.db, self.uid, self.password, 'sale.order.line', 'search_read', [domain], {'fields': fields, 'limit': 5000})
            
            if data:
                df = pd.DataFrame(data)
                df['product_name'] = df['product_id'].apply(lambda x: x[1] if isinstance(x, list) else 'Desc.')
                df['date'] = pd.to_datetime(df['create_date'])
                df['qty_sold'] = pd.to_numeric(df['product_uom_qty'].fillna(0))
                df['revenue'] = pd.to_numeric(df['price_subtotal'].fillna(0))
                return df[['product_name', 'date', 'qty_sold', 'revenue']]
            return pd.DataFrame()
        except Exception:
            return pd.DataFrame()
