import xmlrpc.client

url = "https://inversionescd-pruebatriunfo130126-27436464.dev.odoo.com"
db = "inversionescd-pruebatriunfo130126-27436464"
username = "tu_correo@ejemplo.com"
apikey = "cd879748d3e646604a404ea7659b0afd3812452f"

# --- NUEVO BLOQUE: LISTAR BASES DE DATOS DISPONIBLES ---
try:
    db_sock = xmlrpc.client.ServerProxy(url + '/xmlrpc/2/db')
    dbs = db_sock.list()
    print("📂 BASES DE DATOS DISPONIBLES EN ESTA URL:")
    print(dbs)
    if db not in dbs:
        print(f"❌ La base de datos '{db}' NO está en la lista de bases disponibles.")
    else:
        print(f"✅ La base de datos '{db}' está disponible.")
except Exception as e:
    print(f"Error al listar bases de datos: {e}")

print("🧪 Test de Conexión Odoo")

try:
    common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
    version = common.version()
    print(f"📡 El servidor responde. Versión Odoo: {version.get('server_version')}")
    uid = common.authenticate(db, username, apikey, {})
    if uid:
        print(f"✅ ¡Autenticación EXITOSA! Tu UID es: {uid}")
        models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")
        count = models.execute_kw(db, uid, apikey, 'sale.order', 'search_count', [[]])
        print(f"🔢 Tienes {count} órdenes de venta en el sistema.")
    else:
        print("❌ La autenticación falló (uid es False).")
        print("""
        Posibles causas:
        1. El nombre de la base de datos no es exacto.
        2. El correo no tiene acceso a ESTA base de datos de desarrollo.
        3. No estás usando una API Key válida (genérala en Preferencias > Seguridad de la cuenta).
        """)
except Exception as e:
    print(f"💀 Error de conexión grave: {e}")