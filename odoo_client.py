import xmlrpc.client
import pandas as pd
import streamlit as st

class OdooConnector:
    def __init__(self):
        # Cargar credenciales desde los secretos de Streamlit
        try:
            self.url = st.secrets["odoo_connection"]["url"]
            self.db = st.secrets["odoo_connection"]["db"]
            self.username = st.secrets["odoo_connection"]["username"]
            self.password = st.secrets["odoo_connection"]["password"]
        except FileNotFoundError:
            st.error("No se encontró el archivo .streamlit/secrets.toml")
            st.stop()

        # Endpoints comunes de Odoo
        self.common = xmlrpc.client.ServerProxy('{}/xmlrpc/2/common'.format(self.url))
        self.models = xmlrpc.client.ServerProxy('{}/xmlrpc/2/object'.format(self.url))
        self.uid = self._authenticate()

    def _authenticate(self):
        """Autentica y devuelve el User ID (uid)"""
        try:
            uid = self.common.authenticate(self.db, self.username, self.password, {})
            if not uid:
                st.error("Fallo de autenticación: Revisa usuario/contraseña/base de datos.")
                st.stop()
            return uid
        except Exception as e:
            st.error(f"Error de conexión con Odoo: {e}")
            st.stop()

    def get_data(self, model_name, fields, domain=None, limit=1000):
        """
        Función genérica para traer datos de cualquier modelo.
        Args:
            model_name (str): Ejemplo 'sale.order.line' o 'stock.quant'
            fields (list): Lista de columnas a traer ['name', 'price_unit']
            domain (list): Filtros de Odoo [['state', '=', 'sale']]
            limit (int): Límite de registros para no saturar
        """
        if domain is None:
            domain = []
            
        try:
            # Llamada a la API de Odoo (execute_kw)
            records = self.models.execute_kw(
                self.db, self.uid, self.password,
                model_name, 'search_read',
                [domain],
                {'fields': fields, 'limit': limit}
            )
            
            if not records:
                return pd.DataFrame() # Retorna vacío si no hay datos
                
            return pd.DataFrame(records)
            
        except Exception as e:
            st.error(f"Error consultando {model_name}: {e}")
            return pd.DataFrame()

    def get_stock(self):
        """Trae inventario actual (stock.quant)"""
        # Filtramos por ubicación de stock interno ('usage'='internal')
        domain = [['location_id.usage', '=', 'internal']]
        fields = ['product_id', 'location_id', 'quantity', 'inventory_date']
        df = self.get_data('stock.quant', fields, domain, limit=2000)
        
        # Limpieza: Odoo devuelve [id, nombre], separamos solo el nombre
        if not df.empty:
            df['product_name'] = df['product_id'].apply(lambda x: x[1] if x else 'N/A')
            df['location_name'] = df['location_id.usage'].apply(lambda x: x[1] if x else 'N/A')
        return df

    def get_sales(self):
        """Trae líneas de ventas confirmadas para análisis de rotación"""
        # Filtramos pedidos confirmados o realizados
        domain = [['state', 'in', ['sale', 'done']]]
        # Usamos sale.order.line para tener detalle de producto
        fields = ['order_id', 'product_id', 'product_uom_qty', 'price_unit', 'create_date']
        df = self.get_data('sale.order.line', fields, domain, limit=2000)
        
        if not df.empty:
            df['product_name'] = df['product_id'].apply(lambda x: x[1] if x else 'N/A')
            # Convertir fecha a datetime
            df['create_date'] = pd.to_datetime(df['create_date'])
        return df
