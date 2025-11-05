import pyodbc

server = 'DESKTOP-QGCQ59D\SQLEXPRESS' 
database = 'master'  
username = 'Elgomez05'
password = '123456'


class QueriesSQLServer:
    @staticmethod
    def create_connection(server, database, username, password):
        connection = None
        try:
            connection = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};'
                f'SERVER={server};'
                f'DATABASE={database};'
                f'UID={username};'
                f'PWD={password}'
            )
            print("Connection to SQL Server DB successful")
        except Exception as e:
            print(f"The error '{e}' occurred")
        return connection

    @staticmethod
    def execute_query(connection, query, data_tuple=()):
        cursor = connection.cursor()
        try:
            cursor.execute(query, data_tuple)
            connection.commit()
    
            # Obtener el último ID generado si es un INSERT
            if query.strip().lower().startswith("insert"):
                cursor.execute("SELECT @@IDENTITY")  # Usar @@IDENTITY como alternativa
                last_id = cursor.fetchone()[0]
                if last_id is None:
                    raise Exception("@@IDENTITY devolvió NULL. Verifica la inserción.")
                return last_id
            return None
        except Exception as e:
            print(f"Error al ejecutar la consulta: {e}")
            return None


    @staticmethod
    def execute_read_query(connection, query, data_tuple=()):
        cursor = connection.cursor()
        result = None
        try:
            cursor.execute(query, data_tuple)  
            result = cursor.fetchall()
            return result
        except Exception as e:
            print(f"Error al ejecutar la consulta: {e}")
            return None

    @staticmethod
    def create_tables():
        connection = QueriesSQLServer.create_connection(server, 'PuntoventaDB', username, password)

        if not connection:
            print("Error: No se pudo establecer conexión para crear las tablas.")
            return

        # Crear tabla productos
        create_productos_table = """
        IF NOT EXISTS (SELECT * FROM sysobjects WHERE name = 'productos' AND xtype = 'U')
        BEGIN
            CREATE TABLE productos (
                codigo NVARCHAR(50) PRIMARY KEY, 
                nombre NVARCHAR(255) NOT NULL, 
                precio DECIMAL(18, 2) NOT NULL, 
                cantidad INT NOT NULL
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
                tipo NVARCHAR(50) NOT NULL
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
                FOREIGN KEY(username) REFERENCES usuarios(username)
            );
        END;
        """
        QueriesSQLServer.execute_query(connection, create_ventas_table)

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
            print(f"Base de datos '{db_name}' creada exitosamente.")
        else:
            print(f"La base de datos '{db_name}' ya existe.")

        # Ahora puedes cerrar la conexión a 'master'
        connection.close()

        # Conectar a la base de datos recién creada (o existente)
        connection = QueriesSQLServer.create_connection(server, db_name, username, password)
        
        # Aquí puedes ejecutar más consultas sobre la base de datos 'PuntoventaDB'
        if connection:
            print(f"Conexión exitosa a la base de datos '{db_name}'")
            
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
            #        print("type:", type(venta), "venta:",venta)
#
#
            #select_ventas_detalle = "SELECT * from ventas_detalle"
            #ventas_detalle = QueriesSQLServer.execute_read_query(connection, select_ventas_detalle)
            #if ventas_detalle:
            #    for venta in ventas_detalle:
            #        print("type:", type(venta), "venta:",venta)
    #