import xmlrpc.client
import pandas as pd
import streamlit as st
import os

class OdooConnector:
    def __init__(self):
        try:
            # --- LECTURA DE VARIABLES DE ENTORNO ---
            self.url = os.getenv("URL")
            self.db = os.getenv("DB")
            self.username = os.getenv("USERNAME")
            self.password = os.getenv("PASSWORD")

            if not self.url or not self.db or not self.username or not self.password:
                st.error("❌ Error: Faltan credenciales en las variables de entorno.")
                st.stop()

            # Conexión
            common = xmlrpc.client.ServerProxy(f'{self.url}/xmlrpc/2/common')
            self.uid = common.authenticate(self.db, self.username, self.password, {})
            self.models = xmlrpc.client.ServerProxy(f'{self.url}/xmlrpc/2/object')
            
            if not self.uid:
                st.error("❌ Credenciales inválidas en Odoo.")
                st.stop()
                
        except Exception as e:
            st.error(f"❌ Error crítico de conexión: {e}")
            st.stop()

    def get_products_detailed(self):
        """
        Trae el maestro de productos (Variantes) con sus costos, precios y la referencia madre.
        Modelo: product.product
        """
        fields = [
            'id', 'name', 'default_code', 'categ_id', 'list_price', 
            'standard_price', 'qty_available', 'virtual_available', 
            'uom_id', 'active', 'x_studio_ref_madre' 
        ]
        # Filtramos solo activos para no ensuciar el BI
        domain = [['active', '=', True]]
        data = self.models.execute_kw(self.db, self.uid, self.password, 'product.product', 'search_read', [domain], {'fields': fields, 'limit': 10000})
        
        df = pd.DataFrame(data)
        if not df.empty:
            # Limpieza de campos many2one
            df['categ_name'] = df['categ_id'].apply(lambda x: x[1] if isinstance(x, list) else 'Sin Categoría')
            df['uom_name'] = df['uom_id'].apply(lambda x: x[1] if isinstance(x, list) else '')
            # Renombrar para consistencia
            df.rename(columns={'id': 'product_id', 'qty_available': 'stock_total_teorico'}, inplace=True)
            
            # Asegurar numéricos
            cols_num = ['list_price', 'standard_price', 'stock_total_teorico', 'virtual_available']
            for col in cols_num:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
                
            # Eliminar columnas sucias
            df.drop(columns=['categ_id', 'uom_id'], errors='ignore', inplace=True)
        return df

    def get_stock_quants(self):
        """
        CRUCIAL PARA BI: Trae el stock exacto por ubicación/bodega.
        Modelo: stock.quant
        CORRECCION: Eliminado 'inventory_value' para evitar error en Odoo Community
        """
        fields = ['product_id', 'location_id', 'quantity', 'in_date']
        # Filtramos ubicaciones internas (usage = internal) para no ver stock de clientes/proveedores
        domain = [['location_id.usage', '=', 'internal']]
        data = self.models.execute_kw(self.db, self.uid, self.password, 'stock.quant', 'search_read', [domain], {'fields': fields, 'limit': 10000})
        
        df = pd.DataFrame(data)
        if not df.empty:
            df['product_id'] = df['product_id'].apply(lambda x: x[0] if isinstance(x, list) else x)
            df['location_name'] = df['location_id'].apply(lambda x: x[1] if isinstance(x, list) else 'Desconocida')
            df['quantity'] = pd.to_numeric(df['quantity'], errors='coerce').fillna(0)
            df.rename(columns={'quantity': 'stock_real_ubicacion'}, inplace=True)
            df.drop(columns=['location_id'], errors='ignore', inplace=True)
        return df

    def get_sales_lines(self):
        """
        Trae el detalle de ventas para calcular rotación.
        Modelo: sale.order.line
        """
        fields = ['order_id', 'product_id', 'product_uom_qty', 'qty_delivered', 'price_unit', 'price_subtotal', 'create_date', 'state']
        # Traemos ventas confirmadas o hechas (sale, done)
        domain = [['state', 'in', ['sale', 'done']]] 
        data = self.models.execute_kw(self.db, self.uid, self.password, 'sale.order.line', 'search_read', [domain], {'fields': fields, 'limit': 10000})
        
        df = pd.DataFrame(data)
        if not df.empty:
            df['product_id'] = df['product_id'].apply(lambda x: x[0] if isinstance(x, list) else x)
            df['order_name'] = df['order_id'].apply(lambda x: x[1] if isinstance(x, list) else '')
            df['date'] = pd.to_datetime(df['create_date'])
            df['qty_sold'] = pd.to_numeric(df['product_uom_qty'], errors='coerce').fillna(0)
            df['revenue'] = pd.to_numeric(df['price_subtotal'], errors='coerce').fillna(0)
            
            # Limpieza
            df.drop(columns=['order_id', 'product_uom_qty', 'price_subtotal'], errors='ignore', inplace=True)
        return df

    def get_moves(self):
        """
        Para analizar flujo de movimientos.
        Modelo: stock.move
        """
        fields = ['product_id', 'location_id', 'location_dest_id', 'date', 'product_uom_qty']
        domain = [['state', '=', 'done']]
        data = self.models.execute_kw(self.db, self.uid, self.password, 'stock.move', 'search_read', [domain], {'fields': fields, 'limit': 5000})
        df = pd.DataFrame(data)
        if not df.empty:
            df['product_id'] = df['product_id'].apply(lambda x: x[0] if isinstance(x, list) else x)
            df['origen'] = df['location_id'].apply(lambda x: x[1] if isinstance(x, list) else '')
            df['destino'] = df['location_dest_id'].apply(lambda x: x[1] if isinstance(x, list) else '')
            df['qty'] = pd.to_numeric(df['product_uom_qty'], errors='coerce').fillna(0)
        return df