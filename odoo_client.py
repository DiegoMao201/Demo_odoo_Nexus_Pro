import xmlrpc.client
import pandas as pd
import streamlit as st

class OdooConnector:
    def __init__(self):
        # 1. Cargar credenciales
        try:
            secrets = st.secrets["odoo_connection"]
            self.url = secrets["url"]
            self.username = secrets["username"]
            self.password = secrets["password"] # Aquí usaremos tu API Key
            self.db = secrets.get("db", "").strip() # Puede estar vacío
        except Exception:
            st.error("Error: Falta el archivo .streamlit/secrets.toml o los datos están incompletos.")
            st.stop()

        # 2. Auto-descubrir Base de Datos si no se proporcionó
        if not self.db:
            self.db = self._discover_db()
            if not self.db:
                st.error("No se pudo detectar ninguna base de datos en esa URL. Necesitas conseguir el nombre exacto.")
                st.stop()
            else:
                # Mostramos en sidebar a qué DB se conectó (útil para verificar)
                st.sidebar.info(f"📡 DB Detectada: {self.db}")

        # 3. Configurar Endpoints
        try:
            self.common = xmlrpc.client.ServerProxy('{}/xmlrpc/2/common'.format(self.url))
            self.models = xmlrpc.client.ServerProxy('{}/xmlrpc/2/object'.format(self.url))
            self.uid = self._authenticate()
        except Exception as e:
            st.error(f"Error de conexión general con Odoo: {e}")
            st.stop()

    def _discover_db(self):
        """Consulta al servidor la lista de bases de datos disponibles"""
        try:
            # Endpoint especial para listar bases de datos
            db_proxy = xmlrpc.client.ServerProxy('{}/xmlrpc/2/db'.format(self.url))
            dbs = db_proxy.list()
            if dbs and isinstance(dbs, list):
                return dbs[0] # Retorna la primera que encuentre
            return None
        except Exception as e:
            st.warning(f"No se pudo auto-detectar la base de datos: {e}")
            return None

    def _authenticate(self):
        """Autentica usando la API Key como password"""
        try:
            uid = self.common.authenticate(self.db, self.username, self.password, {})
            if not uid:
                st.error("❌ Fallo de autenticación. Verifica que tu API Key sea correcta y el usuario tenga permisos.")
                st.stop()
            return uid
        except Exception as e:
            st.error(f"Error autenticando: {e}")
            st.stop()

    def get_data(self, model_name, fields, domain=None, limit=1000):
        """Función genérica de consulta"""
        if domain is None: domain = []
        try:
            records = self.models.execute_kw(
                self.db, self.uid, self.password,
                model_name, 'search_read',
                [domain],
                {'fields': fields, 'limit': limit}
            )
            return pd.DataFrame(records) if records else pd.DataFrame()
        except Exception as e:
            st.error(f"Error consultando modelo {model_name}: {e}")
            return pd.DataFrame()

    def get_stock_analysis(self):
        """
        Trae datos combinados para análisis de rotación.
        Nota: Ajustado para buscar en 'product.product' y 'stock.quant'
        """
        # 1. Traemos el stock actual
        domain = [['location_id.usage', '=', 'internal']] # Solo bodegas internas
        fields = ['product_id', 'quantity', 'location_id', 'in_date']
        df_stock = self.get_data('stock.quant', fields, domain, limit=1500)
        
        if not df_stock.empty:
            # Limpieza de nombres que vienen como [id, nombre]
            df_stock['product_name'] = df_stock['product_id'].apply(lambda x: x[1] if x else 'Descocido')
            df_stock['location_name'] = df_stock['location_id'].apply(lambda x: x[1] if x else 'Descocido')
            # Rellenar nulos
            df_stock['quantity'] = df_stock['quantity'].fillna(0)
            
        return df_stock

    def get_sales_history(self):
        """Histórico de ventas para calcular demanda"""
        # Ventas confirmadas o realizadas
        domain = [['state', 'in', ['sale', 'done']]] 
        fields = ['product_id', 'product_uom_qty', 'price_subtotal', 'date_order']
        # Consultamos líneas de venta (detalle)
        df_sales = self.get_data('sale.order.line', fields, domain, limit=1500)
        
        if not df_sales.empty:
            df_sales['product_name'] = df_sales['product_id'].apply(lambda x: x[1] if x else 'N/A')
            df_sales['date'] = pd.to_datetime(df_sales['date_order'])
        
        return df_sales
