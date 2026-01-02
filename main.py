from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
import os
import sys
import json
import logging
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler
from kivy.uix.popup import Popup
from kivy.uix.label import Label
from kivy.clock import Clock
from kivy.uix.button import Button
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label

from Src.Views.sqlqueries import QueriesSQLServer
from Src.Views.signin_view import SigninWindow
from Src.Views.ventas_view import VentasWindow
from Src.Views.admin_view import AdminWindow
from Src.Config.config_loader import config, CURRENT_USER
from Src.Views.Settings import Herramientas

from kivy.core.window import Window

os.environ["KIVY_NO_ARGS"] = "1"

class MainWindow(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.admin_widget=AdminWindow()
        self.ventas_widget=VentasWindow(self.admin_widget.actualizar_inventario)
        self.signin_widget = SigninWindow(self.on_login_success)
        # self.signin_widget=SigninWindow(self.ventas_widget.usuario_loggin)
        self.ids.scrn_signin.add_widget(self.signin_widget)
        self.ids.scrn_ventas.add_widget(self.ventas_widget)
        self.ids.scrn_admin.add_widget(self.admin_widget)

        
    #def usuario_loggin(self, user_data):
    #    # Aquí debe ir el código de login
    #    logging.info(f"Usuario logueado en MainWindow: {user_data}")
    #    self.ventas_widget.usuario_loggin(user_data)  # Llamar el usuario_loggin en VentasWindow

    def on_login_success(self, user_data):
        """
        Callback único post-login
        """
        logging.info(f"Login exitoso: {user_data}")

        # Inyectar usuario en ventas
        self.ventas_widget.usuario_loggin(user_data)
        self.ids.screen_manager_main.current = "scrn_ventas"
        Clock.schedule_once(lambda dt: TurnoPopup().open(), 0.3)


class PuntoVenta(App):
    next_terminal_id = 1
    
    def build(self):
        if not hasattr(QueriesSQLServer, "initialized"):
            db_config = config.get("database")
            connection = QueriesSQLServer.create_connection(
                db_config["server"],
                db_config["database"],
                db_config["username"],
                db_config["password"]
            )
            if connection:
                QueriesSQLServer.create_tables()
                QueriesSQLServer.alter_productos_add_fields()
                QueriesSQLServer.alter_usuarios_add_fields()

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

            CURRENT_USER.clear()
            CURRENT_USER.update(user_data)

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

    def _dispatch_scanner_code(self, codigo):
        app = App.get_running_app()
        root = app.root

        # Ventas
        if hasattr(root, "ventas_widget"):
            root.ventas_widget.agregar_producto_codigo(codigo)

        # # Admin
        # if hasattr(root, "admin_widget"):
        #     root.admin_widget.agregar_producto(codigo)

class TurnoPopup(Popup):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.title = "Verificación de Turno"
        self.size_hint = (None, None)
        self.size = (400, 300)

        # BoxLayout para contenido del Popup
        self.layout = BoxLayout(orientation="vertical")
        self.message_label = Label(text="Verificando el estado del turno...", size_hint=(1, 0.8))
        self.layout.add_widget(self.message_label)

        self.close_button = Button(text="Cerrar", size_hint=(1, 0.2))
        self.close_button.bind(on_release=self.dismiss)
        self.layout.add_widget(self.close_button)

        self.add_widget(self.layout)

        # Iniciar verificación
        Clock.schedule_once(self.verificar_turno, 0)

    def verificar_turno(self, dt):
        # Ruta de control del turno
        path = "C:/ProgramData/PuntoVenta/shiftControl/controlShift.json"

        if os.path.exists(path):
            with open(path, 'r') as f:
                turno_data = json.load(f)
                if turno_data.get("Status") == "ABIERTO":
                    self.message_label.text = "Turno Abierto. Puedes seguir facturando."
                else:
                    self.message_label.text = "Turno cerrado. Abriendo turno..."
                    self.abrir_turno()  # Si el turno está cerrado, lo abrimos.
        else:
            self.message_label.text = "No se encontró archivo de turno. Abriendo turno..."
            self.abrir_turno()

    def abrir_turno(self):
        path = "C:/ProgramData/PuntoVenta/shiftControl/controlShift.json"
        turno_data = {
            "Status": "ABIERTO",
            "Id_Shift": 1,
            "cashInitial": 0,
            "cashFinal": 0,
            "user": "POS",
            "Id_Device": 1
        }
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(turno_data, f, indent=4)
        logging.info("Turno abierto correctamente.")
        self.message_label.text = "Turno abierto con éxito. Puede continuar facturando."


if __name__ == "__main__":
    
    # # ===================================== # #
    # #  CONFIGURACIÓN DE LOGS
    # # ===================================== # #

    LOG_DIR = r"C:\ProgramData\PuntoVenta\Logs"
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

    PuntoVenta().run()#######v14
    