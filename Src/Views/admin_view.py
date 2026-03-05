from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.screenmanager import Screen
from kivy.uix.recycleview.layout import LayoutSelectionBehavior
from kivy.uix.recycleview.views import RecycleDataViewBehavior
from kivy.properties import BooleanProperty
from kivy.uix.recycleboxlayout import RecycleBoxLayout
from kivy.uix.behaviors import FocusBehavior
from kivy.uix.recycleview import RecycleView
from kivy.uix.popup import Popup
from kivy.uix.label import Label
from kivy.uix.dropdown import DropDown
from kivy.clock import Clock
from kivy.lang import Builder
from datetime import datetime, timedelta
import csv
from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
import os
from decimal import Decimal
from kivy.properties import ObjectProperty
from kivy.uix.button import Button
import json

from Src.Views.sqlqueries import QueriesSQLServer
import logging
from Src.Config.config_loader import load_config, config
from Src.Views.Settings import Herramientas, Config
from Src.Views.security import PasswordManager

# Añade al inicio de admin.py después de las importaciones
class SystemStatusPopup(Popup):
    """Popup para confirmar cambio de estado del sistema"""
    def __init__(self, activar_callback, desactivar_callback, estado_actual, **kwargs):
        super(SystemStatusPopup, self).__init__(**kwargs)
        self.activar_callback = activar_callback
        self.desactivar_callback = desactivar_callback
        self.estado_actual = estado_actual
        
        if self.estado_actual:
            self.ids.status_message.text = "El sistema está RESTAURADO.\n¿Deseas BLOQUEARLO completamente?"
            self.ids.confirm_button.text = "BLOQUEAR SISTEMA"
            self.ids.confirm_button.background_color = (0.9, 0.2, 0.2, 1)  # Rojo
        else:
            self.ids.status_message.text = "El sistema está BLOQUEADO.\n¿Deseas RESTAURALO completamente?"
            self.ids.confirm_button.text = "RESTAURAR SISTEMA"
            self.ids.confirm_button.background_color = (0.2, 0.7, 0.2, 1)  # Verde
    
    def confirmar(self):
        if self.estado_actual:
            if self.desactivar_callback:
                self.desactivar_callback()
        else:
            if self.activar_callback:
                self.activar_callback()
        self.dismiss()


class SystemManager:
    """Gestor centralizado del estado del sistema"""
    _instance = None
    Status_path = os.path.join(os.getenv('LOCALAPPDATA', 
        os.path.join(os.path.expanduser('~'), 'AppData', 'Local')),
        'PuntoVenta', 'Config.json')
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SystemManager, cls).__new__(cls)
            cls._instance._sistema_activo = False
            os.makedirs(os.path.dirname(cls.Status_path), exist_ok=True)
            cls._instance.cargar_estado()
        return cls._instance
    
    def cargar_estado(self):
        """Carga el estado del sistema desde archivo"""
        try:
            if os.path.exists(self.Status_path):
                with open(self.Status_path, 'r') as f:
                    data = json.load(f)
                    self._sistema_activo = data.get('activo', False)
            else:
                # Si no existe, crear con estado activo
                self.guardar_estado(False)
        except Exception as e:
            logging.error(f"Error cargando estado del sistema: {e}")
            self._sistema_activo = False
    
    def guardar_estado(self, estado):
        """Guarda el estado del sistema en archivo"""
        try:
            self._sistema_activo = estado
            with open(self.Status_path, 'w') as f:
                json.dump({'activo': estado, 'ultimo_cambio': datetime.now().isoformat()}, f,indent=2)
            logging.info(f"Estado del sistema guardado: {'RESTAURADO' if estado else 'BLOQUEADO'}")
        except Exception as e:
            logging.error(f"Error guardando estado del sistema: {e}")
    
    def esta_activo(self):
        """Verifica si el sistema está activo"""
        return self._sistema_activo
    
    def activar_sistema(self):
        """Activa completamente el sistema"""
        self.guardar_estado(True)
        self._notificar_cambio(True)
    
    def desactivar_sistema(self):
        """Desactiva completamente el sistema"""
        self.guardar_estado(False)
        self._notificar_cambio(False)
    
    def _notificar_cambio(self, nuevo_estado):
        """Notifica a todas las ventanas el cambio de estado"""
        estado = "RESTAURADO" if nuevo_estado else "BLOQUEADO"
        logging.info(f"Sistema {estado} completamente")
        
        # Puedes agregar aquí notificaciones a otros módulos si es necesario

        ###***************************************************************###
        ###*******      INICIO DE SISTEMA DE FACTURACION ###       *******###
        ###***************************************************************###

os.environ["KIVY_NO_ARGS"] = "1"

def format_currency(value):
    """Formatea valores monetarios para COP (Colombia)"""
    try:
        if isinstance(value, str):
            value = float(value)
        
        # (sin decimales para COP)
        value_int = int(round(value))
        value_str = str(value_int)
        parts = []
        while value_str:
            parts.append(value_str[-3:])
            value_str = value_str[:-3]
    
        # Unir con puntos y revertir el orden
        formatted = ".".join(reversed(parts))
        
        return f"${formatted}"
    except Exception as e:
        logging.error(f"Error formateando valor {value}: {e}")
        return "$0"

log = logging.getLogger(__name__)

server = config.get("database", "server")
database = config.get("database", "database")
username = config.get("database", "username")
password = config.get("database", "password")


# BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# # KV_PATH = os.path.join(BASE_DIR, "admin_view.kv")
# # Builder.load_file(KV_PATH)

# # Builder.load_file('Src/Views/admin_view.kv')


class SelectableRecycleBoxLayout(FocusBehavior, LayoutSelectionBehavior, RecycleBoxLayout):
    touch_deselect_last = BooleanProperty(True)


class SelectableProductoLabel(RecycleDataViewBehavior, BoxLayout):
    index = None
    selected = BooleanProperty(False)
    selectable = BooleanProperty(True)

    def refresh_view_attrs(self, rv, index, data):
        self.index = index
        self.ids['_hashtag'].text = str(1 + index)
        self.ids['_codigo'].text = data['codigo']
        self.ids['_articulo'].text = data['nombre'].capitalize()
        self.ids['_cantidad'].text = str(data['cantidad'])
        self.ids['_precio_compra'].text = format_currency(data.get('precio_compra', 0)) 
        self.ids['_precio'].text = format_currency(data['precio'])
        self.ids['_catalogo'].text = data.get('catalogo', '')  
        return super(SelectableProductoLabel, self).refresh_view_attrs(rv, index, data)

    def on_touch_down(self, touch):
        if super(SelectableProductoLabel, self).on_touch_down(touch):
            return True
        if self.collide_point(*touch.pos) and self.selectable:
            return self.parent.select_with_touch(self.index, touch)

    def apply_selection(self, rv, index, is_selected):
        self.selected = is_selected
        if is_selected:
            rv.data[index]['seleccionado'] = True
        else:
            rv.data[index]['seleccionado'] = False


class SelectableUsuarioLabel(RecycleDataViewBehavior, BoxLayout):
    index = None
    selected = BooleanProperty(False)
    selectable = BooleanProperty(True)

    def refresh_view_attrs(self, rv, index, data):
        self.index = index
        self.ids['_hashtag'].text = str(1 + index)
        self.ids['_nombre'].text = data['nombre'].title()
        self.ids['_username'].text = data['username']
        self.ids['_tipo'].text = str(data['tipo'])
        return super(SelectableUsuarioLabel, self).refresh_view_attrs(rv, index, data)

    def on_touch_down(self, touch):
        if super(SelectableUsuarioLabel, self).on_touch_down(touch):
            return True
        if self.collide_point(*touch.pos) and self.selectable:
            return self.parent.select_with_touch(self.index, touch)

    def apply_selection(self, rv, index, is_selected):
        self.selected = is_selected
        if is_selected:
            rv.data[index]['seleccionado'] = True
        else:
            rv.data[index]['seleccionado'] = False


