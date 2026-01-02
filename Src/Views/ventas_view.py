from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.recycleview import RecycleView
from kivy.uix.recycleview.views import RecycleDataViewBehavior
from kivy.properties import BooleanProperty
from kivy.uix.recycleboxlayout import RecycleBoxLayout
from kivy.uix.behaviors import FocusBehavior
from kivy.uix.recycleview.layout import LayoutSelectionBehavior
from kivy.uix.popup import Popup
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.core.window import Window
from decimal import Decimal

import sys
import subprocess
import os
import json
import logging
import traceback
from datetime import datetime, timedelta
from kivy.animation import Animation

from Src.Views.Settings import Herramientas, mostrar_notificacion_popup
from Src.Config.config_loader import load_config, config, CURRENT_USER

os.environ["KIVY_NO_ARGS"] = "1"

def format_currency(value):
    """Formatea valores monetarios para COP (Colombia)"""
    try:
        if isinstance(value, str):
            value = value.replace('.', '').replace(',', '.')
            value = float(value)
    
        value_int = int(round(value))
        formatted = f"{value_int:,}".replace(",", ".") # Formatear con separadores de miles
        
        return f"${formatted}"
    except Exception as e:
        logging.error(f"Error formateando valor {value}: {e}")
        return "$0"

log = logging.getLogger(__name__)

kv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ventas_view.kv")
Builder.load_file(kv_path)

from Src.Views.sqlqueries import QueriesSQLServer

server = config.get("database", "server")
database = config.get("database", "database")
username = config.get("database", "username")
password = config.get("database", "password")

#inventario=[
#    {'codigo': '222', 'nombre': 'leche de vaca','precio': 15.100,'cantidad': 10},
#    {'codigo': '332', 'nombre': 'helado cremoso 1L','precio': 6.500,'cantidad': 30},
#    {'codigo': '442', 'nombre': 'pollo entero','precio': 12.000,'cantidad': 55},
#    {'codigo': '664', 'nombre': 'arroz cereal','precio': 13.100,'cantidad': 88},
#    {'codigo': '754', 'nombre': 'avena molida 80g','precio': 3.000,'cantidad': 65},
#    {'codigo': '845', 'nombre': 'promasa de la abuela 10g','precio': 5.000,'cantidad': 77},
#    {'codigo': '143', 'nombre': 'lentejas del caribe 30g', 'precio': 4.500,'cantidad': 99},
#    {'codigo': '557', 'nombre': 'alberja el buen comer','precio': 3.700,'cantidad': 37},
#    {'codigo': '993', 'nombre': 'chorizos zenu', 'precio': 8.800,'cantidad': 54}
#
#]

class SelectableRecycleBoxLayout(FocusBehavior, LayoutSelectionBehavior,
                                 RecycleBoxLayout):
    ''' Adds selection and focus behavior to the view. '''
    touch_deselect_last = BooleanProperty(True)


class SelectableBoxLayout(RecycleDataViewBehavior, BoxLayout):
    ''' Add selection support to the Label '''
    index = None
    selected = BooleanProperty(False)
    selectable = BooleanProperty(True)

    def refresh_view_attrs(self, rv, index, data):
        self.index = index
        self.ids['_hashtag'].text = str(1+index)
        self.ids['_articulo'].text = data['nombre'].capitalize()                         
        self.ids['_cantidad'].text = str(data['cantidad_carrito'])
        self.ids['_precio_por_articulo'].text = format_currency(data['precio'])
        self.ids['_precio'].text = format_currency(data['precio_total'])
        return super(SelectableBoxLayout, self).refresh_view_attrs(
            rv, index, data)

    def on_touch_down(self, touch):
        ''' Add selection on touch down '''
        if super(SelectableBoxLayout, self).on_touch_down(touch):
            return True
        if self.collide_point(*touch.pos) and self.selectable:
            return self.parent.select_with_touch(self.index, touch)

    def apply_selection(self, rv, index, is_selected):
        ''' Respond to the selection of items in the view. '''
        self.selected = is_selected
        if is_selected:
            rv.data[index]['seleccionado']=True
        else:
            rv.data[index]['seleccionado']=False

