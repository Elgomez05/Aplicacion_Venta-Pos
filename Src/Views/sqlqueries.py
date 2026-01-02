import pyodbc
import logging

# server = 'DESKTOP-QGCQ59D\SQLEXPRESS' 
# database = 'master'  
# username = 'Elgomez05'
# password = '123456'
#Recordatorio tener presente que cuando sea para instalar el sistema Pos a otro Pc modificar el settings database = master . por que de hay se crea la base de datos original "PuntoventaDB"

from Src.Config.config_loader import config

db_cfg = config.get("database")
server = db_cfg["server"]
database = db_cfg["database"]
username = db_cfg["username"]
password = db_cfg["password"]


class QueriesSQLServer:
    connection = None

    @staticmethod
    def create_connection(server=server, database=database, username=username, password=password):
        try:
            if QueriesSQLServer.connection is not None:
                try:
                    QueriesSQLServer.connection.cursor().execute("SELECT 1")
                    return QueriesSQLServer.connection
                except:
                    logging.warning("Conexión caída, re conectando...")

            QueriesSQLServer.connection = pyodbc.connect(
                'DRIVER={ODBC Driver 17 for SQL Server};'
                f'SERVER={server};'
                f'DATABASE={database};'
                f'UID={username};'
                f'PWD={password}'
            )
            logging.info("Connection to SQL Server DB successful")
            return QueriesSQLServer.connection

        except Exception as e:
            logging.error(f"Error conexión DB: {e}")
            raise
        

    @staticmethod
    def execute_query(connection, query, data_tuple=()):
        cursor = connection.cursor()
        try:
            cursor.execute(query, data_tuple)
            connection.commit()
            
            query_lower = query.strip().lower()
            if query_lower.startswith("insert") and ("ventas" in query_lower or "ventas_detalle" in query_lower):
                cursor.execute("SELECT @@IDENTITY")
                last_id = cursor.fetchone()[0]
                return last_id
                
            return None
        except Exception as e:
            logging.error(f"Error al ejecutar la consulta: {e}")
            raise


    @staticmethod
    def execute_read_query(connection, query, data_tuple=()):
        cursor = connection.cursor()
        result = None
        try:
            cursor.execute(query, data_tuple)  
            result = cursor.fetchall()
            return result
        except Exception as e:
            logging.error(f"Error al ejecutar la consulta: {e}")
            return None

    @staticmethod
    def alter_productos_add_fields():
        connection = QueriesSQLServer.create_connection(server, 'PuntoventaDB', username, password)
        if not connection:
            return

        alter_queries = [
            """
            IF COL_LENGTH('productos', 'catalogo') IS NULL
            BEGIN
                ALTER TABLE productos ADD catalogo NVARCHAR(100) NOT NULL DEFAULT 'GENERAL'
            END
            """,
            """
            IF COL_LENGTH('productos', 'precio_compra') IS NULL
            BEGIN
                ALTER TABLE productos ADD precio_compra DECIMAL(18,2) NOT NULL DEFAULT 0
            END
            """,
            """
            IF COL_LENGTH('productos', 'activo') IS NULL
            BEGIN
                ALTER TABLE productos ADD activo BIT NOT NULL DEFAULT 1
            END
            """
        ]
        for q in alter_queries:
            QueriesSQLServer.execute_query(connection, q)

        QueriesSQLServer.execute_query(
            connection,
            "UPDATE productos SET activo = 1 WHERE activo IS NULL"
        )

    @staticmethod
    def alter_usuarios_add_fields():
        connection = QueriesSQLServer.create_connection(server, 'PuntoventaDB', username, password)
        if not connection:
            return

        alter_queries = [
            """
            IF COL_LENGTH('usuarios', 'activo') IS NULL
            BEGIN
                ALTER TABLE usuarios ADD activo BIT NOT NULL DEFAULT 1
            END
            """
        ]

        for q in alter_queries:
            QueriesSQLServer.execute_query(connection, q)

        QueriesSQLServer.execute_query(
            connection,
            "UPDATE usuarios SET activo = 1 WHERE activo IS NULL"
        )


    @staticmethod
    def create_tables():
        connection = QueriesSQLServer.create_connection(server, 'PuntoventaDB', username, password)

        if not connection:
            logging.error("Error: No se pudo establecer conexión para crear las tablas.")
            return

        # Crear tabla productos
        create_productos_table = """
        IF NOT EXISTS (SELECT * FROM sysobjects WHERE name = 'productos' AND xtype = 'U')
        BEGIN
            CREATE TABLE productos (
                codigo NVARCHAR(50) PRIMARY KEY, 
                nombre NVARCHAR(255) NOT NULL, 
                precio DECIMAL(18, 2) NOT NULL, 
                cantidad INT NOT NULL,
                catalogo NVARCHAR(100) NOT NULL DEFAULT 'GENERAL',
                precio_compra DECIMAL(18,2) NOT NULL DEFAULT 0,
                activo BIT DEFAULT 1

            );
        END;
        """
        QueriesSQLServer.execute_query(connection, create_productos_table)

        # Crear tabla usuarios
        create_usuarios_table = """
        IF NOT EXISTS (SELECT * FROM sysobjects WHERE name = 'usuarios' AND xtype = 'U')
        BEGIN
            CREATE TABLE usuarios (
                username NVARCHAR(50) PRIMARY KEY, 
                nombre NVARCHAR(255) NOT NULL, 
                password NVARCHAR(255) NOT NULL,
                tipo NVARCHAR(50) NOT NULL,
                activo BIT DEFAULT 1
            );
        END;
        """
        QueriesSQLServer.execute_query(connection, create_usuarios_table)

        # Crear tabla ventas
        create_ventas_table = """
        IF NOT EXISTS (SELECT * FROM sysobjects WHERE name = 'ventas' AND xtype = 'U')
        BEGIN
            CREATE TABLE ventas (
                id INT IDENTITY(1,1) PRIMARY KEY,  
                total DECIMAL(18, 2) NOT NULL,
                fecha DATETIME NOT NULL,
                username NVARCHAR(50) NOT NULL,
                -- NUEVOS CAMPOS PARA FACTURACIÓN
                id_factura NVARCHAR(50) NULL,
                id_turno INT NULL,
                id_dispositivo INT NULL,
                prefijo_resolucion NVARCHAR(20) NULL,
                num_resolucion NVARCHAR(50) NULL,
                consecutivo INT NULL,
                subtotal DECIMAL(18, 2) NULL,
                impuestos DECIMAL(18, 2) NULL,
                metodo_pago INT NULL DEFAULT 0,
                detalles_pago NVARCHAR(500) NULL,
                receipt_data TEXT NULL,
                json_factura NVARCHAR(MAX) NULL,
                FOREIGN KEY(username) REFERENCES usuarios(username)
            );
        END
        ELSE
        BEGIN
            -- Agregar campos si la tabla ya existe
            IF COL_LENGTH('ventas', 'id_factura') IS NULL
                ALTER TABLE ventas ADD id_factura NVARCHAR(50) NULL;
            
            IF COL_LENGTH('ventas', 'id_turno') IS NULL
                ALTER TABLE ventas ADD id_turno INT NULL;
            
            IF COL_LENGTH('ventas', 'id_dispositivo') IS NULL
                ALTER TABLE ventas ADD id_dispositivo INT NULL;
            
            IF COL_LENGTH('ventas', 'prefijo_resolucion') IS NULL
                ALTER TABLE ventas ADD prefijo_resolucion NVARCHAR(20) NULL;
            
            IF COL_LENGTH('ventas', 'num_resolucion') IS NULL
                ALTER TABLE ventas ADD num_resolucion NVARCHAR(50) NULL;
            
            IF COL_LENGTH('ventas', 'consecutivo') IS NULL
                ALTER TABLE ventas ADD consecutivo INT NULL;
            
            IF COL_LENGTH('ventas', 'subtotal') IS NULL
                ALTER TABLE ventas ADD subtotal DECIMAL(18, 2) NULL;
            
            IF COL_LENGTH('ventas', 'impuestos') IS NULL
                ALTER TABLE ventas ADD impuestos DECIMAL(18, 2) NULL;
            
            IF COL_LENGTH('ventas', 'metodo_pago') IS NULL
                ALTER TABLE ventas ADD metodo_pago INT NULL DEFAULT 0;
            
            IF COL_LENGTH('ventas', 'detalles_pago') IS NULL
                ALTER TABLE ventas ADD detalles_pago NVARCHAR(500) NULL;
            
            IF COL_LENGTH('ventas', 'receipt_data') IS NULL
                ALTER TABLE ventas ADD receipt_data TEXT NULL;
            
            IF COL_LENGTH('ventas', 'json_factura') IS NULL
                ALTER TABLE ventas ADD json_factura NVARCHAR(MAX) NULL;
        END;
        """
        QueriesSQLServer.execute_query(connection, create_ventas_table)

        create_turnos_table = """
        IF NOT EXISTS (SELECT * FROM sysobjects WHERE name = 'turnos' AND xtype = 'U')
        BEGIN
            CREATE TABLE turnos (
                id INT IDENTITY(1,1) PRIMARY KEY,
                id_turno INT NOT NULL,
                id_dispositivo INT NOT NULL,
                fecha_apertura DATETIME NOT NULL,
                fecha_cierre DATETIME NULL,
                estado INT NOT NULL,
                total_facturas INT DEFAULT 0,
                total_ventas DECIMAL(18,2) DEFAULT 0,
                json_data NVARCHAR(MAX) NULL
            );
        END;
        """
        QueriesSQLServer.execute_query(connection, create_turnos_table)

        # Crear tabla ventas_detalle
        create_ventas_detalle_table = """
        IF NOT EXISTS (SELECT * FROM sysobjects WHERE name = 'ventas_detalle' AND xtype = 'U')
        BEGIN
            CREATE TABLE ventas_detalle (
                id INT IDENTITY(1,1) PRIMARY KEY, 
                id_venta INT NOT NULL, 
                precio DECIMAL(18, 2) NOT NULL,
                producto NVARCHAR(50) NOT NULL,
                cantidad INT NOT NULL,
                FOREIGN KEY(id_venta) REFERENCES ventas(id),
                FOREIGN KEY(producto) REFERENCES productos(codigo)
            );
        END;
        """
        QueriesSQLServer.execute_query(connection, create_ventas_detalle_table)
        