class ItemVentaLabel(RecycleDataViewBehavior, BoxLayout):
	index = None

	def refresh_view_attrs(self, rv, index, data):
		self.index = index
		self.ids['_hashtag'].text = str(1+index)
		self.ids['_codigo'].text = data['codigo']
		self.ids['_articulo'].text = data['producto'].capitalize()
		self.ids['_cantidad'].text = str(data['cantidad'])
		self.ids['_precio_por_articulo'].text = format_currency(data['precio'])
		self.ids['_total'].text= format_currency(data['total'])
		return super(ItemVentaLabel, self).refresh_view_attrs(
            rv, index, data)



class SelectableVentaLabel(RecycleDataViewBehavior, BoxLayout):
	index = None
	selected = BooleanProperty(False)
	selectable = BooleanProperty(True)

	def refresh_view_attrs(self, rv, index, data):
		self.index = index
		self.ids['_hashtag'].text = str(1+index)
		self.ids['_username'].text = data['username']
		self.ids['_cantidad'].text = str(data['productos'])
		self.ids['_total'].text= format_currency(data['total'])
		self.ids['_time'].text = str(data['fecha'].strftime("%H:%M:%S"))
		self.ids['_date'].text = str(data['fecha'].strftime("%d/%m/%Y"))
		return super(SelectableVentaLabel, self).refresh_view_attrs(
            rv, index, data)

	def on_touch_down(self, touch):
		if super(SelectableVentaLabel, self).on_touch_down(touch):
			return True
		if self.collide_point(*touch.pos) and self.selectable:
			return self.parent.select_with_touch(self.index, touch)

	def apply_selection(self, rv, index, is_selected):
		self.selected = is_selected
		if is_selected:
			# Deseleccionar todas las demás ventas antes de seleccionar esta
			for i in range(len(rv.data)):
				if i != index:
					rv.data[i]['seleccionado'] = False
			rv.data[index]['seleccionado']=True
		else:
			rv.data[index]['seleccionado']=False

class AdminRV(RecycleView):
    def __init__(self, **kwargs):
        super(AdminRV, self).__init__(**kwargs)
        self.data = []

    def agregar_datos(self, datos):
        # Limpiar datos anteriores antes de agregar nuevos
        self.data = []
        for dato in datos:
            dato['seleccionado'] = False
            self.data.append(dato)
        self.refresh_from_data()

    def dato_seleccionado(self):
        indice = -1
        # Buscar la primera selección y asegurar que solo haya una
        for i in range(len(self.data)):
            if self.data[i].get('seleccionado', False):
                if indice == -1:
                    indice = i
                else:
                    # Si hay múltiples seleccionadas, deseleccionar las demás
                    self.data[i]['seleccionado'] = False
        return indice
    
    def limpiar_datos(self):
        self.data = [] 

class ProductoPopup(Popup):
    def __init__(self, agregar_callback, **kwargs):
        super(ProductoPopup, self).__init__(**kwargs)
        self.agregar_callback=agregar_callback
        
    def abrir(self, agregar, producto=None):
        if agregar:
            self.ids.producto_info_1.text='Agregar producto nuevo'
            self.ids.producto_codigo.disabled=False
        else:
            self.ids.producto_info_1.text='Modificar producto'
            self.ids.producto_codigo.text=producto['codigo']
            self.ids.producto_codigo.disabled=True
            self.ids.producto_nombre.text=producto['nombre']
            self.ids.producto_cantidad.text=str(producto['cantidad'])
            self.ids.producto_precio.text=str(producto['precio'])
            self.ids.spinner_catalogo.text = producto.get('catalogo', '')
            self.ids.precio_compra.text = str(producto.get('precio_compra', 0))
            
        self.open()
    
    def verificar(self, producto_codigo, producto_nombre, producto_cantidad, producto_precio, catalogo, precio_compra ):
        alert1='Falta: '
        alert2=''
        validado={}
        if not producto_codigo:
            alert1+='Codigo. '
            validado['codigo']=False
        else:
            try:
                numeric=int(producto_codigo)
                validado['codigo']=producto_codigo
            except:
                alert2+='Codigo no valido. '
                validado['codigo']=False
                
        if not producto_nombre:
            alert1+='Nombre. '
            validado['nombre']=False
        else:
            validado['nombre']=producto_nombre.lower()
            
        if not producto_cantidad:
            alert1+='Cantidad. '
            validado['cantidad']= False
        else:
            try:
                numeric=int(producto_cantidad)
                validado['cantidad']=producto_cantidad
            except:
                alert2+='cantidad no valida. '
                validado['cantidad']=False
                
        if not producto_precio:
            alert1+='Precio. '
            validado['precio']= False
        else:
            try:
                numeric=float(producto_precio)
                validado['precio']=producto_precio
            except:
                alert2+='precio no valido. '
                validado['precio']=False

        validado['catalogo'] = self.ids.spinner_catalogo.text if hasattr(self.ids, 'spinner_catalogo') else 'GENERAL'
        
        precio_compra_val = 0.0
        if hasattr(self.ids, 'precio_compra') and self.ids.precio_compra.text:
            try:
                precio_compra_val = float(self.ids.precio_compra.text)
            except:
                alert2+='precio compra no valido. '
                validado['precio_compra'] = False
        else:
            precio_compra_val = 0.0
        
        validado['precio_compra'] = precio_compra_val

        if any(value is False for value in validado.values()):
            self.ids.no_valido_notif.text = alert1 + alert2
        else:
            self.ids.no_valido_notif.text = 'Producto validado correctamente'
            validado['cantidad']=int(validado['cantidad'])
            validado['precio']=float(validado['precio'])
            self.agregar_callback(True, validado)
            self.dismiss()
        
        
    
