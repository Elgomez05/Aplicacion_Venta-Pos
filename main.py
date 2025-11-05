from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
import logging
from logging.handlers import TimedRotatingFileHandler
import os

from Src.Views.sqlqueries import QueriesSQLServer
from Src.Views.signin_view import SigninWindow
from Src.Views.ventas_view import VentasWindow
from Src.Views.admin_view import AdminWindow
    
server = 'DESKTOP-QGCQ59D\\SQLEXPRESS'
database = 'PuntoventaDB'
username = 'Elgomez05'
password = '123456'


class MainWindow(BoxLayout):
    connection = QueriesSQLServer.create_connection(server, database, username, password)
    if connection:
        # Crear tablas sin no existen
        QueriesSQLServer.create_tables()
    def __init__(self, **kwargs):
        super().__init__(*kwargs)
        self.admin_widget=AdminWindow()
        self.ventas_widget=VentasWindow(self.admin_widget.actualizar_inventario)
        self.signin_widget=SigninWindow(self.ventas_widget.usuario_loggin)
        self.ids.scrn_signin.add_widget(self.signin_widget)
        self.ids.scrn_ventas.add_widget(self.ventas_widget)
        self.ids.scrn_admin.add_widget(self.admin_widget)
        
    #def usuario_loggin(self, user_data):
    #    # Aquí debe ir el código de login
    #    print(f"Usuario logueado en MainWindow: {user_data}")
    #    self.ventas_widget.usuario_loggin(user_data)  # Llamar el usuario_loggin en VentasWindow

        
        


class MainApp(App):
    def build(self):
        return MainWindow()

if __name__ == "__main__":
    logging.basicConfig(
        level       = logging.DEBUG,
        format      = "%(asctime)s [%(levelname)s]    %(module)s:%(lineno)d    %(funcName)s    | %(message)s" ,
        datefmt     = '%Y-%m-%d %H:%M:%S',
        handlers    = [
            # TimedRotatingFileHandler(f"{logsFolder}/logs_reports.log", when    = "midnight", interval    = 1, backupCount    = 30),
            logging.StreamHandler()
        ]
    )
    MainApp().run()
    