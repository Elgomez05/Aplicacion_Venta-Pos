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

Builder.load_file('Src/Views/ventas_view.kv')

from datetime import datetime, timedelta

from Src.Views.sqlqueries import QueriesSQLServer

server = 'DESKTOP-QGCQ59D\SQLEXPRESS'
database = 'PuntoventaDB'
username = 'Elgomez05'
password = '123456'

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
        self.ids['_precio_por_articulo'].text = str("{:.2f}".format(data['precio']))
        self.ids['_precio'].text = str("{:.2f}".format(data['precio_total']))
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
        self.ids['_precio'].text = str("{:.2f}".format(data['precio']))
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
        connection = QueriesSQLServer.create_connection(server, database, username, password)
        if connection:
            print(f"Conexión exitosa a la base de datos '{database}'")

        query = "SELECT * FROM productos"
        inventario_sql = QueriesSQLServer.execute_read_query(connection, query)
        self.open()
        for nombre in inventario_sql:
            if nombre[1].lower().find(self.input_nombre)>=0:
                if nombre[3] <= 0:  # Verificar si el producto está agotado
                # Mostrar alerta
                    self.ventana_ventas.ids.notificacion_falla.text = f"El producto '{nombre[1]}' está agotado."
                    continue
                producto={'codigo': nombre[0], 'nombre': nombre[1], 'precio': nombre[2], 'cantidad': nombre[3]}
                self.ids.rvs.agregar_articulo(producto)

    def seleccionar_articulo(self):
        indice=self.ids.rvs.articulo_seleccionado()
        if indice>=0:
            _articulo=self.ids.rvs.data[indice]
            articulo={}
            articulo['codigo']=_articulo['codigo']
            articulo['nombre']=_articulo['nombre']
            articulo['precio']=_articulo['precio']
            articulo['cantidad_carrito']=1
            articulo['cantidad_inventario']=_articulo['cantidad']
            articulo['precio_total']=_articulo['precio']
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
        self.ids.total.text="{:.2f}".format(self.total)
        self.ids.boton_pagar.bind(on_release=self.dismiss)
        
    def mostrar_cambio(self):
        recibido= self.ids.recibido.text
        try:
            cambio=float(recibido)-float(self.total)
            if cambio>=0:
                self.ids.cambio.text="{:.2f}".format(cambio)
                self.ids.boton_pagar.disabled=False
            else:
                self.ids.cambio.text="Pago menor a cantidad a pagar"
        except:
            self.ids.cambio.text="Pago no valido"

    def finalizar_cobro(self):
        # Al pulsar terminar pago, delegar al callback superior (p. ej. abrir popup de factura)
        if callable(self.on_pago_completo):
            self.on_pago_completo()

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
            print(f"No se pudo cargar el resumen del carrito: {e}")
        # Mostrar total
        self.ids.total_confirmacion.text = "{:.2f}".format(self.ventana_ventas.total)

    def confirmar(self):
        if callable(self.confirmar_callback):
            self.confirmar_callback()
        self.dismiss()

class TipoFacturaPopup(Popup):
    def __init__(self, confirmar_pago_callback, **kwargs):
        super(TipoFacturaPopup, self).__init__(**kwargs)
        # Este callback debe ejecutar el cierre del pago (pagado)
        self.confirmar_pago = confirmar_pago_callback

    def imprimir_electronica(self):
        # Aquí podría integrarse la impresión electrónica
        if callable(self.confirmar_pago):
            self.confirmar_pago()
        self.dismiss()

    def imprimir_venta(self):
        # Aquí podría integrarse la impresión de venta
        if callable(self.confirmar_pago):
            self.confirmar_pago()
        self.dismiss()

class NuevaVentaPopup(Popup):
    def __init__(self, ventana_anterior, actualizar_inventario_callback, **kwargs):
        super(NuevaVentaPopup, self).__init__(**kwargs)
        self.ventana_anterior = ventana_anterior
        # Crear una nueva ventana de ventas dentro del popup
        try:
            nueva = VentasWindow(actualizar_inventario_callback)
            # Propagar usuario logueado si existe
            if getattr(self.ventana_anterior, 'user_data', None):
                nueva.usuario_loggin(self.ventana_anterior.user_data)
            # Insertar en el contenedor definido en KV (id: contenido)
            self.ids.contenido.add_widget(nueva)
        except Exception as e:
            print(f"Error creando nueva ventana de venta: {e}")
        # Al cerrar, restaurar visibilidad/interacción de la ventana anterior
        self.bind(on_dismiss=self._restaurar_anterior)

    def _restaurar_anterior(self, *_):
        try:
            self.ventana_anterior.disabled = False
            self.ventana_anterior.opacity = 1
        except Exception:
            pass