class VistaProductos(Screen):
    def __init__(self,  **kwargs):
        super().__init__(**kwargs)
        Clock.schedule_once(self.cargar_productos, 1)
        Clock.schedule_once(self.cargar_catalogos, 2) 
        
    def mostrar_notificacion_popup(self, mensaje):
        popup = Popup(
            title="Notificación",
            content=Label(text=mensaje),
            size_hint=(0.6, 0.4), 
            auto_dismiss=True
        )
        popup.open()
        # Cerrar automáticamente después de 2 segundos
        Clock.schedule_once(lambda dt: popup.dismiss(), 2)

    def cargar_catalogos(self, *args):
        """Carga los catálogos únicos de la base de datos"""
        connection = QueriesSQLServer.create_connection()
        
        # Consulta para obtener catálogos únicos
        catalogos_query = "SELECT DISTINCT catalogo FROM productos WHERE ISNULL(activo, 1) = 1 AND catalogo IS NOT NULL AND catalogo != ''"
        catalogos_sql = QueriesSQLServer.execute_read_query(connection, catalogos_query)
        
        catalogos_list = ["TODOS"]  # Opción por defecto
        
        if catalogos_sql:
            for catalogo in catalogos_sql:
                if catalogo[0]:  # Solo agregar si no es None o vacío
                    catalogos_list.append(catalogo[0])
        
        # Actualizar el spinner con los catálogos
        if hasattr(self.ids, 'spinner_catalogo_filtro'):
            self.ids.spinner_catalogo_filtro.values = catalogos_list
            self.ids.spinner_catalogo_filtro.text = "TODOS"

    def cargar_productos(self, *args, catalogo=None):
        _productos = []
        connection = QueriesSQLServer.create_connection()
        if catalogo and catalogo != "TODOS":
            # Filtrar por catálogo específico
            inventario_sql = QueriesSQLServer.execute_read_query(
                connection, 
                "SELECT * FROM productos WHERE ISNULL(activo, 1) = 1 AND catalogo = ?",
                (catalogo,)
            )
        else:
            inventario_sql = QueriesSQLServer.execute_read_query(connection, "SELECT * FROM productos WHERE ISNULL(activo, 1) = 1")

        if inventario_sql:
            for producto in inventario_sql:
                _productos.append({'codigo': producto[0], 'nombre': producto[1], 'precio': producto[2], 'cantidad': producto[3], 'catalogo': producto[4], 'precio_compra': producto[5]})

        self.ids.rv_productos.agregar_datos(_productos)
        self._productos_originales = _productos.copy()

    def filtrar_productos(self, texto):
        texto = texto.strip().lower()

        if not texto:
            self.ids.rv_productos.agregar_datos(self._productos_originales)
            return

        filtrados = [
            p for p in self._productos_originales
            if texto in p['nombre'].lower() or texto in str(p['codigo'])
        ]

        self.ids.rv_productos.agregar_datos(filtrados)

        
    def filtrar_por_catalogo(self, catalogo):
        """Filtra los productos por el catálogo seleccionado"""
        logging.info(f"Filtrando por catálogo: {catalogo}")
        self.cargar_productos(catalogo=catalogo)

    def agregar_producto(self, agregar=False, validado=None):
        if agregar:
            connection = QueriesSQLServer.create_connection()

            # Verificar si el producto ya existe
            cursor = connection.cursor()
            verificar_producto = "SELECT COUNT(*) FROM productos WHERE codigo = ?;"
            cursor.execute(verificar_producto, (validado['codigo'],))
            resultado = cursor.fetchall()

            if resultado[0][0] > 0:  # Si el producto ya existe
                popup = ProductoPopup(self.agregar_producto)
                popup.ids.no_valido_notif.text = f"El producto con código {validado['codigo']} ya existe."
                popup.open()
            else:
                # Si no existe, agregar el producto
                producto_tuple = (validado['codigo'], validado['nombre'], validado['precio'], validado['cantidad'], validado.get('catalogo', 'GENERAL'), validado.get('precio_compra', 0.0))
                crear_producto = """
                INSERT INTO
                    productos (codigo, nombre, precio, cantidad, catalogo, precio_compra)
                VALUES
                    (?, ?, ?, ?, ?, ?);
                """
                QueriesSQLServer.execute_query(connection, crear_producto, producto_tuple)
                producto_formateado = (
                    producto_tuple[0], 
                    producto_tuple[1], 
                    format_currency(producto_tuple[2]),  # Precio formateado
                    producto_tuple[3], 
                    producto_tuple[4], 
                    format_currency(producto_tuple[5])   # Precio compra formateado
                )
                logging.info(f"Producto agregado correctamente.: {producto_formateado}")
                self.ids.rv_productos.data.append(validado)
                self.ids.rv_productos.refresh_from_data()
                self.cargar_catalogos()
                
                self.mostrar_notificacion_popup(f"Producto '{validado['nombre']}' agregado correctamente.")
        else:
            popup = ProductoPopup(self.agregar_producto)
            popup.abrir(True)


    def modificar_producto(self, modificar=False, validado=None):
        indice=self.ids.rv_productos.dato_seleccionado()
        if modificar:
            connection = QueriesSQLServer.create_connection()
            producto_tuple = (validado['nombre'], validado['precio'], validado['cantidad'], validado.get('catalogo', 'GENERAL'), validado.get('precio_compra', 0.0), validado['codigo'])
            actualizar_producto = """
            UPDATE
                productos 
            SET
                nombre = ?, precio = ?, cantidad = ?,  catalogo = ?, precio_compra = ?
            WHERE
                codigo = ?;
                
            """
            QueriesSQLServer.execute_query(connection, actualizar_producto, producto_tuple)
            logging.info(f"Producto modificado correctamente.:, {producto_tuple}")
            self.ids.rv_productos.data[indice]['nombre']=validado['nombre']
            self.ids.rv_productos.data[indice]['cantidad']=validado['cantidad']
            self.ids.rv_productos.data[indice]['precio']=validado['precio']
            self.ids.rv_productos.data[indice]['catalogo']=validado.get('catalogo', '')
            self.ids.rv_productos.data[indice]['precio_compra']=validado.get('precio_compra', 0.0)
            self.ids.rv_productos.refresh_from_data()
            self.cargar_catalogos()

            self.mostrar_notificacion_popup(f"Producto '{validado['nombre']}' modificado correctamente.")
        else:
            if indice>=0:
                Producto=self.ids.rv_productos.data[indice]
                popup = ProductoPopup(self.modificar_producto)
                popup.abrir(False, Producto)

    def eliminar_producto(self):
        if hasattr(self, 'ids') and 'rv_productos' in self.ids:
            rv = self.ids.rv_productos
            indice = rv.dato_seleccionado()
            if indice >= 0:
                producto_tuple = (rv.data[indice]['codigo'],)
                connection = QueriesSQLServer.create_connection()
                desactivar_producto = """
                    UPDATE productos
                    SET activo = 0
                    WHERE codigo = ?
                    """
                try:
                    QueriesSQLServer.execute_query(connection, desactivar_producto, producto_tuple)
                except Exception as e:
                    # Si está relacionado con FK
                    if "REFERENCE constraint" in str(e) or "547" in str(e):
                        self.mostrar_notificacion_popup(
                            "Producto desactivado correctamente.\n"
                            "Tiene ventas asociadas.",
                        )
                        logging.warning(
                            f"No se puede eliminar producto {producto_tuple[0]}: tiene ventas" ######
                        )
                        return
                    else:
                        raise

                # SOLO si SQL sí borró
                logging.info(f"Producto eliminado correctamente.: {producto_tuple}")
                rv.data.pop(indice)
                rv.refresh_from_data()
                self.mostrar_notificacion_popup(
                    f"Producto '{producto_tuple[0]}' eliminado correctamente."
        )
         
               
    def actualizar_productos(self, productos_actualizados):
        for producto_nuevo in productos_actualizados:
            for productos_antes in self.ids.rv_productos.data:
                if producto_nuevo['codigo']==productos_antes['codigo']:
                    productos_antes['cantidad']=producto_nuevo['cantidad']
                    break
        self.ids.rv_productos.refresh_from_data()

    def _tecla_presionada_admin(self, window, key, scancode, codepoint, modifiers):
        """Maneja scanner en ventana de admin"""
        if codepoint and codepoint.isalnum():
            # Aquí puedes implementar lógica similar para buscar productos en admin
            # Por ejemplo, seleccionar automáticamente un producto por código
            pass

            
class UsuarioPopup(Popup):
    def __init__(self, agregar_callback, **kwargs):
        super(UsuarioPopup, self).__init__(**kwargs)
        self.agregar_usuario=agregar_callback
        
    def abrir(self, agregar, usuario=None):
        if agregar:
            self.ids.usuario_info_2.text='Agregar usuario nuevo'
            self.ids.usuario_username.disabled=False
        else:
            self.ids.usuario_info_2.text='Modificar usuario'
            self.ids.usuario_username.text=usuario['username']
            self.ids.usuario_username.disabled=True
            self.ids.usuario_nombre.text=usuario['nombre']
            self.ids.usuario_password=usuario['password']

            if usuario['tipo']=='admin':
                self.ids.admin_tipo.state='down'
            else:
                self.ids.empleado_tipo.state='down'
        self.open()
    
    def verificar(self, usuario_username, usuario_nombre, usuario_password, admin_tipo, empleado_tipo):
        alert1='Falta: '
        alert2=''
        validado={}
        if not usuario_username:
            alert1+='Nombre de usuario. '
            validado['username']=False
        else:
            try:
                validado['username']=usuario_username
            except:
                alert2+='Usuario no valido. '
                validado['username']=False
                
        if not usuario_nombre:
            alert1+='Nombre. '
            validado['nombre']=False
        else:
            validado['nombre']=usuario_nombre.lower()

        if not usuario_password:
            alert1+='Contraseña. '
            validado['password']= False
        else:
            validado['password']=PasswordManager.hash_password(usuario_password)
            
        if admin_tipo=='normal' and empleado_tipo=='normal':
            alert1+='Tipo. '
            validado['tipo']= False
        else:
            if admin_tipo=='down':
                validado['tipo']='admin'
            else:
                validado['tipo']='empleado'
                
        if any(value is False for value in validado.values()):
            self.ids.no_valido_notif_2.text = alert1 + alert2
        else:
            self.ids.no_valido_notif_2.text = 'Usuario validado correctamente'
            self.agregar_usuario(True, validado)
            self.dismiss()