class SelectableBoxLayoutPopup(RecycleDataViewBehavior, BoxLayout):
    ''' Add selection support to the Label '''
    index = None
    selected = BooleanProperty(False)
    selectable = BooleanProperty(True)

    def refresh_view_attrs(self, rv, index, data):
        self.index = index
        self.ids['_codigo'].text = data['codigo']
        self.ids['_articulo'].text = data['nombre'].capitalize()
        self.ids['_cantidad'].text = str(data['cantidad'])
        self.ids['_precio'].text = format_currency(data['precio'])
        return super(SelectableBoxLayoutPopup, self).refresh_view_attrs(
            rv, index, data)

    def on_touch_down(self, touch):
        ''' Add selection on touch down '''
        if super(SelectableBoxLayoutPopup, self).on_touch_down(touch):
            return True
        if self.collide_point(*touch.pos) and self.selectable:
            return self.parent.select_with_touch(self.index, touch)

    def apply_selection(self, rv, index, is_selected):
        ''' Respond to the selection of items in the view. '''
        self.selected = is_selected
        if is_selected:
            rv.data[index]['seleccionado']=True
        else:
            rv.data[index]['seleccionado']=False


class RV(RecycleView):
    def __init__(self, **kwargs):
        super(RV, self).__init__(**kwargs)
        self.data = []
        self.modificar_producto=None

    def agregar_articulo(self, articulo):
        articulo['seleccionado']=False
        indice=-1
        if self.data:
            for i in range(len(self.data)):
                if articulo['codigo']==self.data[i]['codigo']:
                    indice=i
            if indice >=0:
                self.data[indice]['cantidad_carrito']+=1
                self.data[indice]['precio_total']=self.data[indice]['precio']*self.data[indice]['cantidad_carrito']
                self.refresh_from_data()
            else:
                self.data.append(articulo)
        else:
            self.data.append(articulo)

    def eliminar_articulo(self):
        indice=self.articulo_seleccionado()
        precio=0
        if indice >=0:
            self._layout_manager.deselect_node(self._layout_manager._last_selected_node)
            precio=self.data[indice]['precio_total']
            self.data.pop(indice)
            self.refresh_from_data()
        return precio
    
    def modificar_articulo(self):
        indice=self.articulo_seleccionado()
        if indice>=0:
            Popup=CambiarCantidadPopup(self.data[indice], self.actualizar_articulo)
            Popup.open()

    def actualizar_articulo(self, valor):
        indice=self.articulo_seleccionado()
        if indice>=0:
            if valor==0:
                self.data.pop(indice)
                self._layout_manager.deselect_node(self._layout_manager._last_selected_node)
            else:
                self.data[indice]['cantidad_carrito']=valor
                self.data[indice]['precio_total']=self.data[indice]['precio']*valor
            self.refresh_from_data()
            nuevo_total=0
            for data in self.data:
                nuevo_total+=data['precio_total'] 
            self.modificar_producto(False, nuevo_total)   
    def articulo_seleccionado(self):
        indice=-1
        for i in range(len(self.data)):
            if self.data[i]['seleccionado']:
                indice=i
                break
        return indice

class ProductoPorNombrePopup(Popup):
    def __init__(self, input_nombre, agregar_producto_callback, ventana_ventas, **kwargs):
        super(ProductoPorNombrePopup, self).__init__(**kwargs)
        self.input_nombre=input_nombre
        self.agregar_producto=agregar_producto_callback
        self.ventana_ventas = ventana_ventas

    def mostrar_articulos(self):
        connection = QueriesSQLServer.create_connection()

        query = "SELECT * FROM productos WHERE ISNULL(activo, 1) = 1"
        inventario_sql = QueriesSQLServer.execute_read_query(connection, query)
        self.open()

        agotados = []

        for nombre in inventario_sql:
            if nombre[1].lower().find(self.input_nombre)>=0:
                if nombre[3] <= 0:  # Verificar si el producto está agotado
                    agotados.append(nombre)
                # Mostrar alerta
                    # self.ventana_ventas.ids.notificacion_falla.text = f"El producto '{nombre[1]}' está agotado."
                    # logging.warning(f"El producto: {nombre} esta agotado")
                    continue
                producto={'codigo': nombre[0], 'nombre': nombre[1], 'precio': nombre[2], 'cantidad': nombre[3]}
                self.ids.rvs.agregar_articulo(producto)

            # Mostrar alerta
        if agotados:
            agotados.sort(key=lambda x: x[1], reverse=True)  # orden descendente
            # self._agotados_original = agotados[:]
            self._agotados_pendientes = agotados[:]  # Copia segura

            self._agotados_loggeados = set()
            Clock.schedule_once(lambda dt: self._mostrar_agotados_secuencial(), 0.5)

    def _mostrar_agotados_secuencial(self):
        """Muestra los productos agotados """

        # Si ya no hay agotados por mostrar
        if not self._agotados_pendientes:
            self.ventana_ventas.ids.notificacion_falla.text = ""
            return
            # Reiniciar ciclo usando la lista original
            # self._agotados_pendientes = self._agotados_original[:]  
            # Clock.schedule_once(lambda dt: self._mostrar_agotados_secuencial(), 0.3)
            # return

        # Tomar siguiente agotado
        prod = self._agotados_pendientes.pop(0)
        nombre = prod[1]

        label = self.ventana_ventas.ids.notificacion_falla
        label.text = f"El producto '{nombre.upper()}' está agotado"
        if nombre not in self._agotados_loggeados:
            logging.warning(f"El producto: {nombre} está agotado")
            self._agotados_loggeados.add(nombre)

        # Crear animación segura
        anim = Animation(opacity=0.2, duration=0.35) + Animation(opacity=1, duration=0.35)
        anim.repeat = True
        anim.start(label)

        # Detener animación y mostrar siguiente
        def continuar(_):
            anim.stop(label)
            label.opacity = 1
            label.text = ""
            Clock.schedule_once(lambda dt: self._mostrar_agotados_secuencial(), 0.3)

        # Tiempo en pantalla por producto
        Clock.schedule_once(continuar, 2.2)


    def seleccionar_articulo(self):
        indice=self.ids.rvs.articulo_seleccionado()
        if indice>=0:
            _articulo=self.ids.rvs.data[indice]
            articulo={}
            articulo['codigo']=_articulo['codigo']
            articulo['nombre']=_articulo['nombre']
            articulo['precio']=float(_articulo['precio'])
            articulo['cantidad_carrito']=1
            articulo['cantidad_inventario']=_articulo['cantidad']
            articulo['precio_total']=float(_articulo['precio'])
            if callable(self.agregar_producto):
                self.agregar_producto(articulo)
            self.dismiss()
                
