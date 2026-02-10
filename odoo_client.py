import xmlrpc.client
import pandas as pd
import streamlit as st
import os

class OdooConnector:
    def __init__(self):
        try:
            # --- LECTURA DE VARIABLES DE ENTORNO (COOLIFY) ---
            self.url = os.getenv("URL")
            self.db = os.getenv("DB")
            self.username = os.getenv("USERNAME")
            self.password = os.getenv("PASSWORD")

            # Verificación de seguridad
            if not self.url or not self.db or not self.username or not self.password:
                st.error("❌ Error: Faltan credenciales. Por favor configura URL, DB, USERNAME y PASSWORD en las Variables de Entorno de Coolify.")
                st.stop()

            # Conexión a Odoo (Endpoint Common)
            common = xmlrpc.client.ServerProxy(f'{self.url}/xmlrpc/2/common')
            self.uid = common.authenticate(self.db, self.username, self.password, {})
            self.models = xmlrpc.client.ServerProxy(f'{self.url}/xmlrpc/2/object')
            
            if not self.uid:
                st.error("❌ Credenciales inválidas: Odoo rechazó la conexión. Revisa tu usuario y contraseña.")
                st.stop()
                
        except Exception as e:
            st.error(f"❌ Error de conexión crítico con Odoo: {e}")
            st.stop()

    def get_stock_data(self):
        """Stock a nivel variante desde product.product (qty_available)."""
        fields = ['id', 'name', 'qty_available', 'standard_price', 'categ_id']
        data = self.models.execute_kw(self.db, self.uid, self.password, 'product.product', 'search_read', [[]], {'fields': fields, 'limit': 10000})
        df = pd.DataFrame(data)
        if not df.empty:
            df.rename(columns={'id': 'product_id', 'qty_available': 'quantity', 'name': 'product_name'}, inplace=True)
            df['quantity'] = pd.to_numeric(df['quantity'], errors='coerce').fillna(0).clip(lower=0)  # sin negativos
            df['standard_price'] = pd.to_numeric(df['standard_price'], errors='coerce').fillna(0)
        return df

    def get_product_data(self):
        fields = ['id', 'name', 'default_code', 'list_price', 'standard_price', 'categ_id', 'active']
        data = self.models.execute_kw(self.db, self.uid, self.password, 'product.product', 'search_read', [[]], {'fields': fields, 'limit': 10000})
        df = pd.DataFrame(data)
        if not df.empty:
            # Extrae nombre de categoría de forma robusta y elimina la columna original para evitar inferencias problemáticas
            def extract_categ_name(x):
                if isinstance(x, list) and len(x) > 1:
                    return x[1]
                if isinstance(x, (str, int, float)):
                    return str(x)
                return None
            if 'categ_id' in df.columns:
                df['categ_id_nombre'] = df['categ_id'].apply(extract_categ_name)
                # elimina la columna original para evitar que pandas intente convertir tipos mixtos
                df.drop(columns=['categ_id'], inplace=True, errors='ignore')
        return df

    def get_product_template_data(self):
        """Extrae todos los campos relevantes de product.template."""
        fields = [
            'id', 'name', 'default_code', 'barcode', 'categ_id', 'qty_available', 'virtual_available',
            'incoming_qty', 'outgoing_qty', 'list_price', 'standard_price', 'sale_ok', 'purchase_ok',
            'active', 'weight', 'volume', 'uom_id', 'company_id', 'description', 'description_sale',
            'description_purchase', 'image_1920', 'website_published', 'website_url', 'x_studio_ref_madre'
        ]
        data = self.models.execute_kw(self.db, self.uid, self.password, 'product.template', 'search_read', [[]], {'fields': fields, 'limit': 10000})
        df = pd.DataFrame(data)
        if not df.empty:
            # Normaliza campos many2one
            df['categ_id_nombre'] = df['categ_id'].apply(lambda x: x[1] if isinstance(x, list) and len(x) > 1 else None)
            df['uom_name'] = df['uom_id'].apply(lambda x: x[1] if isinstance(x, list) and len(x) > 1 else None)
            df['company_name'] = df['company_id'].apply(lambda x: x[1] if isinstance(x, list) and len(x) > 1 else None)
            df.drop(columns=['categ_id', 'uom_id', 'company_id'], inplace=True, errors='ignore')
        return df

    def get_product_variant_data(self):
        """Lee variantes de producto (product.product) y su cantidad disponible."""
        fields = ['id', 'product_tmpl_id', 'name', 'default_code', 'categ_id', 'qty_available', 'list_price', 'standard_price', 'active']
        data = self.models.execute_kw(self.db, self.uid, self.password, 'product.product', 'search_read', [[]], {'fields': fields, 'limit': 10000})
        df = pd.DataFrame(data)
        if not df.empty:
            def extract_categ_name(x):
                if isinstance(x, list) and len(x) > 1:
                    return x[1]
                if isinstance(x, (str, int, float)):
                    return str(x)
                return None
            if 'categ_id' in df.columns:
                df['categ_id_nombre'] = df['categ_id'].apply(extract_categ_name)
                df.drop(columns=['categ_id'], inplace=True, errors='ignore')
            # Extrae nombre de plantilla si es many2one
            if 'product_tmpl_id' in df.columns:
                df['product_template_name'] = df['product_tmpl_id'].apply(lambda x: x[1] if isinstance(x, list) and len(x) > 1 else None)
        return df

    def get_sales_data(self):
        """Extrae ventas de sale.order.line (todas las líneas para pruebas)."""
        fields = ['id', 'order_id', 'product_id', 'product_uom_qty', 'price_subtotal', 'create_date', 'state']
        domain = []  # sin filtro de estado para no perder ventas de prueba
        data = self.models.execute_kw(self.db, self.uid, self.password, 'sale.order.line', 'search_read', [domain], {'fields': fields, 'limit': 10000})
        df = pd.DataFrame(data)
        if not df.empty:
            df['product_id'] = df['product_id'].apply(lambda x: x[0] if isinstance(x, list) else x)
            df['qty_sold'] = pd.to_numeric(df['product_uom_qty'], errors='coerce').fillna(0)
            df['revenue'] = pd.to_numeric(df['price_subtotal'], errors='coerce').fillna(0)
            df['date'] = pd.to_datetime(df['create_date'])
        return df

    def get_location_data(self):
        fields = ['id', 'name', 'usage', 'company_id']
        data = self.models.execute_kw(self.db, self.uid, self.password, 'stock.location', 'search_read', [[]], {'fields': fields, 'limit': 1000})
        df = pd.DataFrame(data)
        if not df.empty:
            # Normaliza company_id para mostrar solo el nombre
            df['company_name'] = df['company_id'].apply(
                lambda x: x[1] if isinstance(x, list) and len(x) > 1 else (x if isinstance(x, str) else None)
            )
            # Elimina la columna original para evitar problemas de tipo
            df.drop(columns=['company_id'], inplace=True, errors='ignore')
        return df

    def get_stock_move_data(self):
        fields = ['product_id', 'location_id', 'location_dest_id', 'state', 'date', 'product_qty']
        data = self.models.execute_kw(self.db, self.uid, self.password, 'stock.move', 'search_read', [[]], {'fields': fields, 'limit': 10000})
        df = pd.DataFrame(data)
        if not df.empty:
            df['product_id'] = df['product_id'].apply(lambda x: x[0] if isinstance(x, list) else x)
            df['product_name'] = df['product_id'].apply(lambda x: x[1] if isinstance(x, list) and len(x) > 1 else None)
            df['location_id'] = df['location_id'].apply(lambda x: x[0] if isinstance(x, list) else x)
            df['location_name'] = df['location_id'].apply(lambda x: x[1] if isinstance(x, list) and len(x) > 1 else None)
            df['location_dest_id'] = df['location_dest_id'].apply(lambda x: x[0] if isinstance(x, list) else x)
            df['location_dest_name'] = df['location_dest_id'].apply(lambda x: x[1] if isinstance(x, list) and len(x) > 1 else None)
            df['quantity_done'] = pd.to_numeric(df['product_qty'], errors='coerce').fillna(0)
            df['date'] = pd.to_datetime(df['date'])
        return df

    def get_partner_data(self):
        fields = ['id', 'name', 'email', 'phone', 'customer_rank']
        data = self.models.execute_kw(self.db, self.uid, self.password, 'res.partner', 'search_read', [[['customer_rank', '>', 0]]], {'fields': fields, 'limit': 10000})
        return pd.DataFrame(data)

    def get_purchase_order_line_data(self):
        fields = ['product_id', 'order_id', 'product_qty', 'price_unit', 'date_planned']
        data = self.models.execute_kw(self.db, self.uid, self.password, 'purchase.order.line', 'search_read', [[]], {'fields': fields, 'limit': 10000})
        df = pd.DataFrame(data)
        if not df.empty:
            df['product_id'] = df['product_id'].apply(lambda x: x[0] if isinstance(x, list) else x)
            df['product_name'] = df['product_id'].apply(lambda x: x[1] if isinstance(x, list) and len(x) > 1 else None)
            # Normaliza order_id para mostrar solo el nombre
            df['order_id_nombre'] = df['order_id'].apply(
                lambda x: x[1] if isinstance(x, list) and len(x) > 1 else (x if isinstance(x, str) else None)
            )
            # Elimina la columna original para evitar problemas de tipo
            df.drop(columns=['order_id'], inplace=True, errors='ignore')
            df['qty'] = pd.to_numeric(df['product_qty'], errors='coerce').fillna(0)
            df['price_unit'] = pd.to_numeric(df['price_unit'], errors='coerce').fillna(0)
            df['date_planned'] = pd.to_datetime(df['date_planned'])
        return df