class VentasWindow(BoxLayout):
    user_data=None
    def __init__(self, actualizar_inventario_callback, **kwargs):
        super().__init__(**kwargs)
        self.total=0.0
        self.ids.rvs.modificar_producto=self.modificar_producto
        self.actualizar_inventario=actualizar_inventario_callback

        self.ahora=datetime.now()
        self.ids.fecha.text=self.ahora.strftime("%d/%m/%y")
        Clock.schedule_interval(self.actualizar_hora, 1)
        
    def agregar_producto_codigo(self, codigo):
        connection = QueriesSQLServer.create_connection(server, database, username, password)
        if connection:
            print(f"Conexión exitosa a la base de datos '{database}'")

        query = "SELECT * FROM productos"
        inventario_sql = QueriesSQLServer.execute_read_query(connection, query)
        for producto in inventario_sql:
            if codigo==producto[0]:
                if producto[3] <= 0:  # Verificar si la cantidad es 0 o menor
                # Mostrar alerta de producto agotado
                    self.ids.notificacion_falla.text = f"El producto '{producto[1]}' está agotado."
                    return
                
                articulo={}
                articulo['codigo']=producto[0]
                articulo['nombre']=producto[1]
                articulo['precio']=producto[2]
                articulo['cantidad_carrito']=1
                articulo['cantidad_inventario']=producto[3]
                articulo['precio_total']=producto[2]
                self.agregar_producto(articulo)
                self.ids.buscar_codigo.text=''
                break

    def agregar_producto_nombre(self, nombre):
        self.ids.buscar_nombre.text=''
        popup=ProductoPorNombrePopup(nombre, self.agregar_producto, ventana_ventas=self)
        popup.mostrar_articulos()

    def agregar_producto(self, articulo):  
        self.total+=articulo['precio']
        self.ids.sub_total.text='$ '+ "{:.2f}".format(self.total)
        self.ids.rvs.agregar_articulo(articulo)

    def eliminar_producto(self):
        menos_precio=self.ids.rvs.eliminar_articulo()
        self.total-=menos_precio
        self.ids.sub_total.text='$ '+ "{:.2f}".format(self.total)

    def modificar_producto(self, cambio=True, nuevo_total=None):
       if cambio:
            self.ids.rvs.modificar_articulo() 
       else:
           self.total=nuevo_total
           self.ids.sub_total.text='$ '+ "{:.2f}".format(self.total)

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

    def _abrir_tipo_factura(self):
        popup_tipo = TipoFacturaPopup(self.pagado)
        popup_tipo.open()

    def nueva_venta_popup(self):
        # Poner esta ventana en segundo plano e iniciar una nueva en un Popup
        try:
            self.disabled = True
            self.opacity = 0
        except Exception:
            pass
        popup = NuevaVentaPopup(self, self.actualizar_inventario)
        popup.open()

    def pagado(self):
        self.ids.notificacion_exito.text='Pago realizado con exito'
        self.ids.notificacion_falla.text=''
        self.ids.total.text="{:.2f}".format(self.total)
        self.ids.buscar_codigo.disabled=True
        self.ids.buscar_nombre.disabled=True
        self.ids.borrar_articulo.disabled=True
        self.ids.cambiar_cantidad.disabled=True
        self.ids.pagar.disabled=True
        connection = QueriesSQLServer.create_connection(server, database, username, password)
        if connection:
            print(f"Conexión exitosa a la base de datos '{database}'")
        actualizar="""
        UPDATE
            productos
        SET
            cantidad=?
        WHERE
            codigo=?

        """
        actualizar_admin=[]
        
        venta = """ 
            INSERT INTO ventas (total, fecha, username) 
            VALUES (?, ?, ?)
        """
        venta_tuple = (self.total, self.ahora, self.user_data['username'])

        try:
            print("Datos insertados correctamente en:", venta_tuple)
            venta_id = QueriesSQLServer.execute_query(connection, venta, venta_tuple)
            if venta_id is None:
                raise Exception("No se pudo obtener el ID de la venta. Verifica la inserción.")
            print("ID insertado en la tabla ventas:", venta_id)
        except Exception as e:
            print(f"Error al insertar en la tabla ventas: {e}")

        ventas_detalle = """
        INSERT INTO ventas_detalle (id_venta, precio, producto, cantidad)
        VALUES
            (?, ?, ?, ?)
        """
        for producto in self.ids.rvs.data:
            nueva_cantidad=0
            if producto['cantidad_inventario']-producto['cantidad_carrito']>0:
                nueva_cantidad=producto['cantidad_inventario']-producto['cantidad_carrito']
            producto_tuple=(nueva_cantidad, producto['codigo'])
            ventas_detalle_tuple = (venta_id, producto['precio'], producto['codigo'], producto['cantidad_carrito'])
            print("Datos insertados correctamente en:", ventas_detalle_tuple)
            actualizar_admin.append({'codigo': producto['codigo'], 'cantidad': nueva_cantidad})
            QueriesSQLServer.execute_query(connection, ventas_detalle, ventas_detalle_tuple)
            QueriesSQLServer.execute_query(connection, actualizar, producto_tuple)
              
            self.actualizar_inventario(actualizar_admin)
        
            


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
            #print(f"Conexión exitosa a la base de datos '{database}'")

        #select_products = "SELECT * FROM productos"
        #productos = QueriesSQLServer.execute_read_query(connection, select_products)
        #for producto in productos:
        #    print(producto)

        print("admin presionado")

    def signout(self):
        if self.ids.rvs.data:
            self.ids.notificacion_falla.text='Compra iniciada'
        else:
            self.parent.parent.current='scrn_signin'
            print("Signout presionado")

    def usuario_loggin(self, user_data):
        self.ids.bienvenido_log.text=''+user_data['nombre']
        self.user_data=user_data
        if user_data['tipo']=='empleado':
            self.ids.admin_boton.disabled=True
            self.ids.admin_boton.text='Admin'
            self.ids.admin_boton.opacity=1
        else:
            self.ids.admin_boton.disabled=False
            #self.ids.admin_boton.text='Admin'
            #self.ids.admin_boton.opacity=1
            
    



class VentasApp(App):
    def build(self):
        return VentasWindow()
    
if __name__ == '__main__':
    VentasApp().run()
        
    