class CambiarCantidadPopup(Popup):
    def __init__(self, data, actualizar_articulo_callback, **kwargs):
        super(CambiarCantidadPopup, self).__init__(**kwargs)
        self.data=data
        self.actualizar_articulo=actualizar_articulo_callback
        self.ids.info_nueva_cant_1.text = "Producto: " + self.data['nombre'].capitalize()
        self.ids.info_nueva_cant_2.text = "Cantidad: " + str(self.data['cantidad_carrito'])

    def validar_input(self, texto_input):
        try:
            nueva_cantidad=int(texto_input)
            self.ids.notificacion_no_valido.text=''
            self.actualizar_articulo(nueva_cantidad)
            self.dismiss()
        except:
            self.ids.notificacion_no_valido.text='cantidad no valida'

class PagarPopup(Popup):
    def __init__(self, total, on_pago_completo_callback, **kwargs):
        super(PagarPopup, self).__init__(**kwargs)
        self.total=total
        # Callback que se ejecuta cuando el cobro termina correctamente
        self.on_pago_completo=on_pago_completo_callback
        self.ids.total.text=format_currency(self.total)
        self.ids.boton_pagar.bind(on_release=self.dismiss)
        
    def mostrar_cambio(self):
        recibido = self.ids.recibido.text.replace(".", "")
        try:
            cambio=float(recibido)-float(self.total)
            if cambio>=0:
                self.ids.cambio.text=format_currency(cambio)
                self.ids.boton_pagar.disabled=False
            else:
                self.ids.cambio.text="Pago menor a cantidad a pagar"
        except:
            self.ids.cambio.text="Pago no valido"

    def finalizar_cobro(self):
        recibido = float(self.ids.recibido.text.replace(".", ""))
        cambio = recibido - self.total
        if callable(self.on_pago_completo):
            self.on_pago_completo(recibido, cambio)


        

class NuevaCompraPopup(Popup):
    def __init__(self, nueva_compra_callback, **kwargs):
        super(NuevaCompraPopup, self).__init__(**kwargs)
        self.nueva_compra=nueva_compra_callback
        self.ids.aceptar.bind(on_release=self.dismiss)

class ConfirmarPagoPopup(Popup):
    def __init__(self, ventana_ventas, confirmar_callback, **kwargs):
        super(ConfirmarPagoPopup, self).__init__(**kwargs)
        self.ventana_ventas = ventana_ventas
        self.confirmar_callback = confirmar_callback
        # Cargar resumen del carrito
        try:
            self.ids.resumen_rv.data = [dict(item) for item in self.ventana_ventas.ids.rvs.data]
        except Exception as e:
            logging.error(f"No se pudo cargar el resumen del carrito: {e}")
        # Mostrar total
        self.ids.total_confirmacion.text = format_currency(self.ventana_ventas.total)

    def confirmar(self):
        if callable(self.confirmar_callback):
            self.confirmar_callback()
        self.dismiss()

    # def on_pago_completo(self):
    #     venta_data = {
    #         "items": self._convertir_items_para_factura(),
    #         "Tax": [],
    #         "PaymentMethod": 0,  # efectivo
    #         "PaymentDetails": {
    #             "valuePaid": self.total,
    #             "change": 0,
    #             "notDispense": 0
    #         }
    #     }

    #     FactuHerr = Herramientas()
    #     FactuHerr.generar_e_imprimir_factura(venta_data)

    #     self._limpiar_venta()

    # def _convertir_items_para_factura(self):
    #     items = []
    #     for p in self.ids.rv.data:
    #         items.append({
    #             "Id_Product": p["codigo"],
    #             "description": p["nombre"],
    #             "Total": p["precio_total"],
    #             "taxes": [],
    #             "include": True
    #         })
    #     return items


