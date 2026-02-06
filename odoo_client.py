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
        """Trae stock valorizado y cantidades"""
        domain = [['location_id.usage', '=', 'internal']]
        fields = ['product_id', 'quantity', 'value', 'location_id', 'in_date']
        
        data = self.models.execute_kw(self.db, self.uid, self.password, 'stock.quant', 'search_read', [domain], {'fields': fields, 'limit': 10000})
        
        df = pd.DataFrame(data)
        if not df.empty:
            df['product_id'] = df['product_id'].apply(lambda x: x[0] if isinstance(x, list) else x)
            df['product_name'] = df['product_id'].apply(lambda x: x[1] if isinstance(x, list) and len(x) > 1 else None)
            df['location_id'] = df['location_id'].apply(lambda x: x[0] if isinstance(x, list) else x)
            df['location_name'] = df['location_id'].apply(lambda x: x[1] if isinstance(x, list) and len(x) > 1 else None)
            df['quantity'] = pd.to_numeric(df['quantity'], errors='coerce').fillna(0)
            df['value'] = pd.to_numeric(df['value'], errors='coerce').fillna(0)
        return df

    def get_product_data(self):
        fields = ['id', 'name', 'default_code', 'list_price', 'standard_price', 'categ_id', 'active']
        data = self.models.execute_kw(self.db, self.uid, self.password, 'product.product', 'search_read', [[]], {'fields': fields, 'limit': 10000})
        df = pd.DataFrame(data)
        if not df.empty:
            df['category_id'] = df['categ_id'].apply(lambda x: x[0] if isinstance(x, list) else x)
            df['category_name'] = df['categ_id'].apply(lambda x: x[1] if isinstance(x, list) and len(x) > 1 else None)
        return df

    def get_sales_data(self):
        fields = [
            'id', 'order_id', 'product_id', 'product_uom_qty', 'qty_delivered',
            'price_unit', 'price_subtotal', 'create_date', 'state', 'warehouse_id',
            'qty_invoiced', 'qty_to_invoice'
        ]
        domain = [['state', 'in', ['sale', 'done']]]
        data = self.models.execute_kw(self.db, self.uid, self.password, 'sale.order.line', 'search_read', [domain], {'fields': fields, 'limit': 10000})
        df = pd.DataFrame(data)
        if not df.empty:
            df['product_id'] = df['product_id'].apply(lambda x: x[0] if isinstance(x, list) else x)
            df['product_name'] = df['product_id'].apply(lambda x: x[1] if isinstance(x, list) and len(x) > 1 else None)
            df['order_id'] = df['order_id'].apply(lambda x: x[0] if isinstance(x, list) else x)
            df['order_name'] = df['order_id'].apply(lambda x: x[1] if isinstance(x, list) and len(x) > 1 else None)
            df['warehouse_id'] = df['warehouse_id'].apply(lambda x: x[0] if isinstance(x, list) else x) if 'warehouse_id' in df else None
            df['warehouse_name'] = df['warehouse_id'].apply(lambda x: x[1] if isinstance(x, list) and len(x) > 1 else None) if 'warehouse_id' in df else None
            df['qty_sold'] = pd.to_numeric(df['product_uom_qty'], errors='coerce').fillna(0)
            df['revenue'] = pd.to_numeric(df['price_subtotal'], errors='coerce').fillna(0)
            df['date'] = pd.to_datetime(df['create_date'])
        return df

    def get_location_data(self):
        fields = ['id', 'name', 'usage', 'company_id']
        data = self.models.execute_kw(self.db, self.uid, self.password, 'stock.location', 'search_read', [[]], {'fields': fields, 'limit': 1000})
        df = pd.DataFrame(data)
        if not df.empty:
            df['company_name'] = df['company_id'].apply(lambda x: x[1] if isinstance(x, list) and len(x) > 1 else None)
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
            df['qty'] = pd.to_numeric(df['product_qty'], errors='coerce').fillna(0)
            df['price_unit'] = pd.to_numeric(df['price_unit'], errors='coerce').fillna(0)
            df['date_planned'] = pd.to_datetime(df['date_planned'])
        return df
