import xmlrpc.client
import pandas as pd
import streamlit as st

class OdooConnector:
    def __init__(self):
        # Cargar credenciales
        try:
            secrets = st.secrets["odoo_connection"]
            self.url = secrets["url"]
            self.db = secrets["db"]
            self.username = secrets["username"]
            self.password = secrets["password"]
            
            # Conexión
            common = xmlrpc.client.ServerProxy(f'{self.url}/xmlrpc/2/common')
            self.uid = common.authenticate(self.db, self.username, self.password, {})
            self.models = xmlrpc.client.ServerProxy(f'{self.url}/xmlrpc/2/object')
            
            if not self.uid:
                st.error("Error de credenciales Odoo.")
                st.stop()
                
        except Exception as e:
            st.error(f"Error de conexión: {e}")
            st.stop()

    def get_stock_clean(self):
        """
        Trae el stock usando los campos confirmados: 'quantity' y 'value'.
        """
        try:
            # Filtramos solo ubicaciones internas
            domain = [['location_id.usage', '=', 'internal']]
            fields = ['product_id', 'quantity', 'value', 'location_id']
            
            data = self.models.execute_kw(self.db, self.uid, self.password,
                'stock.quant', 'search_read', [domain], {'fields': fields, 'limit': 3000})
            
            if data:
                df = pd.DataFrame(data)
                
                # --- LIMPIEZA CRÍTICA (Evita errores de PyArrow) ---
                # Extraemos el nombre del producto de la lista [ID, "Nombre"]
                df['product_name'] = df['product_id'].apply(lambda x: x[1] if isinstance(x, list) else 'N/A')
                # Extraemos nombre de ubicación
                df['location_name'] = df['location_id'].apply(lambda x: x[1] if isinstance(x, list) else 'N/A')
                
                # Aseguramos que los números sean números
                df['quantity'] = df['quantity'].fillna(0).astype(float)
                df['value'] = df['value'].fillna(0).astype(float)
                
                return df[['product_name', 'quantity', 'value', 'location_name']]
            
            return pd.DataFrame(columns=['product_name', 'quantity', 'value', 'location_name'])
            
        except Exception as e:
            st.error(f"Error bajando stock: {e}")
            return pd.DataFrame()

    def get_sales_clean(self):
        """
        Trae ventas usando 'create_date' y 'product_uom_qty'.
        """
        try:
            # Ventas confirmadas o realizadas
            domain = [['state', 'in', ['sale', 'done']]]
            fields = ['product_id', 'product_uom_qty', 'price_subtotal', 'create_date']
            
            data = self.models.execute_kw(self.db, self.uid, self.password,
                'sale.order.line', 'search_read', [domain], {'fields': fields, 'limit': 3000})
            
            if data:
                df = pd.DataFrame(data)
                
                # --- LIMPIEZA CRÍTICA ---
                df['product_name'] = df['product_id'].apply(lambda x: x[1] if isinstance(x, list) else 'N/A')
                df['date'] = pd.to_datetime(df['create_date'])
                
                df['qty_sold'] = df['product_uom_qty'].fillna(0).astype(float)
                df['revenue'] = df['price_subtotal'].fillna(0).astype(float)
                
                return df[['product_name', 'date', 'qty_sold', 'revenue']]
            
            return pd.DataFrame(columns=['product_name', 'date', 'qty_sold', 'revenue'])
            
        except Exception as e:
            st.error(f"Error bajando ventas: {e}")
            return pd.DataFrame()