class TipoFacturaPopup(Popup):
    def __init__(self, confirmar_pago_callback, ventana_ventas, **kwargs):
        super(TipoFacturaPopup, self).__init__(**kwargs)
        # Este callback debe ejecutar el cierre del pago (pagado)
        self.confirmar_pago = confirmar_pago_callback
        self.ventana_ventas = ventana_ventas

    def finalizar_pago_sin_factura(self):
        # Desactivar impresión
        if self.ventana_ventas:
            self.ventana_ventas.imprimir_factura = False
        if callable(self.confirmar_pago):
            self.confirmar_pago()
        self.dismiss()

        Clock.schedule_once(lambda dt: setattr(self.ventana_ventas, 'imprimir_factura', True), 2)

    def imprimir_venta(self):
        # Activar impresión (ya está activado por defecto)
        if self.ventana_ventas:
            self.ventana_ventas.imprimir_factura = True
        if callable(self.confirmar_pago):
            self.confirmar_pago()
        self.dismiss()

    


# class NuevaVentaPopup(Popup):
#     def __init__(self, ventana_anterior, actualizar_inventario_callback, **kwargs):
#         super(NuevaVentaPopup, self).__init__(**kwargs)
#         self.ventana_anterior = ventana_anterior
#         # Crear una nueva ventana de ventas dentro del popup
#         try:
#             nueva = VentasWindow(actualizar_inventario_callback)
#             # Propagar usuario logueado si existe
#             if getattr(self.ventana_anterior, 'user_data', None):
#                 nueva.usuario_loggin(self.ventana_anterior.user_data)
#             # Insertar en el contenedor definido en KV (id: contenido)
#             self.ids.contenido.add_widget(nueva)
#         except Exception as e:
#             logging.info(f"Error creando nueva ventana de venta: {e}")
#         # Al cerrar, restaurar visibilidad/interacción de la ventana anterior
#         self.bind(on_dismiss=self._restaurar_anterior)

#     def _restaurar_anterior(self, *_):
#         try:
#             self.ventana_anterior.disabled = False
#             self.ventana_anterior.opacity = 1
#         except Exception:
#             pass