if __name__ == "__main__":
    from datetime import datetime, timedelta
    # Conexión a 'master' para realizar operaciones de creación
    connection = QueriesSQLServer.create_connection(server, database, username, password)

    if connection:
        # Asegurarse de que la conexión no esté dentro de una transacción
        connection.autocommit = True  # Habilitar autocommit para que el CREATE DATABASE no esté dentro de una transacción

        # Verificar si la base de datos existe
        db_name = 'PuntoventaDB'
        check_db_query = f"SELECT name FROM sys.databases WHERE name = '{db_name}'"
        result = QueriesSQLServer.execute_read_query(connection, check_db_query)

        if not result:  # Si no existe, la creamos
            create_db_query = f"CREATE DATABASE {db_name}"
            QueriesSQLServer.execute_query(connection, create_db_query)
            logging.info(f"Base de datos '{db_name}' creada exitosamente.")
        else:
            logging.warning(f"La base de datos '{db_name}' ya existe.")

        # Ahora puedes cerrar la conexión a 'master'
        connection.close()

        # Conectar a la base de datos recién creada (o existente)
        connection = QueriesSQLServer.create_connection(server, db_name, username, password)
        
        # Aquí puedes ejecutar más consultas sobre la base de datos 'PuntoventaDB'
        if connection:
            logging.info(f"Conexión exitosa a la base de datos '{db_name}'")####v5----
            
            #fecha1= datetime.today()-timedelta(days=5)
            #nueva_data=(fecha1, 4)
            #actualizar = """
            #UPDATE
            #  ventas
            #SET
            #  fecha=?
            #WHERE
            #  id = ?
            #"""
#
            #QueriesSQLServer.execute_query(connection, actualizar, nueva_data)
#
            #select_ventas = "SELECT * from ventas"
            #ventas = QueriesSQLServer.execute_read_query(connection, select_ventas)
            #if ventas:
            #    for venta in ventas:
            #        logging("type:", type(venta), "venta:",venta)
#
#
            #select_ventas_detalle = "SELECT * from ventas_detalle"
            #ventas_detalle = QueriesSQLServer.execute_read_query(connection, select_ventas_detalle)
            #if ventas_detalle:
            #    for venta in ventas_detalle:
            #        logging("type:", type(venta), "venta:",venta)
    #