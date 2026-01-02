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

from Src.Views.sqlqueries import QueriesSQLServer
import logging
from Src.Config.config_loader import load_config, config
from Src.Views.Settings import Herramientas, Config

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


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
KV_PATH = os.path.join(BASE_DIR, "admin_view.kv")
Builder.load_file(KV_PATH)

# Builder.load_file('Src/Views/admin_view.kv')


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
            validado['password']=usuario_password
            
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
        usuarios_sql = QueriesSQLServer.execute_read_query(connection, "SELECT * from usuarios WHERE ISNULL(activo, 1) = 1")
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
	connection = QueriesSQLServer.create_connection()
	select_item_query=" SELECT nombre FROM productos WHERE codigo = ?  "
	def __init__(self, venta, **kwargs):
		super(InfoVentaPopup, self).__init__(**kwargs)	
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
        
    def cambiar_vista(self, cambio=False, vista=None):
        if cambio:
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
    AdminApp().run()#######v14-----16