class VentasWindow(BoxLayout):
    user_data=None
    def __init__(self, actualizar_inventario_callback, terminal_id=1, user_data=None, **kwargs):
        super().__init__(**kwargs)

        self.terminal_id = terminal_id
        self.user_data = user_data or {"nombre": "Usuario", "tipo": "empleado"}
        self._actualizar_encabezado(self.user_data)
        self.imprimir_factura = True


        self.total=0.0
        self.ids.rvs.modificar_producto=self.modificar_producto
        self.actualizar_inventario=actualizar_inventario_callback

        self.ahora=datetime.now()
        self.ids.fecha.text=self.ahora.strftime("%d/%m/%y")
        Clock.schedule_interval(self.actualizar_hora, 1)
        Window.bind(on_key_down=self._tecla_presionada)

        # NUEVO: Sistema de detección scanner vs manual
        self.scanner_buffer = ""
        self.last_key_time = 0
        self.scanner_timeout = None
        self.scanner_detected = False
        
        # NUEVO: Configurar el foco automático para el scanner
        Clock.schedule_once(self._enfocar_campo_scanner, 0.5)
        
    def _enfocar_campo_scanner(self, dt):
        """Enfoca automáticamente el campo de búsqueda por código"""
        self.ids.buscar_codigo.focus = True
        
    def agregar_producto_codigo(self, codigo):
        codigo = codigo.strip()

        if not codigo:
            return

        connection = QueriesSQLServer.create_connection()

        query = "SELECT * FROM productos WHERE codigo = ?"
        inventario_sql = QueriesSQLServer.execute_read_query(connection, query, (codigo,))
        if not inventario_sql:
            self.ids.notificacion_falla.text = f"Producto con código '{codigo}' no encontrado"
            logging.warning(f"Producto no encontrado: {codigo}")
            self.ids.buscar_codigo.text = ""
            self.ids.buscar_codigo.focus = True
            return

        producto = inventario_sql[0]
        if producto[3] <= 0:
            self.ids.notificacion_falla.text = f"El producto '{producto[1]}' está agotado."
            logging.warning(f"Producto agotado: {producto[1]}")
            self.ids.buscar_codigo.text = ""
            self.ids.buscar_codigo.focus = True
            return

        articulo = {
            'codigo': producto[0],
            'nombre': producto[1],
            'precio': float(producto[2]),
            'cantidad_carrito': 1,
            'cantidad_inventario': producto[3],
            'precio_total': float(producto[2])
        }

        self.agregar_producto(articulo)
        self.ids.notificacion_falla.text = ""
        self.ids.buscar_codigo.text = ""
        self.ids.buscar_codigo.focus = True

    def buscar_codigo_manual(self, instance):
        codigo = instance.text.strip()
        
        if not codigo:
            return
        
        # Verificar que sea solo numérico
        if not codigo.isdigit():
            self.ids.notificacion_falla.text = "Código inválido: solo números permitidos"
            logging.warning(f"Código inválido (manual): {codigo}")
            instance.text = ""
            Clock.schedule_once(lambda dt: setattr(instance, 'focus', True), 0.1)
            return
        
        # Procesar código
        self.agregar_producto_codigo(codigo)
        instance.text = ""
        Clock.schedule_once(lambda dt: setattr(instance, 'focus', True), 0.1)

        self.agregar_producto_codigo(codigo)
        instance.text = ""                

    def agregar_producto_nombre(self, nombre):
        self.ids.buscar_nombre.text=''
        popup=ProductoPorNombrePopup(nombre, self.agregar_producto, ventana_ventas=self)
        popup.mostrar_articulos()

    def filtrar_nombre(self, instance, value):
        limpio = "".join(c for c in value if c.isalpha() or c.isspace())
        if value != limpio:
            instance.text = limpio

    def agregar_producto(self, articulo):
        precio_float = float(articulo['precio'])  
        # self.total+=articulo['precio']
        self.total += precio_float  # Ahora ambos son float
        self.ids.sub_total.text=format_currency(self.total)
        articulo['precio'] = precio_float
        self.ids.rvs.agregar_articulo(articulo)

    def eliminar_producto(self):
        menos_precio=self.ids.rvs.eliminar_articulo()
        self.total-=menos_precio
        self.ids.sub_total.text=format_currency(self.total)

    def modificar_producto(self, cambio=True, nuevo_total=None):
       if cambio:
            self.ids.rvs.modificar_articulo() 
       else:
           self.total=nuevo_total
           self.ids.sub_total.text=format_currency(self.total)

    def actualizar_hora(self, *args):
        self.ahora=self.ahora+timedelta(seconds=1)
        self.ids.hora.text=self.ahora.strftime("%H:%M:%S")

    def pagar(self):
        if self.ids.rvs.data:
            # Primero mostrar confirmación del pago con listado y total
            confirmar_popup = ConfirmarPagoPopup(self, self._abrir_popup_pago)
            confirmar_popup.open()
        else:
            self.ids.notificacion_falla.text='No hay nada que pagar'

    def _abrir_popup_pago(self):
        popup_pago = PagarPopup(self.total, self._abrir_tipo_factura)
        popup_pago.open()

    def _abrir_tipo_factura(self, recibido, cambio):
        self.value_paid = recibido
        self.change = cambio

        popup_tipo = TipoFacturaPopup(self.pagado, self)
        popup_tipo.open()

    # def nueva_venta_popup(self):
    #     # Poner esta ventana en segundo plano e iniciar una nueva en un Popup
    #     try:
    #         self.disabled = True
    #         self.opacity = 0
    #     except Exception:
    #         pass
    #     popup = NuevaVentaPopup(self, self.actualizar_inventario)
    #     popup.open()

    def pagado(self):
        username = CURRENT_USER.get("username")
        nombre = CURRENT_USER.get("nombre", "")

        if not username:
            logging.error("ERROR: Usuario no autenticado (CURRENT_USER vacío)")
            self.ids.notificacion_falla.text = "Error: Usuario no identificado"
            return

        try:
            self.ids.notificacion_exito.text = 'Pago realizado con éxito'
            self.ids.notificacion_falla.text = ''
            self.ids.total.text = format_currency(self.total)
            
            # Deshabilitar controles temporalmente
            self.ids.buscar_codigo.disabled = True
            self.ids.buscar_nombre.disabled = True
            self.ids.borrar_articulo.disabled = True
            self.ids.cambiar_cantidad.disabled = True
            self.ids.pagar.disabled = True
            
            # Validaciones iniciales críticas
            if not self.ids.rvs.data:
                logging.error("ERROR CRÍTICO: No hay items en el carrito para facturar")
                self.ids.notificacion_falla.text = 'Error: Carrito vacío'
                self._restaurar_controles()
                return
            
            # Conexión a base de datos
            connection = QueriesSQLServer.create_connection()
            if not connection:
                logging.error("ERROR: No se pudo conectar a la base de datos")
                self.ids.notificacion_falla.text = 'Error de conexión a BD'
                self._restaurar_controles()
                return
            
            # Preparar datos para la venta (antes de insertar)
            value_paid = getattr(self, "value_paid", self.total)
            change = getattr(self, "change", 0)
            
            items_factura = []
            actualizar_admin = []
            
            for producto in self.ids.rvs.data:
                items_factura.append({
                    "Id_Product": str(producto['codigo']),
                    "quantity": producto['cantidad_carrito'],
                    "description": producto['nombre'],
                    "Total": float(producto['precio_total']),
                    "taxes": [1],
                    "include": True
                })
            
            venta_data = {
                "username": username, 
                "total": self.total,
                "items": items_factura, 
                "Tax": [
                    {
                        "Id_Tax": 1,
                        "TaxValue": 19.0,
                        "TaxName": "IVA"
                    }
                ],
                "PaymentMethod": 0,  # Efectivo
                "PaymentDetails": {
                    "valuePaid": value_paid,
                    "change": change,
                    "notDispense": 0
                },
                "Details": {
                    "Vendedor": nombre,
                    "Terminal": f"POS#{self.terminal_id}"
                }
            }
            
            logging.info(f"Venta data preparada con {len(items_factura)} items")
            venta_query = """INSERT INTO ventas (total, fecha, username) VALUES (?, ?, ?)"""
            venta_tuple = (self.total, datetime.now(), username)
            
            venta_id = QueriesSQLServer.execute_query(connection, venta_query, venta_tuple)
            if not venta_id:
                raise Exception("No se pudo obtener el ID de la venta")
            
            logging.info(f"Venta insertada con ID: {venta_id}")
            
            for producto in self.ids.rvs.data:
                nueva_cantidad = max(0, producto['cantidad_inventario'] - producto['cantidad_carrito'])
                update_query = """
                UPDATE productos 
                SET cantidad = ?
                WHERE codigo = ?
                """
                update_tuple = (nueva_cantidad, producto['codigo'])
                QueriesSQLServer.execute_query(connection, update_query, update_tuple)
                
                # Insertar detalle de venta
                detalle_query = """
                INSERT INTO ventas_detalle (id_venta, precio, producto, cantidad)
                VALUES (?, ?, ?, ?)
                """
                detalle_tuple = (venta_id, producto['precio'], producto['codigo'], producto['cantidad_carrito'])
                QueriesSQLServer.execute_query(connection, detalle_query, detalle_tuple)
                
                # Guardar para actualización de UI
                actualizar_admin.append({
                    'codigo': producto['codigo'],
                    'cantidad': nueva_cantidad
                })
            
            # Generar e imprimir factura
            factura_result = None
            try:
                from Src.Views.Settings import Herramientas
                factura_result = Herramientas(self.user_data).generar_e_imprimir_factura(venta_data, imprimir=self.imprimir_factura)

                if not self.imprimir_factura:
                    mostrar_notificacion_popup(
                        "Venta registrada correctamente",
                        exito=True,
                        duracion=2
                    )

            except Exception as e:
                msg = str(e).lower()
                factura_result = None
                if hasattr(e, 'factura_generada'):
                    factura_result = e.factura_generada
                    logging.info(f"Factura recuperada de la excepción: {factura_result.get('IdInvoice')}")
                
                mostrar_notificacion_popup(
                    "La venta fue registrada correctamente",
                    exito=True,
                    duracion=2
                )
                if (
                    "openprinter" in msg
                    or "1801" in msg
                    or "nombre de la impresora" in msg
                ):
                    mostrar_notificacion_popup(
                        "Impresora no configurada\nConfigure una impresora válida en Settings",
                        exito=False,
                        duracion=4
                    )
                elif "impresora" in msg or "printer" in msg:
                    mostrar_notificacion_popup(
                        "Impresora desconectada\nVerifique la conexión física",
                        exito=False,
                        duracion=3
                    )
                else:
                    mostrar_notificacion_popup(
                        "Error inesperado al imprimir",
                        exito=False,
                        duracion=4
                    )

            if factura_result and isinstance(factura_result, dict) and "warning" not in factura_result:
                cursor = connection.cursor()
                cursor.execute("""
                    UPDATE ventas SET
                        id_factura = ?,
                        id_turno = ?,
                        id_dispositivo = ?,
                        prefijo_resolucion = ?,
                        num_resolucion = ?,
                        consecutivo = ?,
                        subtotal = ?,
                        impuestos = ?,
                        metodo_pago = ?,
                        detalles_pago = ?,
                        receipt_data = ?,
                        json_factura = ?
                    WHERE id = ?
                """, (
                    f"{factura_result.get('Prefix')}-{factura_result.get('IdInvoice')}",
                    factura_result.get("IdShift"),
                    factura_result.get("IdDevice"),
                    factura_result.get("Prefix"),
                    factura_result.get("numResolution"),
                    factura_result.get("IdInvoice"),
                    factura_result.get("Subtotal"),
                    factura_result.get("TotalTaxes"),
                    venta_data["PaymentMethod"],
                    json.dumps(venta_data["PaymentDetails"]),
                    factura_result.get("Receipt", "")[:4000],
                    json.dumps(factura_result, ensure_ascii=False),
                    venta_id
                ))
                connection.commit()
                
                if factura_result.get("print_status") == "PENDING":
                    pass
                elif factura_result.get("print_status") == "NOT_PRINTED":
                    pass
                elif "warning" not in factura_result:
                    mostrar_notificacion_popup(
                        "Factura impresa correctamente",
                        exito=True
                    )
            elif factura_result and isinstance(factura_result, dict) and "warning" in factura_result:
                pass
            else:
                logging.warning("Factura generada pero no se obtuvo resultado válido")
                if isinstance(factura_result, str) and "error" in factura_result.lower():
                    mostrar_notificacion_popup(
                        "Factura generada pero con advertencias",
                        exito=False,
                        duracion=3
                    )
        
            if callable(self.actualizar_inventario):
                try:
                    self.actualizar_inventario(actualizar_admin)
                except Exception as e:
                    logging.warning(f"Error actualizando UI de inventario: {e}")
                
        except Exception as e:
            logging.error(f"ERROR en proceso de pago: {str(e)}")
            logging.error(traceback.format_exc())
            
            # Mostrar error apropiado al usuario
            error_msg = str(e)
            if "items" in error_msg.lower() or "factura" in error_msg.lower():
                self.ids.notificacion_falla.text = f'Error al generar factura: {error_msg[:50]}...'
                mostrar_notificacion_popup(
                    "Error al generar factura\nRevise los datos de la venta",
                    exito=False,
                    duracion=4
                )
            else:
                self.ids.notificacion_falla.text = f'Error en pago: {error_msg[:50]}...'
                mostrar_notificacion_popup(
                    f"Error procesando pago: {error_msg[:30]}...",
                    exito=False,
                    duracion=4
                )
            
            try:
                if 'connection' in locals() and connection:
                    connection.rollback()
            except:
                pass
    
    def nueva_compra(self, desde_popup=False):
        if desde_popup:
            self.ids.rvs.data=[]
            self.total=0.0
            self.ids.sub_total.text= '0.00'
            self.ids.total.text= '0.00'
            self.ids.notificacion_exito.text=''
            self.ids.notificacion_falla.text=''
            self.ids.buscar_codigo.disabled=False
            self.ids.buscar_nombre.disabled=False
            self.ids.borrar_articulo.disabled = False
            self.ids.cambiar_cantidad.disabled=False
            self.ids.pagar.disabled=False        
            self.ids.rvs.refresh_from_data()
        elif len(self.ids.rvs.data):
            popup=NuevaCompraPopup(self.nueva_compra)
            popup.open()


    def admin(self):
        self.parent.parent.current='scrn_admin'
        #connection = QueriesSQLServer.create_connection(server, database, username, password)
        #if connection:
            #logging.info(f"Conexión exitosa a la base de datos '{database}'")

        #select_products = "SELECT * FROM productos"
        #productos = QueriesSQLServer.execute_read_query(connection, select_products)
        #for producto in productos:
        #    logging.info(producto)

        logging.info("admin presionado")

    def signout(self):
        if self.ids.rvs.data:
            self.ids.notificacion_falla.text='Compra iniciada'
        else:
            self.parent.parent.current='scrn_signin'
            logging.info("Signout presionado")

    def usuario_loggin(self, user_data):
        # self.ids.bienvenido_log.text=''+user_data['nombre']
        self.user_data=user_data
        rol = "Admin" if user_data['tipo'] == 'admin' else "Empleado"
        self._actualizar_encabezado(user_data)
        if user_data['tipo']=='empleado':
            self.ids.admin_boton.disabled=True
            self.ids.admin_boton.text='Admin'
            self.ids.admin_boton.opacity=1
        else:
            self.ids.admin_boton.disabled=False
            #self.ids.admin_boton.text='Admin'
            #self.ids.admin_boton.opacity=1

    def _actualizar_encabezado(self, user_data):
        nombre = user_data.get("nombre", "Usuario")
        rol = "Admin" if user_data.get('tipo') == 'admin' else "Empleado"
        self.ids.encabezado_terminal.text = f"Terminal POS #{self.terminal_id} — Usuario: {nombre} ({rol})"


    def _tecla_presionada(self, window, key, scancode, codepoint, modifiers):
        if key == 293:  # F12
            logging.info(f"F12 -> Abriendo SubTerminal POS {key}")

            # Nuevo terminal basado en este mismo número
            nuevo_id = self.terminal_id + 1

            args = json.dumps({"terminal_id": nuevo_id, "user": self.user_data})

            # Detectar si ejecuta como EXE o script
            if getattr(sys, 'frozen', False):
                exe_path = sys.executable
                cmd = [exe_path, "--subterminal", args]
            else:
                main_path = os.path.abspath("main.py")
                cmd = [sys.executable, main_path, "--subterminal", args]

            try:
                subprocess.Popen(cmd)
                logging.info(f"SubTerminal #{nuevo_id} iniciada correctamente")
            except Exception as e:
                logging.error(f"Error abriendo subterminal: {e}")

            return True

        if 'repeat' in modifiers:
            return True

        # NUEVO: Sistema inteligente de detección scanner
        current_time = Clock.get_time()
        time_since_last_key = current_time - self.last_key_time
        
        # Detectar si es dígito (scanner) o tecla especial
        if codepoint and codepoint.isdigit():
            # Scanner o entrada manual rápida
            self.scanner_buffer += codepoint
            self.last_key_time = current_time
            
            # Cancelar timeout anterior
            if self.scanner_timeout:
                self.scanner_timeout.cancel()
            
            # Programar timeout para procesar código completo
            self.scanner_timeout = Clock.schedule_once(self._procesar_scanner_completo, 0.15)
            return True
        
        # Detectar Enter (final del scanner)
        elif key == 13 or key == 271:  # Enter o numpad enter
            if self.scanner_buffer and time_since_last_key < 0.2:  # Scanner rápido
                self._procesar_scanner_final()
                return True
            else:  # Enter manual - solo limpiar buffer
                self.scanner_buffer = ""
                if self.scanner_timeout:
                    self.scanner_timeout.cancel()
                return False
        
        # Para otras teclas, limpiar buffer (entrada manual)
        else:
            self.scanner_buffer = ""
            if self.scanner_timeout:
                self.scanner_timeout.cancel()
        
        self.last_key_time = current_time
        return False
        

    def _procesar_entrada_scanner(self, caracter):
        """Procesa la entrada del scanner de códigos de barras"""
        # Cancelar timeout anterior si existe
        if self.scanner_timeout:
            self.scanner_timeout.cancel()
        
        # Agregar carácter al buffer
        self.scanner_buffer += caracter
        self.scanner_timeout = Clock.schedule_once(self._finalizar_lectura_scanner, 0.1)
    
    def _finalizar_lectura_scanner(self, dt):
        """Procesa el código completo leído por el scanner"""
        if self.scanner_buffer:
            # El scanner generalmente agrega un Enter al final
            codigo = self.scanner_buffer.strip()
            if codigo:
                logging.info(f"Código leído por scanner: {codigo}")
                # Procesar el código
                self.ids.buscar_codigo.text = codigo
                self.agregar_producto_codigo(codigo)
            
            # Limpiar buffer
            self.scanner_buffer = ""

    def _procesar_scanner_completo(self, dt):
        """Procesa el código del scanner después del timeout"""
        if len(self.scanner_buffer) >= 8:  # Códigos de barras típicos son largos
            self._procesar_scanner_final()
        else:
            # Código muy corto, probablemente entrada manual
            self.scanner_buffer = ""

    def _procesar_scanner_final(self):
        """Procesa el código final del scanner"""
        if self.scanner_buffer:
            codigo = self.scanner_buffer.strip()
            logging.info(f"[SCANNER] Código procesado: {codigo}")
            
            # Verificar que sea solo numérico (código de barras)
            if codigo.isdigit():
                # Enfocar campo y procesar código
                self.ids.buscar_codigo.focus = True
                Clock.schedule_once(lambda dt: self.agregar_producto_codigo(codigo), 0.05)
            
            # Limpiar buffer
            self.scanner_buffer = ""
        
        if self.scanner_timeout:
            self.scanner_timeout.cancel()

class VentasApp(App):
    def build(self):
        return VentasWindow()
    
if __name__ == '__main__':
    VentasApp().run()########v14