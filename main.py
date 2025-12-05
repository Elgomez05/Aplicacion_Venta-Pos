from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
import os
import sys
import json
import logging
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler

from Src.Views.sqlqueries import QueriesSQLServer
from Src.Views.signin_view import SigninWindow
from Src.Views.ventas_view import VentasWindow
from Src.Views.admin_view import AdminWindow

os.environ["KIVY_NO_ARGS"] = "1"

server = 'DESKTOP-QGCQ59D\\SQLEXPRESS'
database = 'PuntoventaDB'
username = 'Elgomez05'
password = '123456'


class MainWindow(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.admin_widget=AdminWindow()
        self.ventas_widget=VentasWindow(self.admin_widget.actualizar_inventario)
        self.signin_widget=SigninWindow(self.ventas_widget.usuario_loggin)
        self.ids.scrn_signin.add_widget(self.signin_widget)
        self.ids.scrn_ventas.add_widget(self.ventas_widget)
        self.ids.scrn_admin.add_widget(self.admin_widget)
        
    #def usuario_loggin(self, user_data):
    #    # Aquí debe ir el código de login
    #    logging.info(f"Usuario logueado en MainWindow: {user_data}")
    #    self.ventas_widget.usuario_loggin(user_data)  # Llamar el usuario_loggin en VentasWindow


class PuntoVenta(App):
    next_terminal_id = 1
    
    def build(self):
        if not hasattr(QueriesSQLServer, "initialized"):
            connection = QueriesSQLServer.create_connection(server, database, username, password)
            if connection:
                QueriesSQLServer.create_tables()
            QueriesSQLServer.initialized = True

        if "--subterminal" not in sys.argv:
            logging.info("Iniciando aplicación principal POS...")
            return MainWindow()

        logging.info("Iniciando subterminal independiente...")
        terminal_id = 1
        user_data = {"nombre": "Usuario", "tipo": "empleado"}

        try:
            idx = sys.argv.index("--subterminal") + 1
            data = json.loads(sys.argv[idx])
            terminal_id = data.get("terminal_id", 1)
            user_data = data.get("user", user_data)

            self.next_terminal_id = max(self.next_terminal_id, terminal_id)
        except Exception as e:
            logging.error(f"Error leyendo argumentos: {e}")

        ventas = VentasWindow(
            actualizar_inventario_callback=self._actualizar_sub_inventario,
            terminal_id=terminal_id,
            user_data=user_data
        )
        ventas.usuario_loggin(user_data)
        return ventas

    def _actualizar_sub_inventario(self, datos):
        # Reusar actualización desde Admin
        try:
            win = self.root.admin_widget
            win.actualizar_inventario(datos)
        except:
            logging.info("Actualización inventario subterminal ejecutada")


if __name__ == "__main__":
    
    # # ===================================== # #
    # #  CONFIGURACIÓN DE LOGS
    # # ===================================== # #

    LOG_DIR = r"C:\ProgramData\PEPE"
    os.makedirs(LOG_DIR, exist_ok=True)

    file_handler = TimedRotatingFileHandler(f"{LOG_DIR}/App_logs.log", when="midnight", 
                interval=1, backupCount=30, encoding="utf-8")
                
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(module)s:%(lineno)d | %(message)s",
            "%d-%m-%Y %H:%M:%S %p"
        )
    )
    logging.getLogger().addHandler(file_handler)

    # logging.info("Guardando logs correctamente")

    PuntoVenta().run()#######v2
    