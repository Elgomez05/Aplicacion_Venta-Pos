# Src/Views/Settings.py
from kivy.app import App
import logging
import json
import os
from kivy.uix.popup import Popup
from kivy.uix.label import Label
from kivy.clock import Clock
from datetime import datetime

from Src.Config.config_loader import config, load_config
from Src.Services.service_invoicing_v2 import Invoicing 
from Src.Devices.device_desktop_printer import Printer
from Src.Services.Service_mqtt import DummyMQTT

CONFIG_PATH = "C:/ProgramData/PuntoVenta/Setting/settings.json"

def mostrar_notificacion_popup(mensaje, exito=True, duracion=2):
    """
    Función global para mostrar notificaciones popup desde cualquier módulo.
    
    Args:
        mensaje (str): Texto a mostrar
        exito (bool): True para verde (éxito), False para rojo (error)
        duracion (int): Segundos que permanece visible
    """
    color = (0, 0.7, 0, 1) if exito else (1, 0, 0, 1)
    
    popup = Popup(
        title="Notificación",
        content=Label(text=mensaje, color=color),
        size_hint=(0.6, 0.3),
        auto_dismiss=True
    )
    popup.open()
    Clock.schedule_once(lambda dt: popup.dismiss(), duracion)
    return popup

class Herramientas:
    def __init__(self, user_data=None):
        self.user_data = user_data or {}
        
    def _on_prueba_impresion(self, e=None, ventana=None):
        """Prueba la impresora con configuración desde settings.json"""
        logging.info("****************************************************************************")
        logging.info("*************** Realizando prueba de Impresora Configurada *****************")
        logging.info("****************************************************************************")
        logging.warning("Imprimiendo prueba...")
        
        # def mostrar_notificacion_popup(mensaje, exito=True):
        #     color = (0, 0.7, 0, 1) if exito else (1, 0, 0, 1)
            
        #     popup = Popup(
        #         title="Notificación Impresora",
        #         content=Label(text=mensaje, color=color),
        #         size_hint=(0.6, 0.3),
        #         auto_dismiss=True
        #     )
        #     popup.open()
        #     Clock.schedule_once(lambda dt: popup.dismiss(), 3)
        
        try:
            # Obtener configuración actual
            cfg = config.get("printer") or {}
            printer_name = cfg.get("name", "")
            use_default = cfg.get("use_default", True)
            paper_width = cfg.get("paper_width", 58)
            logging.info(f"Configuración: {printer_name}, Ancho: {paper_width}")
                
            printer = Printer()
            
            # Datos de prueba
            print_data = [
                {
                    "type": "text",
                    "data": "=" * paper_width,
                    "align": "center"
                },
                {
                    "type": "text",
                    "data": "PRUEBA DE IMPRESORA",
                    "align": "center",
                    "bold": True
                },
                {
                    "type": "text",
                    "data": "=" * paper_width,
                    "align": "center"
                },
                {
                    "type": "text",
                    "data": f"Elaborado por: Pepe Inteligent System S.A.S.",
                    "align": "center"
                },
                {
                    "type": "text",
                    "data": f"Nombre: {printer_name if printer_name else 'Por defecto'}",
                    "align": "left"
                },
                {
                    "type": "text",
                    "data": f"Ancho papel: {paper_width} caracteres",
                    "align": "left"
                },
                {
                    "type": "text",
                    "data": "=" * paper_width,
                    "align": "center"
                },
                {
                    "type": "qr",
                    "data": "https://www.pepe.com.co",
                    "size": 8 
                },
                {
                    "type": "text",
                    "data": "Escanea para verificar",
                    "align": "center"
                },
                {
                    "type": "text",
                    "data": "=" * paper_width,
                    "align": "center"
                },
                {
                    "type": "text",
                    "data": "Prueba completada",
                    "align": "center",
                    "bold": True
                },
                {
                    "type": "cut",
                    "data": ""
                }
            ]
            
            success = printer.print(print_data, "Prueba_Configuracion")
            if success:
                nombre_mostrar = printer_name if printer_name else "Por defecto"
                mostrar_notificacion_popup(f"Prueba de impresión exitosa\nImpresora: {nombre_mostrar}", True)
                logging.info("Prueba de impresión exitosa")
                return True
            else:
                mostrar_notificacion_popup("Error en prueba de impresión\nVerifique la conexión", False)
                logging.error("Error en prueba de impresión")
                return False
                
        except Exception as e:
            error_msg = f"Error: {str(e)}"
            
            # Detectar si es error de impresora no configurada
            if "OpenPrinter" in str(e) or "1801" in str(e) or "nombre de la impresora" in str(e).lower():
                error_msg = "Impresora no configurada\nConfigure una impresora válida en Settings"
            
            mostrar_notificacion_popup(error_msg, False)
            logging.error(f"Error en prueba de impresión: {e}")
            return False

    def generar_e_imprimir_factura(self, venta_data, imprimir=True):
        config_manager = config
        
        required_fields = ["Tax", "items", "PaymentMethod", "PaymentDetails"]
        for field in required_fields:
            if field not in venta_data:
                if field == "Tax":
                    venta_data["Tax"] = [{
                        "Id_Tax": 1,
                        "TaxValue": 19,
                        "TaxName": "IVA"
                    }]
                elif field == "items" and "Items" in venta_data:
                    # Compatibilidad con mayúscula/minúscula
                    venta_data["items"] = venta_data.pop("Items")
                elif field == "items":
                    venta_data["items"] = []
                elif field == "PaymentMethod":
                    venta_data["PaymentMethod"] = 0
                elif field == "PaymentDetails":
                    venta_data["PaymentDetails"] = {
                        "valuePaid": venta_data.get("total", 0),
                        "change": 0,
                        "notDispense": 0
                    }
        
        # Asegurar que cada item tenga campos requeridos
        for item in venta_data.get("items", []):
            if "taxes" not in item:
                item["taxes"] = [1]  # Referencia al primer impuesto
            if "include" not in item:
                item["include"] = True  # IVA incluido por defecto
        
        invoicer = Invoicing()
        invoicer._mqtt = DummyMQTT()
        
        # Preparar dataConfig con template_invoice REAL
        dataConfig = {
            "Currency": config_manager.get("invoicing", "currency", "COP"),
            "Currency_symbol": config_manager.get("invoicing", "currency_symbol", "$"),
            "adjustment": config_manager.get("invoicing", "adjustment", 50),
            "template_invoice": {
                "enterprise": config_manager.get("invoicing", "enterprise", ""),
                "nit": config_manager.get("invoicing", "nit", ""),
                "address": config_manager.get("invoicing", "address", ""),
                "cellphone": config_manager.get("invoicing", "cellphone", ""),
                "footer": config_manager.get("invoicing", "footer", "")
            }
        }

        invoicer.start(
            dataPath=config_manager.get("invoicing", "data_path"),
            dataConfig=dataConfig,
            idDevice=1,
            saveBilling=config_manager.get("invoicing", "save_billing")
        )

        factura = invoicer.invoice(
            dataInvoice=venta_data,
            useIdInvoice=True,
            printer="dict"
        )

        if not factura or "Receipt" not in factura:
            raise Exception("No se pudo generar la factura")

        # --- IMPRESIÓN ---
        if imprimir:
            receipt = factura.get("Receipt")
            if receipt is None:
                raise Exception("Factura generada sin Receipt")

            printer = Printer()
            if not isinstance(receipt, str):
                receipt = str(receipt)
                logging.info("FACTURA RECIBO:\n%s", receipt)

            printer_data = [{
                "type": "text",
                "data": receipt,  
                "align": "left"
                }
            ]

            printer_data.append({
                "type": "cut",
                "data": ""
                }
            )

            success = False
            try:
                success = printer.print(printer_data, "Factura de Venta")

            except Exception as e:
                logging.error(f"Error de impresora: {e}")

                factura["print_status"] = "PENDING"
                factura["print_error"] = str(e)
                e.factura_generada = factura # ← ¡NUEVA LÍNEA!
                raise

            if not success:
                logging.warning("Impresora desconectada — factura generada sin impresión")
                factura["print_status"] = "PENDING"
                factura["print_error"] = "IMPRESORA_DESCONECTADA"
                mostrar_notificacion_popup(
                    "Impresora desconectada\nNo se pudo generar factura",
                    exito=False,
                    duracion=4
                )

            for line in receipt.splitlines():
                logging.info("[Texto a imprimir] %s", line)

        else:
            # Si no se imprime, marcar como no impresa
            factura["print_status"] = "NOT_PRINTED"
            factura["print_error"] = "SIN_IMPRESION_SOLICITADA"

        return factura

    def _turno_path(self):
        return "C:/ProgramData/PuntoVenta/shiftControl/controlShift.json"

    def verificar_turno(self):
        path = self._turno_path()
        if not os.path.exists(path):
            return "CERRADO"

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                status_num = data.get("Status", 1)
                if status_num == 0:
                    return "ABIERTO"
                else:
                    return "CERRADO"

        except Exception as e:
            logging.error(f"Error leyendo estado del turno: {e}")
            return "CERRADO"

    def abrir_turno(self, user=None):
        user = user or self.user_data
        path = self._turno_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        
        # Crear estructura compatible con el facturador
        data = {
            "Id_Shift": 1,  # ID inicial
            "Id_Device": 1,
            "InitialDate": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "FinalDate": "",
            "Status": 0,  # 0 = abierto
            "InitInvoice": 0,
            "FinishInvoice": 0,
            "Id_PeopleOpening": 0,
            "InitialCash": 0,
            "InternalControl": 0,
            "Diference": 0,
            "Id_PeopleClosed": 0,
            "FinalCash": 0,
            "MethodsPay": {},
            "TotalInvoices": 0,
            "TotalTaxes": 0,
            "TotalwhitTaxes": 0,
            "TotalwhitOutTaxes": 0,
            "FailReturn": 0,
            "List_FailReturn": [],
            "Emptied": 0,
            "List_Emptied": [],
            "Withdrawal": 0,
            "List_Withdrawal": [],
            "Recharge": 0,
            "List_Recharge": [],
            "StackControl": 0,
            "Billetes_Stacked": {},
            "LastInsert": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "TotalItems": {},
            "NextIdShift": 2,
            "user": user,  # Campo adicional para tu interfaz
            "info_only": True
        }
        
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
        
        logging.info("Turno abierto correctamente")
        return True

    def cerrar_turno(self):
        path = self._turno_path()
        if not os.path.exists(path):
            return
        
        try:
            with open(path, "r+", encoding="utf-8") as f:
                data = json.load(f)
                data["Status"] = 1  # 1 = cerrado
                data["FinalDate"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                f.seek(0)
                json.dump(data, f, indent=4)
                f.truncate()
            
            self._popup("Turno cerrado correctamente")
        except Exception as e:
            logging.error(f"Error cerrando turno: {e}")

# Para compatibilidad hacia atrás
class Config:
    def __init__(self):
        self.config_manager = config
    
    def get(self, key, default=None):
        return self.config_manager.get(key, default)
    
    def set(self, key, value):
        if isinstance(value, dict):
            self.config_manager.set_section(key, value)
        else:
            logging.warning("archivo cofig espera un diccionario como valor")##11