import os
import pandas as pd
from sqlalchemy import create_engine
from odoo_client import OdooConnector

EMPRESA_ID = 1  # ID de odoo_triunfo

def upload_odoo_data_to_postgres(pg_url):
    connector = OdooConnector()
    engine = create_engine(pg_url)

    # STOCK POR UBICACION
    df_stock = connector.get_stock_data()
    if not df_stock.empty:
        df_stock['empresa_id'] = EMPRESA_ID
        df_stock.rename(columns={
            'product_name': 'producto_nombre',
            'quantity': 'cantidad',
            'value': 'valor',
            'location_name': 'ubicacion_nombre'
        }, inplace=True)
        df_stock.to_sql('stock_por_ubicacion', engine, if_exists='replace', index=False)

    # VENTAS
    df_sales = connector.get_sales_data()
    if not df_sales.empty:
        # Extrae solo el ID de order_id si es lista
        df_sales['order_id'] = df_sales['order_id'].apply(lambda x: x[0] if isinstance(x, list) else x)
        df_sales['empresa_id'] = EMPRESA_ID
        df_sales.rename(columns={
            'product_name': 'producto_nombre',
            'date': 'fecha',
            'qty_sold': 'cantidad_vendida',
            'revenue': 'subtotal_venta'
        }, inplace=True)
        df_sales.to_sql('venta_linea', engine, if_exists='replace', index=False)

    # PRODUCTOS
    fields_prod = ['name', 'default_code', 'list_price', 'standard_price', 'categ_id']
    data_prod = connector.models.execute_kw(connector.db, connector.uid, connector.password, 'product.product', 'search_read', [[]], {'fields': fields_prod, 'limit': 5000})
    df_prod = pd.DataFrame(data_prod)
    if not df_prod.empty:
        df_prod['empresa_id'] = EMPRESA_ID
        # Extrae solo el nombre de la categoría
        df_prod['categoria'] = df_prod['categ_id'].apply(lambda x: x[1] if isinstance(x, list) and len(x) > 1 else None)
        df_prod.rename(columns={
            'name': 'nombre',
            'default_code': 'codigo_interno',
            'list_price': 'precio_venta',
            'standard_price': 'precio_costo',
            # 'categ_id': 'categoria'  # Ya lo transformaste arriba
        }, inplace=True)
        # Elimina la columna categ_id original para evitar problemas
        df_prod.drop(columns=['categ_id'], inplace=True)
        df_prod.to_sql('producto', engine, if_exists='replace', index=False)

    # CLIENTES
    fields_partner = ['name', 'email', 'phone', 'customer_rank']
    data_partner = connector.models.execute_kw(connector.db, connector.uid, connector.password, 'res.partner', 'search_read', [[['customer_rank', '>', 0]]], {'fields': fields_partner, 'limit': 5000})
    df_partner = pd.DataFrame(data_partner)
    if not df_partner.empty:
        df_partner['empresa_id'] = EMPRESA_ID
        df_partner.rename(columns={
            'name': 'nombre',
            'email': 'correo',
            'phone': 'telefono',
            'customer_rank': 'rango_cliente'
        }, inplace=True)
        df_partner.to_sql('cliente', engine, if_exists='replace', index=False)

    print("✅ Datos subidos a PostgreSQL correctamente.")

# Ejemplo de uso:
pg_url = (
    f"postgresql://{os.getenv('PG_USER')}:{os.getenv('PG_PASSWORD')}"
    f"@{os.getenv('PG_HOST')}:{os.getenv('PG_PORT')}/{os.getenv('PG_DB')}"
)
upload_odoo_data_to_postgres(pg_url)