class AdminLoginPopup(Popup):
    def __init__(self, login_callback, **kwargs):
        super(AdminLoginPopup, self).__init__(**kwargs)
        self.login_callback = login_callback
        
    def verificar_admin(self, username, password):
        if not username or not password:
            self.ids.admin_login_notif.text = 'Ingrese usuario y contraseña'
            return
            
        connection = QueriesSQLServer.create_connection()
        if not connection:
            self.ids.admin_login_notif.text = 'Error de conexión'
            return
            
        query = "SELECT * FROM usuarios WHERE username = ? AND tipo = 'administrador' AND ISNULL(activo, 1) = 1"
        result = QueriesSQLServer.execute_read_query(connection, query, (username,))
        
        if result and len(result) > 0:
            user = result[0]
            stored_password = user[2]
            
            if PasswordManager.verify_password(password, stored_password):
                self.ids.admin_login_notif.text = 'Acceso concedido'
                self.login_callback(True)
                self.dismiss()
            else:
                self.ids.admin_login_notif.text = 'Credenciales incorrectas'
        else:
            self.ids.admin_login_notif.text = 'Usuario no autorizado'

class VistaAdmin(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.admin_authenticated = False
        self.system_manager = SystemManager()
        self._popup_configuracion = None  # ← Añadir esta línea
        
    def mostrar_login_admin(self):
        """Muestra popup de login para administrador"""
        if not self.admin_authenticated:
            popup = AdminLoginPopup(self.on_admin_login)
            popup.open()
        else:
            self.mostrar_configuracion_sistema()
    
    def on_admin_login(self, success):
        """Callback después del login de admin"""
        if success:
            self.admin_authenticated = True
            self.mostrar_configuracion_sistema()
    
    def mostrar_configuracion_sistema(self):
        """Muestra la configuración del sistema"""
        # Aquí puedes mostrar opciones avanzadas de configuración
        popup = Popup(
            title="Configuración del Sistema",
            size_hint=(0.8, 0.8),
            auto_dismiss=False
        )
        self._popup_configuracion = popup
        
        content = BoxLayout(orientation='vertical', padding=20, spacing=10)

        # Estado actual del sistema
        estado_actual = self.system_manager.esta_activo()
        estado_texto = "RESTAURADO" if estado_actual else "BLOQUEADO"
        estado_color = (0.2, 0.7, 0.2, 1) if estado_actual else (0.9, 0.2, 0.2, 1)
        
        content.add_widget(Label(
            text=f"Estado del Sistema: {estado_texto}",
            font_size=20,
            color=estado_color,
            bold=True
        ))
        
        # Botón para cambiar estado
        btn_text = "BLOQUEAR Sistema" if estado_actual else "RESTAURAR Sistema"
        btn_color = (0.9, 0.2, 0.2, 1) if estado_actual else (0.2, 0.7, 0.2, 1)
        
        btn_cambiar = Button(
            text=btn_text,
            size_hint_y=None,
            height=50,
            background_color=btn_color,
            on_release=lambda x: self.mostrar_confirmacion_cambio()
        )
        content.add_widget(btn_cambiar)
        
        # Otras opciones de configuración
        content.add_widget(Button(
            text="Respaldar Base de Datos",
            size_hint_y=None,
            height=40,
            on_release=lambda x: self.respaldar_bd()
        ))
        
        content.add_widget(Button(
            text="Configuración Avanzada",
            size_hint_y=None,
            height=40,
            on_release=lambda x: self.configuracion_avanzada()
        ))
        
        content.add_widget(Button(
            text="Cerrar",
            size_hint_y=None,
            height=40,
            on_release=lambda x: self.cerrar_configuracion(popup)
        ))
        
        popup.content = content
        popup.open()
    
    def mostrar_confirmacion_cambio(self):
        """Muestra popup de confirmación para cambiar estado"""
        estado_actual = self.system_manager.esta_activo()
        popup = SystemStatusPopup(
            self.activar_sistema_completo,
            self.desactivar_sistema_completo,
            estado_actual,
            size_hint=(0.6, 0.5)
        )
        popup.open()
    
    def activar_sistema_completo(self):
        """RESTAURA completamente el sistema"""
        try:
            self.system_manager.activar_sistema()
            self.mostrar_notificacion("Sistema RESTAURADO completamente")
            
            # Notificar a AdminWindow para que desbloquee botones
            app = App.get_running_app()
            if hasattr(app.root, 'admin_widget'):
                admin = app.root.admin_widget
                admin.ids.notification.text = ""
                admin.desbloquear_todo()  # <-- LLAMAR AL NUEVO MÉTODO
            
            # Notificar a VentasWindow
            if hasattr(app.root, 'ventas_widget'):
                self.habilitar_controles_ventas(app.root.ventas_widget, True)

            if self._popup_configuracion:
                self._popup_configuracion.dismiss()
            Clock.schedule_once(lambda dt: self.mostrar_configuracion_sistema(), 0.3)
            
        except Exception as e:
            logging.error(f"Error restaurando sistema: {e}")
            self.mostrar_notificacion(f"Error: {str(e)}", error=True)
    
    def desactivar_sistema_completo(self):
        """BLOQUEA completamente el sistema"""
        try:
            self.system_manager.desactivar_sistema()
            self.mostrar_notificacion("Sistema BLOQUEADO completamente")
            
            # Notificar a AdminWindow para que bloquee botones
            app = App.get_running_app()
            if hasattr(app.root, 'admin_widget'):
                admin = app.root.admin_widget
                admin.ids.notification.text = "SISTEMA BLOQUEADO"
                admin.ids.notification.color = (0.9, 0.2, 0.2, 1)
                admin.bloquear_acciones_admin()  # <-- LLAMAR AL NUEVO MÉTODO
            
            # Notificar a VentasWindow
            if hasattr(app.root, 'ventas_widget'):
                self.habilitar_controles_ventas(app.root.ventas_widget, False)

                # Cerrar popup actual y reabrir
            if self._popup_configuracion:
                self._popup_configuracion.dismiss()
            
            # Reabrir con estado actualizado
            Clock.schedule_once(lambda dt: self.mostrar_configuracion_sistema(), 0.3)
            
        except Exception as e:
            logging.error(f"Error bloqueando sistema: {e}")
            self.mostrar_notificacion(f"Error: {str(e)}", error=True)
    
    def habilitar_controles_ventas(self, ventas_widget, habilitar):
        """Habilita o deshabilita controles en ventas"""
        try:
            # Estos son los controles que queremos deshabilitar cuando el sistema esté desactivado
            controles_a_bloquear = [
                'buscar_codigo', 'buscar_nombre', 'borrar_articulo',
                'cambiar_cantidad', 'pagar', 'nueva_compra'
            ]
            
            for control_id in controles_a_bloquear:
                if hasattr(ventas_widget.ids, control_id):
                    control = ventas_widget.ids[control_id]
                    control.disabled = not habilitar
                    control.opacity = 1 if habilitar else 0.5
            
            # Actualizar notificación
            if hasattr(ventas_widget.ids, 'notificacion_falla'):
                if not habilitar:
                    ventas_widget.ids.notificacion_falla.text = "SISTEMA BLOQUEADO - Contacte a su administrador"
                    ventas_widget.ids.notificacion_falla.color = (0.9, 0.2, 0.2, 1)
                else:
                    ventas_widget.ids.notificacion_falla.text = "Sistema RESTAURADO"
                    ventas_widget.ids.notificacion_falla.color = (0.2, 0.7, 0.2, 1)
                    Clock.schedule_once(lambda dt: setattr(ventas_widget.ids.notificacion_falla, 'text', ''), 3)
                    
        except Exception as e:
            logging.error(f"Error actualizando controles de ventas: {e}")

    def _bloquear_controles_admin(self):
        """Bloquea controles en el panel admin cuando el sistema está BLOQUEADO"""
        try:
            app = App.get_running_app()
            if hasattr(app.root, 'admin_widget'):
                admin = app.root.admin_widget
                # Solo mostrar notificación, mantener botones de navegación activos
                if hasattr(admin.ids, 'notification'):
                    admin.ids.notification.text = "Sistema BLOQUEADO"
                    admin.ids.notification.color = (0.9, 0.2, 0.2, 1)
        except Exception as e:
            logging.error(f"Error bloqueando controles admin: {e}")
    
    def _desbloquear_controles_admin(self):
        """Desbloquea controles en el panel admin"""
        try:
            app = App.get_running_app()
            if hasattr(app.root, 'admin_widget'):
                admin = app.root.admin_widget
                if hasattr(admin.ids, 'notification'):
                    admin.ids.notification.text = "Sistema RESTAURADO"
                    admin.ids.notification.color = (0.2, 0.7, 0.2, 1)
                    Clock.schedule_once(lambda dt: setattr(admin.ids, 'notification', ''), 3)
        except Exception as e:
            logging.error(f"Error desbloqueando controles admin: {e}")
    
    def mostrar_notificacion(self, mensaje, error=False):
        """Muestra notificación al usuario"""
        popup = Popup(
            title="Notificación del Sistema" if not error else "Error",
            content=Label(text=mensaje),
            size_hint=(0.6, 0.4),
            auto_dismiss=True
        )
        popup.open()
        Clock.schedule_once(lambda dt: popup.dismiss(), 3)
    
    def respaldar_bd(self):
        """Respaldar base de datos"""
        self.mostrar_notificacion("Función de respaldo en desarrollo")
    
    def configuracion_avanzada(self):
        """Configuración avanzada"""
        self.mostrar_notificacion("Configuración avanzada en desarrollo")
    
    def cerrar_configuracion(self, popup):
        """Cierra la configuración y limpia autenticación"""
        try:
            self.admin_authenticated = False
            popup.dismiss()
            logging.info("Configuración cerrada correctamente")
        except Exception as e:
            logging.error(f"Error cerrando configuración: {e}")
            popup.dismiss()

class VistaUsuarios(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        Clock.schedule_once(self.cargar_usuarios, 1)
        
    def mostrar_notificacion_popup(self, mensaje):
        popup = Popup(
            title="Notificación",
            content=Label(text=mensaje),
            size_hint=(0.6, 0.4), 
            auto_dismiss=True
        )
        popup.open()
        Clock.schedule_once(lambda dt: popup.dismiss(), 2)
        
    def cargar_usuarios(self, *args):
        _usuarios = []
        connection = QueriesSQLServer.create_connection()
        usuarios_sql = QueriesSQLServer.execute_read_query(connection, """
        SELECT * from usuarios 
            WHERE ISNULL(activo, 1) = 1 
                AND tipo NOT IN ('administrador', 'superadmin')
                    AND username NOT IN ('superadmin', 'root')"""
        )
        if usuarios_sql:
            for usuario in usuarios_sql:
                _usuarios.append({'nombre': usuario[1], 'username': usuario[0], 'password': usuario[2], 'tipo': usuario[3]})
        self.ids.rv_usuarios.agregar_datos(_usuarios)
        
    
    def agregar_usuario(self, agregar=False, validado=None):
        if agregar:
            connection = QueriesSQLServer.create_connection()
            # Verificar si el producto ya existe
            cursor = connection.cursor()
            verificar_usuario = "SELECT COUNT(*) FROM usuarios WHERE username = ?;"
            cursor.execute(verificar_usuario, (validado['username'],))
            resultado = cursor.fetchall()
            if resultado[0][0] > 0:  # Si el producto ya existe
                popup = UsuarioPopup(self.agregar_usuario)
                popup.ids.no_valido_notif_2.text = f"El usuario {validado['username']} ya existe."
                popup.open()
            else:
                # Si no existe, agregar el producto
                usuario_tuple = (validado['username'], validado['nombre'], validado['password'], validado['tipo'])
                crear_usuario = """
                INSERT INTO
                    usuarios (username, nombre, password, tipo)
                VALUES
                    (?, ?, ?, ?);
                """
                QueriesSQLServer.execute_query(connection, crear_usuario, usuario_tuple)
                logging.info(f"Usuario agregado correctamente.: {usuario_tuple}")
                self.ids.rv_usuarios.data.append(validado)
                self.ids.rv_usuarios.refresh_from_data()
                self.mostrar_notificacion_popup(f"Usuario '{validado['nombre']}' agregado correctamente.")
        else:
            popup = UsuarioPopup(self.agregar_usuario)
            popup.abrir(True)
        

    def modificar_usuario(self, modificar=False, validado=None):
        indice=self.ids.rv_usuarios.dato_seleccionado()
        if modificar:
            connection = QueriesSQLServer.create_connection()
            usuario_tuple = (validado['nombre'], validado['password'], validado['tipo'], validado['username'])
            actualizar_usuario = """
            UPDATE
                usuarios 
            SET
                nombre=?, password=?, tipo=?
            WHERE
                username=?;
            """
            QueriesSQLServer.execute_query(connection, actualizar_usuario, usuario_tuple)
            logging.info(f"Usuario modificado correctamente.:, {usuario_tuple}" )
            self.ids.rv_usuarios.data[indice]['nombre']=validado['nombre']
            self.ids.rv_usuarios.data[indice]['password']=validado['password']
            self.ids.rv_usuarios.data[indice]['tipo']=validado['tipo']
            self.ids.rv_usuarios.refresh_from_data()
            self.mostrar_notificacion_popup(f"Usuario '{validado['nombre']}' modificado correctamente.")
        else:
            if indice>=0:
                usuario=self.ids.rv_usuarios.data[indice]
                popup = UsuarioPopup(self.modificar_usuario)
                popup.abrir(False, usuario)

    def eliminar_usuario(self):
        if hasattr(self, 'ids') and 'rv_usuarios' in self.ids:
            rv = self.ids.rv_usuarios
            indice = rv.dato_seleccionado()
            if indice >= 0:
                usuario_tuple = (rv.data[indice]['username'],)
                connection = QueriesSQLServer.create_connection()
                # borrar_usuario = """ DELETE from usuarios WHERE username = ? """
                # Marcar como inactivo en lugar de eliminar
                desactivar_usuario = """
                    UPDATE usuarios
                    SET activo = 0
                    WHERE username = ?
                    """

                try:
                    QueriesSQLServer.execute_query(connection, desactivar_usuario, usuario_tuple)
                    logging.info(f"Usuario desactivado correctamente: {usuario_tuple}")
                    rv.data.pop(indice)
                    rv.refresh_from_data()
                    self.mostrar_notificacion_popup(
                        f"Usuario '{usuario_tuple[0]}' eliminado correctamente.."
                    )
                    
                except Exception as e:
                    logging.error(f"Error al desactivar usuario: {e}")
                    self.mostrar_notificacion_popup(
                        f"Error al eliminar usuario. '{usuario_tuple[0]}'"
                    )
                    
                # QueriesSQLServer.execute_query(connection, desactivar_usuario, usuario_tuple)
                # logging.info(f"Usuario eliminado correctamente.: {usuario_tuple}")
                # rv.data.pop(indice)
                # rv.refresh_from_data()
                # self.mostrar_notificacion_popup(f"Usuario '{usuario_tuple[0]}' eliminado correctamente.")


class InfoVentaPopup(Popup):
	select_item_query=" SELECT nombre FROM productos WHERE codigo = ?  "
	def __init__(self, venta, **kwargs):
		super(InfoVentaPopup, self).__init__(**kwargs)	
		self.connection = QueriesSQLServer.create_connection()
		self.venta=[{"codigo": producto[3], "producto": QueriesSQLServer.execute_read_query(self.connection, self.select_item_query, 
                                                                                      (producto[3],))[0][0], "cantidad": producto[4], "precio": producto[2], "total": producto[4]*producto[2]} for producto in venta]

	def mostrar(self):
		self.open()
		total_items=0
		total_dinero= Decimal(0.0)
		for articulo in self.venta:
			total_items+=articulo['cantidad']
			total_dinero += Decimal(articulo['total'])
		self.ids.total_items.text=str(total_items)
		self.ids.total_dinero.text="$ "+format_currency(total_dinero)
		self.ids.info_rv.agregar_datos(self.venta)


class PopupVenta(Popup):
    vista_ventas = ObjectProperty(None)# Define la propiedad
    def select_today(self):
        today = datetime.today().date()
        self.ids.single_date_input.text = today.strftime('%d/%m/%y')
        
    def cargar_ventas(self):
        self.vista_ventas.cargar_ventas()  
        


class VistaVentas(Screen):
    productos_actuales = []
    popup_actual = None  # Referencia al popup actual para cerrarlo si existe

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def crear_pdf(self):
        connection = QueriesSQLServer.create_connection()
        select_item_query = "SELECT nombre FROM productos WHERE codigo=?"

        select_username_query = "SELECT TOP 1 username FROM usuarios WHERE tipo = 'admin' ORDER BY nombre DESC"

        resultado = QueriesSQLServer.execute_read_query(connection, select_username_query)

        if resultado:
            self.username = resultado[0][0]  
        else:
            self.username = "Usuario desconocido"  


        if self.ids.ventas_rv.data:
            pdf_reporte = 'C:\\Users\\user\\Documents\\ventas\\'

            if not os.path.exists(pdf_reporte):
                os.makedirs(pdf_reporte)

            fecha_reporte = self.ids.date_id.text
            pdf_nombre = f"{pdf_reporte}reporte_{fecha_reporte}.pdf"
            logging.info(f"Archivo guardado correctamente: {pdf_reporte}")

            productos_pdf = []
            total = 0

            for venta_info in self.productos_actuales:
                if isinstance(venta_info, dict) and 'detalle' in venta_info:
                    for item in venta_info['detalle']:
                        # CONVERTIR A NÚMEROS ANTES DE MULTIPLICAR
                        try:
                            precio = float(item[2])  # Convertir precio a float
                            cantidad = int(item[4])  # Convertir cantidad a int
                            item_total = precio * cantidad
                            total += item_total
                        except (ValueError, TypeError) as e:
                            logging.error(f"Error convirtiendo datos: {e}, item: {item}")
                            continue

                        item_found = next((producto for producto in productos_pdf if producto["codigo"] == item[3]), None)
                        # total += item[2] * item[4]

                        if item_found:
                            item_found['cantidad'] += item[4]
                            item_found['precio_total'] += item_total #item_found['precio'] * item_found['cantidad']
                        else:
                            nombre = QueriesSQLServer.execute_read_query(connection, select_item_query, (item[3],))[0][0]
                            productos_pdf.append({
                                'nombre': nombre,
                                'codigo': item[3],
                                'cantidad': item[4],
                                'precio': precio,
                                'precio_total': item_total
                            }
                        )

            # Crear el PDF
            c = canvas.Canvas(pdf_nombre, pagesize=letter)
            c.setFont("Helvetica-Bold", 12)
            c.drawString(50, 750, "Reporte de Ventas")
            c.setFont("Helvetica", 10)
            c.drawString(50, 735, f"Fecha: {self.ids.date_id.text}")
            c.drawString(50, 720, f"Generado por: {self.username}")
            c.drawString(50, 710, "-" * 150)

            # alinear encabezado manual
            y_position = 695
            c.setFont("Helvetica-Bold", 10)
            c.drawString(50, y_position, "Nombre")
            c.drawString(220, y_position, "Código")
            c.drawString(320, y_position, "Cantidad")
            c.drawString(400, y_position, "Precio")
            c.drawString(480, y_position, "Total")

            y_position -= 20
            c.setFont("Helvetica", 10)

            # productos
            for producto in productos_pdf:
                c.drawString(50, y_position, f"{producto['nombre'][:20]:<20}")  
                c.drawString(220, y_position, f"{producto['codigo']:<10}")
                c.drawRightString(350, y_position, f"{producto['cantidad']:<5}") 
                precio_formateado = format_currency(producto['precio'])  # Formatear precio con separador de miles (COP)
                c.drawRightString(440, y_position, f"{precio_formateado:<7}")
                total_formateado = format_currency(producto['precio_total'])  # Formatear precio con separador de miles (COP)
                c.drawRightString(520, y_position, f"{total_formateado:<7}")
                y_position -= 15

            # Total
            c.setFont("Helvetica-Bold", 10)
            c.drawString(50, y_position - 10, "-" * 150)
            y_position -= 30
            c.drawString(322, y_position, "Total :")
            total_final_formateado = format_currency(total)  # Formatear total final con separador de miles
            c.drawRightString(520, y_position, f"{total_final_formateado}")

            c.save()

            self.ids.notificacion.text = 'Archivo PDF creado y guardado'
        else:
            self.ids.notificacion.text = 'No hay datos que guardar'

    def mas_info(self):
        # Cerrar popup anterior si existe
        if self.popup_actual is not None:
            try:
                self.popup_actual.dismiss()
            except:
                pass
            self.popup_actual = None
        
        # Limpiar todas las selecciones antes de obtener la actual
        indice = -1
        for i in range(len(self.ids.ventas_rv.data)):
            if self.ids.ventas_rv.data[i].get('seleccionado', False):
                indice = i
                # Asegurar que solo esta esté seleccionada
                for j in range(len(self.ids.ventas_rv.data)):
                    self.ids.ventas_rv.data[j]['seleccionado'] = (j == i)
                break
        
        if indice >= 0 and indice < len(self.ids.ventas_rv.data):
            # Obtener el ID real de la venta seleccionada
            venta_id = self.ids.ventas_rv.data[indice].get("id_venta")
            
            if venta_id is None:
                logging.error(f"Error: id_venta no encontrado en índice. {indice}")
                return
            
            # Buscar su detalle en la lista actual
            venta_detalle = []
            for v in self.productos_actuales:
                if isinstance(v, dict) and v.get("id_venta") == venta_id:
                    venta_detalle = v.get("detalle", [])
                    break

            # Mostrar el popup con la venta correcta
            if venta_detalle:
                p = InfoVentaPopup(venta_detalle)
                self.popup_actual = p  # Guardar referencia
                # Cerrar el popup cuando se cierre
                p.bind(on_dismiss=lambda *args: setattr(self, 'popup_actual', None))
                p.mostrar()
                logging.info(f"Mostrando detalle para venta {venta_id} con {len(venta_detalle)} productos")
            else:
                logging.error(f"Error: No se encontró detalle para venta {venta_id}")
        else:
            logging.error(f"Error: Índice inválido {indice} o no hay venta seleccionada")

            
## implementacion Popup a ventas

    def open_popup(self):
        self.popup = PopupVenta(vista_ventas=self)
        self.popup.open()
        self.cargar_usuarios()

    def select_today(self):
        today = datetime.today().date()
        self.popup.ids.single_date_input.text = today.strftime('%d/%m/%y')
        
    def cargar_usuarios(self):
        connection = QueriesSQLServer.create_connection()
        if not connection:
            logging.error("Error al conectar con la base de datos")
            return
    
        select_usuarios_query = "SELECT DISTINCT username FROM ventas"
        usuarios_sql = QueriesSQLServer.execute_read_query(connection, select_usuarios_query)
    
        # Verificar que se obtuvieron datos
        if usuarios_sql:
            logging.info(f"Usuarios obtenidos de la base de datos: {usuarios_sql}")
        else:
            logging.error("No se encontraron usuarios en la tabla de ventas.")
    
        if hasattr(self.popup, 'ids') and 'usuario_spinner' in self.popup.ids:
            self.popup.ids.usuario_spinner.values = []  
            self.usuarios_cargados = []  
    
            if usuarios_sql:  # Solo agregar usuarios si hay datos
                for usuario in usuarios_sql:
                    self.usuarios_cargados.append(usuario[0])
    
            # Actualizar el spinner con los usuarios
            self.popup.ids.usuario_spinner.values = self.usuarios_cargados
            logging.info(f"Usuarios cargados en el spinner: {self.popup.ids.usuario_spinner.values}")
        else:
            logging.error("No se encontró el spinner de usuario en el popup.")

    

    def cargar_ventas(self):
        username = self.popup.ids.usuario_input.text.strip()  # Obtener el nombre ingresado
        logging.info(f"Usuario ingresado: {username}")

        fecha = self.popup.ids.single_date_input.text
        fecha_inicio = self.popup.ids.initial_date_input.text
        fecha_fin = self.popup.ids.last_date_input.text

        choice = 'Default'
        if fecha:
            choice = 'Date'
        elif fecha_inicio and fecha_fin:
            choice = 'Range'

        self.cargar_venta(choice, username, fecha, fecha_inicio, fecha_fin)
        self.popup.dismiss()

    def cargar_venta(self, choice='Default', username='', fecha='', fecha_inicio='', fecha_fin=''):
        connection = QueriesSQLServer.create_connection()
        
        if self.popup_actual is not None:
            try:
                self.popup_actual.dismiss()
            except:
                pass
            self.popup_actual = None
        
        final_sum = 0
        _ventas = []
        _total_productos = []
        self.ids.ventas_rv.limpiar_datos()
        self.productos_actuales = []  # Limpiar productos actuales antes de cargar nuevos

        try:
            if choice == 'Default':
                fecha_inicio = datetime.today().date()
                fecha_fin = datetime.combine(fecha_inicio, datetime.max.time())
                # fecha_fin = fecha_inicio + timedelta(days=1)
                self.ids.date_id.text = fecha_inicio.strftime("%d-%m-%y")
            elif choice == 'Date' and fecha:
                fecha = fecha.strip()
                formato_fecha = '%d/%m/%Y' if len(fecha.split('/')[-1]) == 4 else '%d/%m/%y'
                fecha_inicio = datetime.strptime(fecha, formato_fecha).date()
                fecha_fin = datetime.combine(fecha_inicio, datetime.max.time())
                # fecha_fin = fecha_inicio + timedelta(days=1)
                self.ids.date_id.text = fecha_inicio.strftime('%d-%m-%y')
            elif choice == 'Range' and fecha_inicio and fecha_fin:
                fecha_inicio = fecha_inicio.strip()
                fecha_fin = fecha_fin.strip()
                formato_fecha = '%d/%m/%Y' if len(fecha_inicio.split('/')[-1]) == 4 else '%d/%m/%y'
                fecha_inicio = datetime.strptime(fecha_inicio, formato_fecha).date()
                fecha_fin_original = datetime.strptime(fecha_fin, formato_fecha).date()
                fecha_fin = datetime.combine(fecha_fin_original, datetime.max.time())
                # fecha_fin = datetime.strptime(fecha_fin, formato_fecha).date() + timedelta(days=1)
                self.ids.date_id.text = fecha_inicio.strftime("%d-%m-%y") + " - " + fecha_fin.strftime("%d-%m-%y")
            else:
                raise ValueError("Fechas no válidas")

            logging.info(f"Ejecutando consulta con fechas: {fecha_inicio} - {fecha_fin} y usuario: {username}")
        except ValueError as e:
            logging.error(f"Error en la conversión de fechas: {e}")
            return

        query_params = [fecha_inicio, fecha_fin]
        if username and username != "Seleccionar Usuario":
            # select_ventas_query = "SELECT * FROM ventas WHERE fecha BETWEEN ? AND ? AND username = ?"
            select_ventas_query = """
                SELECT 
                    id, total, fecha, username,
                    id_factura, id_turno, id_dispositivo,
                    prefijo_resolucion, num_resolucion, consecutivo,
                    subtotal, impuestos, metodo_pago
                FROM ventas 
                WHERE fecha BETWEEN ? AND ? AND username = ?
            """
            query_params.append(username)
        else:
            # select_ventas_query = "SELECT * FROM ventas WHERE fecha BETWEEN ? AND ?"
            select_ventas_query = """
                SELECT 
                    id, total, fecha, username,
                    id_factura, id_turno, id_dispositivo,
                    prefijo_resolucion, num_resolucion, consecutivo,
                    subtotal, impuestos, metodo_pago
                FROM ventas 
                WHERE fecha BETWEEN ? AND ?
            """
        ventas_sql = QueriesSQLServer.execute_read_query(connection, select_ventas_query, 
                                        tuple(query_params))

        if ventas_sql:
            logging.info(f"Ventas obtenidas: {ventas_sql}")
            for venta in ventas_sql:
                final_sum += venta[1]
                logging.info(f"Procesando venta: {venta}")

                selec_productos_query = "SELECT * FROM ventas_detalle WHERE id_venta=?"
                ventas_detalle_sql = QueriesSQLServer.execute_read_query(connection, selec_productos_query, (venta[0],))
                _total_productos.append({"id_venta": venta[0], "detalle": ventas_detalle_sql})

                count = sum(producto[4] for producto in ventas_detalle_sql)

                _ventas.append({
                    "id_venta": venta[0],
                    "username": venta[3],
                    "productos": count,
                    "total": venta[1],
                    "fecha": venta[2] if isinstance(venta[2], datetime) else datetime.strptime(venta[2], '%Y-%m-%d %H:%M:%S.%f')
                })

            self.ids.ventas_rv.agregar_datos(_ventas)
            self.productos_actuales = _total_productos
        else:
            logging.info("No se encontraron ventas para el rango de fechas seleccionado.")

        self.ids.final_sum.text = '$ ' + format_currency(final_sum)
        self.ids.initial_date.text = ''
        self.ids.last_date.text = ''
        self.ids.single_date.text = ''
        self.ids.notificacion.text = 'Datos de Ventas'
        
        #------   
                  
class VistaSettings(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.config = config
        # Vista de configuraciones - puede expandirse según necesidades

    def configurar_impresora(self):
        PruebInpresion = Herramientas()
        PruebInpresion._on_prueba_impresion(ventana=self)

    def configurar_scanner(self):
        logging.info("Configurar Pistola Scanner")
        # La configuración del scanner ahora está en settings.json
        scanner_config = config.get("scanner")
        if scanner_config:
            logging.info(f"Scanner config: enabled={scanner_config.get('enabled')}, mode={scanner_config.get('mode')}")

        # Configuración cargada
    def abrir_turno(self):
        herramientas = Herramientas()
        ok = herramientas.abrir_turno(user="POS")

        if ok:
            popup = Popup(
                title="Notificación",
                content=Label(text="Turno abierto correctamente"),
                size_hint=(0.6, 0.3),
                auto_dismiss=True
            )
            popup.open()
            Clock.schedule_once(lambda dt: popup.dismiss(), 2)

        self.config.set("turno", {"Status": "ABIERTO", "user": "POS", "info_only": True})

    def cerrar_turno(self):
        herramientas = Herramientas()
        herramientas.cerrar_turno()

        self.config.set("turno", {"Status": "CERRADO", "user": "POS", "info_only": True})
        logging.info("Turno cerrado correctamente.")

class CustomDropDown(DropDown):
    def __init__(self, cambiar_collback, **kwargs):
        self.cpuv_ad = cambiar_collback
        super(CustomDropDown, self).__init__(**kwargs)
        
    def vista(self, vista):
        if callable(self.cpuv_ad):
            self.cpuv_ad(True, vista)
    

class AdminWindow(BoxLayout):
    def __init__(self,  **kwargs):
        super().__init__(**kwargs)
        self.vista_actual = 'Productos'
        self.vista_manager = self.ids.vista_manager
        self.dropdown = CustomDropDown(self.cambiar_vista)
        self.ids.cambiar_vista.bind(on_release=self.dropdown.open)
        self.system_manager = SystemManager()  
        self.es_administrador = False
        self.verificar_privilegios()

        # Verificar estado del sistema al iniciar
        Clock.schedule_once(self.verificar_estado_sistema, 0.5)

    def verificar_estado_sistema(self, dt):
        """Verifica y aplica el estado del sistema al iniciar"""
        if not self.system_manager.esta_activo():
            # Si el sistema está desbloqueado, mostrar notificación
            self.ids.notification.text = "SISTEMA BLOQUEADO"
            self.ids.notification.color = (0.9, 0.2, 0.2, 1)  # Rojo
            
            # Solo permitir cambiar vista y administrador
            Clock.schedule_once(lambda dt: self.bloquear_acciones_admin(), 0.2)
            Clock.schedule_once(lambda dt: self.permitir_solo_navegacion(), 0.2)
        else:
            self.ids.notification.text = ""
            Clock.schedule_once(lambda dt: self.desbloquear_todo(), 0.2)

    def bloquear_acciones_admin(self):
        """Bloquea botones de acciones en todas las vistas admin"""
        try:
            # Bloquear en Productos
            if hasattr(self.ids, 'vista_productos'):
                vista = self.ids.vista_productos
                # Bloquear buscador
                if hasattr(vista.ids, 'buscador_productos'):
                    vista.ids.buscador_productos.disabled = True
                    vista.ids.buscador_productos.hint_text = "Sistema BLOQUEADO"
                    vista.ids.buscador_productos.opacity = 0.5
                self._bloquear_botones_en_layout(vista)
            
            # Bloquear en Usuarios
            if hasattr(self.ids, 'vista_usuarios'):
                vista = self.ids.vista_usuarios
                self._bloquear_botones_en_layout(vista)
            
            # Bloquear en Ventas
            if hasattr(self.ids, 'vista_ventas'):
                vista = self.ids.vista_ventas
                botones_ventas = [
                    'btn_ver_ventas',
                    'btn_mas_info',
                    'btn_guardar_pdf'
                ]
                for btn_id in botones_ventas:
                    if hasattr(vista.ids, btn_id):
                        vista.ids[btn_id].disabled = True
                        vista.ids[btn_id].opacity = 0.5
            
            # Bloquear en Configuraciones
            if hasattr(self.ids, 'vista_configuraciones'):
                vista = self.ids.vista_configuraciones
                controles_bloquear = [
                    'btn_config_impresora',
                    'btn_config_scanner',
                    'btn_abrir_turno',
                    'btn_cerrar_turno'
                ]
                for control in controles_bloquear:
                    if hasattr(vista.ids, control):
                        vista.ids[control].disabled = True
                        vista.ids[control].opacity = 0.5
            
            # Bloquear en Administrador
            if hasattr(self.ids, 'vista_administrador'):
                vista = self.ids.vista_administrador
                if hasattr(vista, 'ids'):
                    for key in vista.ids:
                        widget = vista.ids[key]
                        if isinstance(widget, Button):
                            widget.disabled = True
                            widget.opacity = 0.5
        
        except Exception as e:
            logging.error(f"Error bloqueando acciones admin: {e}")

    def _bloquear_botones_en_layout(self, vista):
        """Busca y bloquea botones en un layout"""
        try:
            # Buscar botones en el layout
            def buscar_botones(widget):
                if isinstance(widget, Button):
                    widget.disabled = True
                    widget.opacity = 0.5
                elif hasattr(widget, 'children'):
                    for child in widget.children:
                        buscar_botones(child)
            
            # Comenzar búsqueda desde el layout principal de la vista
            if hasattr(vista, 'children'):
                for child in vista.children:
                    buscar_botones(child)
        except Exception as e:
            logging.error(f"Error buscando botones: {e}")

    def permitir_solo_navegacion(self):
        """Permite solo navegación entre vistas"""
        try:
            navegacion_ids = [
                'cambiar_vista',
                'boton_venta', 
                'boton_signout'
            ]
            
            for btn_id in navegacion_ids:
                if hasattr(self.ids, btn_id):
                    self.ids[btn_id].disabled = False
                    self.ids[btn_id].opacity = 1
        
        except Exception as e:
            logging.error(f"Error configurando navegación: {e}")

    def desbloquear_todo(self):
        """Desbloquea todos los controles"""
        try:
            # Quitar notificación
            self.ids.notification.text = ""
            
            # Desbloquear en Productos
            if hasattr(self.ids, 'vista_productos'):
                vista = self.ids.vista_productos
                # Desbloquear buscador
                if hasattr(vista.ids, 'buscador_productos'):
                    vista.ids.buscador_productos.disabled = False
                    vista.ids.buscador_productos.hint_text = "Buscar producto (código o nombre)"
                    vista.ids.buscador_productos.opacity = 1
                
                # Desbloquear botones en productos
                self._desbloquear_botones_en_layout(vista)
            
            # Desbloquear en Usuarios
            if hasattr(self.ids, 'vista_usuarios'):
                vista = self.ids.vista_usuarios
                self._desbloquear_botones_en_layout(vista)
            
            # Desbloquear en Ventas
            if hasattr(self.ids, 'vista_ventas'):
                vista = self.ids.vista_ventas
                botones_ventas = [
                    'btn_ver_ventas',
                    'btn_mas_info',
                    'btn_guardar_pdf'
                ]
                for btn_id in botones_ventas:
                    if hasattr(vista.ids, btn_id):
                        vista.ids[btn_id].disabled = False
                        vista.ids[btn_id].opacity = 1
            
            # Desbloquear en Configuraciones
            if hasattr(self.ids, 'vista_configuraciones'):
                vista = self.ids.vista_configuraciones
                controles_desbloquear = [
                    'btn_config_impresora',
                    'btn_config_scanner',
                    'btn_abrir_turno',
                    'btn_cerrar_turno'
                ]
                for control in controles_desbloquear:
                    if hasattr(vista.ids, control):
                        vista.ids[control].disabled = False
                        vista.ids[control].opacity = 1
            
            # Desbloquear en Administrador
            if hasattr(self.ids, 'vista_administrador'):
                vista = self.ids.vista_administrador
                if hasattr(vista, 'ids'):
                    for key in vista.ids:
                        widget = vista.ids[key]
                        if isinstance(widget, Button):
                            widget.disabled = False
                            widget.opacity = 1
        
        except Exception as e:
            logging.error(f"Error desbloqueando controles: {e}")

    def _desbloquear_botones_en_layout(self, vista):
        """Busca y desbloquea botones en un layout"""
        try:
            # Buscar botones en el layout
            def buscar_botones(widget):
                if isinstance(widget, Button):
                    widget.disabled = False
                    widget.opacity = 1
                elif hasattr(widget, 'children'):
                    for child in widget.children:
                        buscar_botones(child)
            
            # Comenzar búsqueda desde el layout principal de la vista
            if hasattr(vista, 'children'):
                for child in vista.children:
                    buscar_botones(child)
        except Exception as e:
            logging.error(f"Error buscando botones: {e}")

    def verificar_privilegios(self):
        """Verifica si el usuario actual tiene privilegios de admin"""
        from Src.Config.config_loader import CURRENT_USER
        if CURRENT_USER and CURRENT_USER.get('tipo') == 'administrador':
            self.es_administrador = True
            pass
        
    def cambiar_vista(self, cambio=False, vista=None):
        if cambio:
            if vista == 'Administrador' and not self.es_administrador:
                self.ids.vista_administrador.mostrar_login_admin()
            else:
                self.vista_actual = vista
                self.vista_manager.current=self.vista_actual
                self.dropdown.dismiss()

    def signout(self):
        self.parent.parent.current = 'scrn_signin'

    def venta(self):
        self.parent.parent.current = 'scrn_ventas'
        
        
    def actualizar_inventario(self, productos):
         if hasattr(self.ids, 'vista_productos'):
            self.ids.vista_productos.actualizar_productos(productos)

class AdminApp(App):
    def build(self):
        return AdminWindow()


if __name__ == "__main__":
    AdminApp().run()#######v14-----17
