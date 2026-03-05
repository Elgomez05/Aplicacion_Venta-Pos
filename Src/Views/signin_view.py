from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.lang import Builder
from kivy.uix.checkbox import CheckBox
import os
import sys
import logging
from kivy.properties import StringProperty
from cryptography.fernet import Fernet
from Src.Config.config_loader import load_config, config, CURRENT_USER
from Src.Views.security import PasswordManager

os.environ["KIVY_NO_ARGS"] = "1"

# BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# # KV_PATH = os.path.join(BASE_DIR, "signin_view.kv")
# # Builder.load_file(KV_PATH)

# logging.info("Archivo KV cargado correctamente")

from Src.Views.sqlqueries import QueriesSQLServer

server = config.get("database", "server")
database = config.get("database", "database")
username = config.get("database", "username")
password = config.get("database", "password")

userload_path = os.path.join(os.getenv('LOCALAPPDATA', 
                          os.path.join(os.path.expanduser('~'), 'AppData', 'Local')),
                          'PuntoVenta', 'remembereduser.txt')
os.makedirs(os.path.dirname(userload_path), exist_ok=True)


def resource_path(relative_path):
    """Obtiene la ruta correcta para recursos en dev y en el ejecutable"""
    try:
        # PyInstaller crea una carpeta temporal y almacena la ruta en _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    
    return os.path.join(base_path, relative_path)

class SigninWindow(BoxLayout):
    bg_image_path = StringProperty('')

    def __init__(self, usuario_loggin_callback, **kwargs):
        super().__init__(**kwargs)
        self.usuario_loggin=usuario_loggin_callback

        self._cargar_imagen_fondo()  # NUEVO MÉTODO
        self._cargar_usuario_guardado()
    
    def _cargar_imagen_fondo(self):
        """Carga robustamente la imagen de fondo."""
        try:
            # Intentar múltiples rutas posibles
            possible_paths = [
                resource_path(os.path.join('Src', 'Asset', 'Img-venta-Pos1.png')),
                resource_path('Src/Asset/Img-venta-Pos1.png'),
                os.path.join('Src', 'Asset', 'Img-venta-Pos1.png'),
                'Src/Asset/Img-venta-Pos1.png',
                # Rutas absolutas como fallback
                os.path.abspath(os.path.join('Src', 'Asset', 'Img-venta-Pos1.png'))
            ]
            
            for imagen_path in possible_paths:
                logging.info(f"Buscando imagen en: {imagen_path}")
                if os.path.exists(imagen_path):
                    self.bg_image_path = imagen_path
                    logging.info(f" Imagen de fondo cargada correctamente: {self.bg_image_path}")
                    break
            else:
                logging.error(f"Imagen de fondo no encontrada en ninguna ruta: {self.bg_image_path}")
                self.bg_image_path = ''
                
        except Exception as e:
            logging.error(f" Error al cargar imagen de fondo: {e}")
            self.bg_image_path = ''

    def _cargar_usuario_guardado(self):
        try:
            if os.path.exists(userload_path):
                with open(userload_path, "rb") as f:
                    encrypted = f.read()
                    if encrypted:
                        decrypted = self.fernet.decrypt(encrypted).decode()
                        user, pwd = decrypted.split("|")

                        self.ids.username.text = user
                        self.ids.password.text = pwd
                        self.ids.recordar_checkbox.active = True
                        logging.info(f"Usuario cargado correctamente: {user}")
        except Exception as e:
            logging.error(f"Error cargando usuario recordado: {e}")

    def cargar_clave():
        base_dir = os.path.dirname(os.path.abspath(__file__))
        key_path = os.path.join(base_dir, 'key.key')

        if not os.path.exists(key_path):
            logging.error(f"Archivo key no encontrado en: {key_path}")
            return None
        return open(key_path, "rb").read()

    fernet = Fernet(cargar_clave())

    def verificar_usuario(self, username_input, password_input, recordar_usuario):
        username_input = username_input.strip()
        password_input = password_input.strip()

        if recordar_usuario:
            data = f"{username_input}|{password_input}".encode()
            logging.info(f"Guardando usuario de inicios de sesión.")
            encrypted = self.fernet.encrypt(data)

            with open(userload_path, "wb") as f:
                f.write(encrypted)
        else:
            logging.info("No se guardará el usuario.")
            with open(userload_path, "wb") as f:
                f.write(b"") 
        
        if not username_input or not password_input:
            self.ids.signin_notificacion.text = 'Falta nombre de usuario y/o contraseña'
            return

        try:
            connection = QueriesSQLServer.create_connection()
            if connection:
                if connection is None:
                    self.ids.signin_notificacion.text = 'Error al conectar con la base de datos.'
                    logging.error("No se pudo establecer conexión con la base de datos")
                    return

                # logging.info(f"Conexión exitosa a la base de datos: {database}")
                query = "SELECT * FROM usuarios WHERE username = ? AND activo = 1"
                user_result = QueriesSQLServer.execute_read_query(connection, query, (username_input,))

                if user_result is not None:
                    if len(user_result) > 0:  
                        user = user_result[0] 
                        user_data = {
                                'nombre': user[1],
                                'username': user[0],
                                'password': user[2],
                                'tipo': user[3]
                            }
                        if PasswordManager.verify_password(password_input, user_data['password']):
                            CURRENT_USER.clear()
                            CURRENT_USER.update(user_data)

                            self.ids.username.text = ''
                            self.ids.password.text = ''
                            self.ids.signin_notificacion.text = ''
                            if user_data['tipo'] == 'empleado':
                                self.parent.parent.current = 'scrn_ventas'
                            elif user_data['tipo'] == 'administrador':
                                self.parent.parent.current = 'scrn_admin'
                            else:
                                self.parent.parent.current = 'scrn_admin'
                            self.usuario_loggin(user_data)
                            logging.info(f"Ingreso a ventas, Bienvenido {user_data['nombre']}")
                        else:
                            self.ids.signin_notificacion.text = 'Usuario o contraseña incorrecta.'
                            logging.info(f"Contraseña incorrecta para el usuario {username_input}.")
                    else:
                        self.ids.signin_notificacion.text = 'El usuario no existe en la base de datos.'
                        logging.debug(f"Usuario no encontrado: {username_input}")
                else:
                    self.ids.signin_notificacion.text = 'Error al consultar la base de datos.'
                    logging.error("Error en la consulta a la base de datos.")
        except Exception as e:
            logging.error(f"Ocurrió un error en verificar_usuario: {e}")
            self.ids.signin_notificacion.text = 'Error de conexión con la base de datos.'

class SigninApp(App):
    def build(self):
        return SigninWindow()

if __name__ == "__main__":
    SigninApp().run()##########v5
