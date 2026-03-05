import  os
import  json
import  time
import  base64
import  logging
import  threading
import  traceback
import textwrap

from    datetime  import datetime
from    time      import sleep

from threading import Event
from Src.Config.config_loader import load_config, config
from Src.Views.sqlqueries import QueriesSQLServer

server = config.get("database", "server")
database = config.get("database", "database")
username = config.get("database", "username")
password = config.get("database", "password")

class Invoicing:
    offset = time.timezone if (time.localtime().tm_isdst == 0) else time.altzone
    def _format_currency(self, value):
        """Formatea valores monetarios manteniendo separadores de miles"""
        try:
            if isinstance(value, str):
                # Limpiar formato existente
                value = value.replace('.', '').replace(',', '.')
                value = float(value)
            
            # Para COP, usar enteros con separadores de miles
            if self.currency == "COP":
                value_int = int(round(value))
                # Formatear con puntos como separadores de miles
                return f"{value_int:,}".replace(",", ".")
            else:
                return f"{value:,.2f}"
        except:
            return "0"
    def __init__(self):
        logging.info(f"INIT CLASS ({self.__class__.__name__})")

    """
    #*Params
    # dataPath:    url where the internal files of the biller are to be stored
    # dataConfig:  dictionary with the configuration parameters of the biller, requested by mqtt
    # idDevice:    id of the device
    # saveBilling: url where the generated invoices will be stored
    # mqtt:        instance of the local mqtt class
    # topic:       mqtt receiver
    """
    # initializer and configurator of the biller
    def start(self,dataPath,dataConfig, idDevice, saveBilling = None, mqtt = None, topic = None, config_time="1970-01-01T00:00:00", products=[], pay_methods={})-> bool:
        logging.info(f"------------------------------------------------")
        logging.info(f"             INICIANDO FACTURADOR               ")
        logging.info(f"------------------------------------------------")

        try:
            # global variables
            self.config_time=config_time
            self._mqtt           = mqtt
            self.topic           = topic
            self.dataPath        = dataPath
            self.dataConfig      = dataConfig
            self.saveBilling     = saveBilling
            self.idDevice        = idDevice
            self.dataGovernor    = None
            self.resolution      = None
            self.pay_methods=pay_methods
            self.products=products

            if not self.getSettings(): return False

            return True

        except Exception as e:
            error = str(e) + ": " + traceback.format_exc()
            logging.info(f"Ha Ocurrido un error al iniciar el facturador -----> {error}")
            return False

    # get data from billing files
    def getSettings(self)-> None:
        os.makedirs(f"{self.dataPath}/shiftControl", exist_ok=True)
        os.makedirs(f"{self.dataPath}/transactions/trans/", exist_ok=True)
        os.makedirs(f"{self.dataPath}/transactions/backup/", exist_ok=True)
        os.makedirs(f"{self.dataPath}/transactions/pendientes/", exist_ok=True)

        # *** Añadir esto: asegurar carpeta invoices si se usa ***
        if self.saveBilling and self.saveBilling != f"{self.dataPath}/transactions/trans/":
            os.makedirs(self.saveBilling, exist_ok=True)

        self.controlShift    = f"{self.dataPath}/shiftControl/controlShift.json"
        self.nextInvoice     = f"{self.dataPath}/shiftControl/nextInvoice.json"
        self.global_settings_path = f"{self.dataPath}/shiftControl/global_settings_invoicing.json"
        os.makedirs(f"{self.dataPath}/shiftControl", exist_ok=True)

        self.currency = self.dataConfig.get("Currency","COP")
        self.currency_symbol = self.dataConfig.get("Currency_symbol", "$")

        self.pendientes_folder = f"{self.dataPath}/transactions/pendientes/"

        if not self.saveBilling : self.saveBilling = f"{self.dataPath}/transactions/trans/"

        self.check_pendientes()
        #*Get Resolution
        try:
            url_shiftResult = self.dataPath + "/shiftControl/"
            os.makedirs(f"{self.dataPath}/shiftControl", exist_ok=True)

            if not os.path.exists(self.nextInvoice):
                logging.info(f"No se encuentra el archivo de resolucion local -> {self.nextInvoice}")
                self.updateResolution()
            else:
                with open(self.nextInvoice,'r') as file: self.resolution = json.load(file)
                file.close()

        except Exception as e:
            error = str(e) + ": " + traceback.format_exc()
            logging.info(f"Error al cargar los datos de la resolucion: {error}")
            return False
        

        return True
    
    def check_pendientes(self):
        logging.info("Validando si hay pendientes")
        pendientes = os.listdir(self.pendientes_folder)
        logging.info(f"Hay {len(pendientes)} archivos pendientes")
        for p in pendientes:
            logging.info(f"Validando {p}")
            with open(self.pendientes_folder + p, 'r') as fp:
                invoice = json.load(fp)
                fp.close()
            path_invoice_shift = f"{self.dataPath}/shiftControl/shiftResults/{invoice.get('IdShift')}/{p}"
            logging.info(f"{path_invoice_shift}")
            if not os.path.exists(path_invoice_shift):
                logging.info("El archivo no existe, se agregara al turno")
                self.addInvoiceTurn(invoice)
            else:
                logging.info("El archivo ya existe")
                os.remove(self.pendientes_folder + p) ########           

    def invoice(self, dataInvoice:dict, useIdInvoice:bool, electronicData={"IsElectronic": False},  typeInvoice = 2 , printer = "dict") -> dict:
        self.getSettings()
        def createInvoice():
            logging.info(f"------------------------------------------------")
            logging.info(f"               GENERANDO FACTURA                ")
            logging.info(f"------------------------------------------------")

            try:
                #* Get Data Shift
                for i in range(0,2,1):
                    try:
                        with open(self.controlShift) as file: data_turn = json.load(file)
                        file.close()
                        break
                    except Exception as e:
                        logging.error(f"Error - {e}")
                    
                self. id_shift = data_turn["Id_Shift"]
                dateBilling    = datetime.now()
                if self.config_time == "1970-01-01T00:00:00":	epoch		= int((datetime.now() - datetime.fromisoformat(self.config_time)).total_seconds()	+ self.offset)
                elif self.config_time== "2000-01-01T00:00:00":	epoch		= int((datetime.now() - datetime.fromisoformat(self.config_time)).total_seconds())
                else:										epoch		= int((datetime.now - datetime.fromisoformat(self.config_time)).total_seconds())
                #epoch          = int(datetime.timestamp(dateBilling)*1)

                # CREATE INVOICE
                generic_Invoice = {}
                generic_Invoice["JsonType"]          = int(typeInvoice)
                generic_Invoice["DateNow"]           = int(datetime.timestamp(dateBilling))
                #generic_Invoice["DateNow"]           = epoch
                generic_Invoice["IdInvoice"]         = self.resolution["actualIndexResolution"]
                generic_Invoice["IdDevice"]          = self.idDevice
                generic_Invoice["IdShift"]           = self.id_shift
                generic_Invoice["Id_Transaction"]    = f'{self.idDevice}-{epoch}'
                if dataInvoice.get("token"):
                    generic_Invoice["IdToken"] = dataInvoice["token"]
                    generic_Invoice["TokenTipo"]=dataInvoice["token_type"]
                generic_Invoice["InvoiceDate"]       = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                generic_Invoice["numResolution"]     = self.resolution["numResolution"]
                generic_Invoice["Prefix"]            = self.resolution["prefijo"]
                generic_Invoice["TotalWithoutTaxes"] = 0
                generic_Invoice["TotalTaxes"]        = 0
                generic_Invoice["Subtotal"]          = 0
                generic_Invoice["TotalAdjustments"]  = 0
                generic_Invoice["Total"]             = 0
                generic_Invoice["isVoided"]          = False
                generic_Invoice["IsElectronic"]      = electronicData.get("IsElectronic", False)
                generic_Invoice["Tax"]               = dataInvoice["Tax"]
                generic_Invoice["items"]             = []
                generic_Invoice["PaymentMethod"]     = dataInvoice["PaymentMethod"]
                generic_Invoice["PaymentDetails"]    = dataInvoice["PaymentDetails"]
                generic_Invoice["Receipt"]           = ""
                generic_Invoice["Note"]              = ""
                generic_Invoice["ElectronicData"]    = electronicData.get("ElectronicData", {})
                generic_Invoice["epoch"]             = epoch
                generic_Invoice["TotalItems"]        = {}

                from Src.Config.config_loader import CURRENT_USER
                if CURRENT_USER:
                    generic_Invoice["username"] = CURRENT_USER.get('username', '')
                    # También puedes agregar el nombre completo si lo necesitas
                    if "Details" not in generic_Invoice:
                        generic_Invoice["Details"] = {}
                    generic_Invoice["Details"]["Vendedor"] = CURRENT_USER.get('nombre', '')

                #* ADD ITEMS
                if dataInvoice["items"]:

                    TotalWithoutTaxes = 0
                    totalTaxes        = 0
                    totalsubtotal     = 0
                    totalAdjustment   = 0
                    totalInvoice      = 0

                    taxes = generic_Invoice["Tax"]
                    for item in dataInvoice["items"]:
                        totalItem          = taxCalculator(item, taxes)

                        TotalWithoutTaxes += totalItem["TotalWithoutTaxes"]
                        totalTaxes        += totalItem["tax"]
                        totalsubtotal     += totalItem["Subtotal"]
                        totalAdjustment   += abs(totalItem["TotalAdjustment"])
                        totalInvoice      += totalItem["Total"]

                        if "AgreementsApplied" in item: totalItem["AgreementsApplied"]  = item["AgreementsApplied"]
                        if "ParkingData"       in item: totalItem["ParkinData"]         = item["ParkingData"]
                        if "NoteItems"         in item: totalItem["NoteItems"]          = item["NoteItems"]

                        if "TypeItem" in item :

                            if item["TypeItem"] == 1:
                                if "Carro" in generic_Invoice["TotalItems"]:
                                    generic_Invoice["TotalItems"]["Carro"] += totalItem["Total"]
                                else:
                                    generic_Invoice["TotalItems"]["Carro"] = 0
                                    generic_Invoice["TotalItems"]["Carro"] += totalItem["Total"]
                            elif item["TypeItem"] == 2:
                                if "Moto" in generic_Invoice["TotalItems"]:
                                    generic_Invoice["TotalItems"]["Moto"] += totalItem["Total"]
                                else:
                                    generic_Invoice["TotalItems"]["Moto"] = 0
                                    generic_Invoice["TotalItems"]["Moto"] += totalItem["Total"]
                            elif item["TypeItem"] == 3:
                                if "Placa" in generic_Invoice["TotalItems"]:
                                    generic_Invoice["TotalItems"]["Placa"] += totalItem["Total"]
                                else:
                                    generic_Invoice["TotalItems"]["Placa"] = 0
                                    generic_Invoice["TotalItems"]["Placa"] += totalItem["Total"]

                        else:
                            if "Productos" in generic_Invoice["TotalItems"]:
                                generic_Invoice["TotalItems"]["Productos"] += totalItem["Total"]
                            else:
                                generic_Invoice["TotalItems"]["Productos"] = 0
                                generic_Invoice["TotalItems"]["Productos"] += totalItem["Total"]

                        generic_Invoice["items"].append(totalItem)

                    generic_Invoice["TotalWithoutTaxes"]   = TotalWithoutTaxes
                    generic_Invoice["TotalTaxes"]          = totalTaxes
                    generic_Invoice["Subtotal"]            = totalsubtotal
                    generic_Invoice["TotalAdjustments"]    = totalAdjustment
                    generic_Invoice["Total"]               = totalInvoice
                    generic_Invoice["Reference"]           = {"Id_TransactionParent": generic_Invoice["Id_Transaction"] }

                    if "Note" in dataInvoice            : generic_Invoice["Note"]           = dataInvoice["Note"]
                    if "Reference" in dataInvoice       : generic_Invoice["Reference"]      = dataInvoice["Reference"]
                    if "ElectronicData" in dataInvoice  : generic_Invoice["ElectronicData"] = dataInvoice["ElectronicData"]
                    if "Details" in dataInvoice         : generic_Invoice["Details"]        = dataInvoice["Details"]
                else:
                    logging.info("----> No se puede facturar sin items")
                    return False
                
                if not useIdInvoice and generic_Invoice["Total"] == 0:
                    logging.info("######### No se consumira consecutivo ##########")
                    generic_Invoice["IdInvoice"] = "0"
                    logging.info(f"----> Factura Generada con consecutivo en 0")
                    logging.info(generic_Invoice)

                    return generic_Invoice
                else:
                    logging.info("######### Consumo normal ##########")

                    checkResolution = self.checkResolution()
                    if checkResolution:
                        logging.info("----> Resolucion valida")

                        with open(self.nextInvoice) as file: resolution = json.load(file)
                        file.close()

                        self.resolution = resolution

                        resolution["actualIndexResolution"] = int(resolution["actualIndexResolution"]) + 1
                        with open(self.nextInvoice, 'w') as file: json.dump(resolution, file, indent=4)
                        file.close()

                        print(f"----> Factura Generada")
                        print(f"{generic_Invoice=}")

                        return generic_Invoice

                    else:
                        logging.info("----> Resolucion invalida")
                        logging.info("----> Factura no fue generada")
                        return False

            except Exception as e:
                error = str(e) + ": " + traceback.format_exc()
                logging.info(f"Ha Ocurrido un error al iniciar el Crear Factura -----> {error}")
                return False

        def formatInvoice(invoice):
            # TEMPLATE INVOICE
            """
                @Empresa\n
                @Direccion\n
                @Telefono\n
                NIT: @Nit\n\n\n
                Formulario No: @ResDIAN\n
                FECHA @FechaDIAN hasta @FechaEndDIAN\n
                RANGO DE FACTURACION PREFIJO @IdTerminal\n
                Desde @ResINI hasta @ResFIN\n\n
                Transaccion: @TransaccionId\n\n
                --------------------------------------------\n
                Sistema POS No:      @Recibo\n
                Fecha de expedicion: @FechaRecibo\n
                --------------------------------------------\n
                @Detalles\n
                --------------------------------------------\n

                Cant Descripción      Subtotal   impuesto   Total\n
                --------------------------------------------\n
                @DatosFactura\n
                        SUB TOTAL:       @Moneda @SinImpuestoTotal\n
                        Impuesto :       @Moneda @ImpuestoTotal\n
                                        ------------------\n
                        Total:           @Moneda @Total\n
                        Ajuste:          @Moneda @AjusteAntes\n
                                        ------------------\n\n
                        TOTAL A PAGAR:   @Moneda @ValorTotal\n
                --------------------------------------------\n
                Pago @TipoPago\n
                @DataAux\n
                --------------------------------------------\n
                @Footer
            """

            logging.info(f"invoice - formatInvoice - {self.currency=}")
            match self.currency:
                case "COP":
                    strInvoice = "\x1B\x61\x31\x1B\x45\x0D@Empresa\n@Direccion\nTel: @Telefono\nNIT: @Nit\n@Adicion\nFormulario No: @ResDIAN\nFECHA @FechaDIAN hasta @FechaEndDIAN\nRANGO DE FACTURACION PREFIJO @IdTerminal\nDesde @ResINI hasta @ResFIN\n\x1B\x61\x30--------------------------------------------\n@Sistema No:      @Recibo\nFecha de expedicion: @FechaRecibo\n--------------------------------------------\n@Cliente\n@Detalles--------------------------------------------\nCant Descripción    Subtotal Impuesto Total\n--------------------------------------------\n@DatosFactura\n        SUB TOTAL:       @Moneda @SinImpuestoTotal\n        @ImpuestoName :       @Moneda @ImpuestoTotal\n                        ------------------\n        Total:           @Moneda @Total\n        Ajuste:          @Moneda @AjusteAntes\n                        ------------------\n        TOTAL A PAGAR:   @Moneda @ValorTotal\n--------------------------------------------@Descuentos\nPago @TipoPago\n@DataAux--------------------------------------------\n@Footer--------------------------------------------\nElaborado por: PEPE INTELIGENT SYSTEM S.A.S\nWWW.PEPE.COM\nNIT:1006.029.934-0\n--------------------------------------------\n\x1B\x61\x31CUDE\n@CUFE\n\nRepresentación gráfica de la factura de venta\n\x1B\x45\x0A"
                case "MXN":
                    strInvoice = "\x1B\x61\x31\x1B\x45\x0D@Empresa\n@Direccion\nTel: @Telefono\n@Adicion\n\x1B\x61\x30--------------------------------------------\n@Sistema No:      @Recibo\nFecha de expedicion: @FechaRecibo\n--------------------------------------------\n@Cliente\n@Detalles--------------------------------------------\nCant   Detalle        Subtotal   Impuesto      Total\n--------------------------------------------\n@DatosFactura        SUB TOTAL:       @Moneda @SinImpuestoTotal\n        @ImpuestoName :       @Moneda @ImpuestoTotal\n                        ------------------\n        Total:           @Moneda @Total\n        Ajuste:          @Moneda @AjusteAntes\n                        ------------------\n        TOTAL A PAGAR:   @Moneda @ValorTotal\n--------------------------------------------@Descuentos\nPago @TipoPago\n@DataAux--------------------------------------------\n\x1B\x61\x30@Footer--------------------------------------------\n\x1B\x45\x0A"

            if invoice.get("IsElectronic", False):
                match invoice.get("ElectronicData",{}).get("id_type",""):
                    case "cc"|"CC":
                        nombre_tercero = f"{invoice['ElectronicData']['name1']} {invoice['ElectronicData']['name2']} {invoice['ElectronicData']['lastname1']} {invoice['ElectronicData']['lastname2']}".replace("   "," ").replace("  ", " ")
                        documento_tercero = f"CC {invoice['ElectronicData']['uuid']}"
                    case "nit"|"NIT":
                        nombre_tercero = invoice["ElectronicData"]["razon_social"]
                        documento_tercero = f"NIT {invoice['ElectronicData']['uuid']}"
                    case __:
                        nombre_tercero = "Consumidor final"
                        documento_tercero = "CC 222222222222"

                tercero = f"""Nombre: {nombre_tercero}\nDocumento: {documento_tercero}\n--------------------------------------------"""
                strInvoice = strInvoice.replace("@Cliente", tercero)
                match electronicData.get("electronicBilling",{}).get("proveedor",""):
                    case "carvajal"|"facse":
                        strInvoice = strInvoice.replace("@Sistema", "Facturación electrónica")
                        strInvoice = strInvoice.replace("@Adicion", "\nFactura electrónica de venta\n")
                    case __:
                        strInvoice = strInvoice.replace("@Sistema", "Documento equivalente")
                        strInvoice = strInvoice.replace("@Adicion", "\nDocumento equivalente electrónico tiquete de maquina registradora con sistema P.O.S\n")
            else:
                strInvoice = strInvoice.replace("@Adicion\n", "")
                strInvoice = strInvoice.replace("@Cliente\n", "")
                strInvoice = strInvoice.replace("@Sistema", "Sistema POS")

            #* Aditional Info
            extraItems = ""
            if "Details" in invoice:
                # logging.info(f'{invoice["Details"].keys()=}')
                # if self.currency == "MXN":
                #     invoice["Details"].pop("")
                for key, value in invoice["Details"].items():
                    key = key + ":"
                    key = key.ljust(19, " ")
                    extraItems += f"{key.capitalize()}{value}\n"
                invoice.pop("Details")

            #* List Products
            acu = 0
            listDetails = ""
            # listItems   = ""
            # if invoice.get("items"):
            #     for item in invoice["items"]:
            #         detailItems = ""
            #         for value in item.values():
            #             acu += 1
            #             if acu > 1 and acu < 6:
            #                 detailItems += f"{value}   "

            #         listItems += detailItems + "\n"
            #         acu = 0

            # else: listItems = "Sin Productos":

            ##############################################
            # metodo nuevo agregado para el Bloque RECEIPT 
            ##############################################

            listItems = ""
            convenios_lista = []
            convenios_data = {}
            convenio_base = {"nombre": "", "valor_aplicado": 0}
            
            for i in invoice.get("items", []):
                cantidad = i.get('quantity', 1)
                nombre = i.get('description', '')
                subtotal = i.get('TotalWithoutTaxes', 0)
                impuesto = i.get('tax', 0)
                total_item = i.get('Subtotal', 0)
                
                # Formatear valores con _format_currency
                subtotal_str = self._format_currency(subtotal)
                impuesto_str = self._format_currency(impuesto)
                total_item_str = self._format_currency(total_item)

                nombre_lineas = textwrap.wrap(str(nombre), width=15) if nombre else [""]

                cant_str = str(cantidad).rjust(3)
                nombre = nombre.replace("|", " ")
                
                for idx, linea_nombre in enumerate(nombre_lineas):
                    if idx == 0:
                        linea = (
                            f"{cant_str:>3} "
                            f"{linea_nombre:<17}"#########
                            f"{subtotal_str:>2}  "
                            f"{impuesto_str:>6} "
                            f"{total_item_str:>7}"
                        )
                    else:
                        linea = (
                            f"{'':>4} "
                            f"{linea_nombre:<14}"
                            f"{'':>3}  "
                            f"{'':>8} "
                            f"{'':>9}"
                        )
                    
                    # Agregar al listItems
                    if listItems:
                        listItems += "\n" + linea
                    else:
                        listItems = linea
                
                agreements = i.get("AgreementsApplied", [])
                if isinstance(agreements, list):
                    for agreement in agreements:
                        if agreement not in convenios_lista:
                            convenios_lista.append(agreement)
                
                # Procesar convenios de NoteItems
                note_items = i.get("NoteItems", {})
                detail_liquidation = note_items.get("Detail_liquidation", {})
                convenios_note = detail_liquidation.get("convenios", [])
                
                for c_a in convenios_note:
                    convenio_d = convenio_base.copy()
                    
                    if isinstance(c_a, int):
                        convenio_id = c_a
                        convenio_nombre = ""
                        valor_aplicado = 0
                    else:
                        convenio_id = c_a.get("id", "")
                        convenio_nombre = c_a.get("nombre", "")
                        valor_aplicado = c_a.get("valor_aplicado", 0)
                    
                    if not convenio_nombre and convenio_id:
                        try:
                            gobernador_path = "C:\ProgramData\CI24\Settings\Asistido\gobernador.json"
                            if os.path.exists(gobernador_path):
                                with open(gobernador_path, 'r', encoding='utf-8') as f:
                                    gobernador_data = json.load(f)
                                
                                agreement_section = gobernador_data.get('Agreement', {})
                                convenios_list = agreement_section.get('convenios', [])
                                
                                for convenio in convenios_list:
                                    if convenio.get('convenio') == convenio_id:
                                        convenio_nombre = convenio.get('nombre', f'Convenio {convenio_id}')
                                        break
                                
                                if not convenio_nombre:
                                    convenio_nombre = f'Convenio {convenio_id}'
                            else:
                                convenio_nombre = f'Convenio {convenio_id}'
                        except Exception as e:
                            logging.warning(f"Error obteniendo nombre de convenio: {e}")
                            convenio_nombre = f'Convenio {convenio_id}'
                    
                    # Actualizar o crear entrada en convenios_data
                    convenio_d["nombre"] = convenio_nombre
                    convenio_d["valor_aplicado"] += valor_aplicado
                    id_c = str(convenio_id)
                    
                    if id_c in convenios_data:
                        convenios_data[id_c]["valor_aplicado"] += valor_aplicado
                    else:
                        convenios_data[id_c] = convenio_d
            
            if not listItems:
                listItems = "Sin Productos"
            
            listItems = listItems.rstrip() + "\n"
            
            #### Fin del parcheo ####

           #* DataAux Type Payment
            formatDataAux = {}
            if invoice["PaymentMethod"]   ==  0 : #*EFECTIVO
                typePayment = "Efectivo"
                formatDataAux["Efectivo"]        = invoice["PaymentDetails"]["valuePaid"]
                formatDataAux["Cambio"]          = invoice["PaymentDetails"]["change"]
                formatDataAux["Dinero Faltante"] = invoice["PaymentDetails"]["notDispense"]

            elif invoice["PaymentMethod"] ==  1 : #*CARD
                typePayment = "Tarjeta"
                formatDataAux["Cuotas"]          = invoice["PaymentDetails"]["dues"]
                formatDataAux["Autorizacion"]    = invoice["PaymentDetails"]["cardAuthCode"]
                formatDataAux["Franquicia"]      = invoice["PaymentDetails"]["franchise"]
                formatDataAux["ultimos4"]        = invoice["PaymentDetails"]["last4Number"]
                formatDataAux["tipo"]            = invoice["PaymentDetails"]["accountType"]

            elif invoice["PaymentMethod"] ==  2 : #*MAGNETIC CARD
                typePayment = "MagneticCard"
                formatDataAux["Autorizacion"]    = invoice["PaymentDetails"]["autorization"]
                formatDataAux["Estatus"]         = invoice["PaymentDetails"]["status"]


            elif invoice["PaymentMethod"] ==  3 : #*FLYPASS
                typePayment = "Flypass"
                invoice["PaymentDetails"] = ""

            elif invoice["PaymentMethod"] ==  4 : #*NEQUI
                typePayment = "Nequi"
                formatDataAux["Autorizacion"]    = invoice["PaymentDetails"]["autorization"]
                formatDataAux["Estatus"]         = invoice["PaymentDetails"]["status"]

            elif invoice["PaymentMethod"] ==  5 : #*BANCOLOMBIA
                typePayment = "Bancolombia"
                formatDataAux["Autorizacion"]    = invoice["PaymentDetails"]["autorization"]
                formatDataAux["Estatus"]         = invoice["PaymentDetails"]["status"]

            elif invoice["PaymentMethod"] ==  6 : #Daviplata
                typePayment = "Daviplata"
                formatDataAux["Autorizacion"]    = invoice["PaymentDetails"]["autorization"]
                formatDataAux["Estatus"]         = invoice["PaymentDetails"]["status"]

            elif invoice["PaymentMethod"] ==  7 : #* TRANSFER
                typePayment = "Trasnfererencia"
                formatDataAux["Autorizacion"]    = invoice["PaymentDetails"]["autorization"]
                formatDataAux["Estatus"]         = invoice["PaymentDetails"]["status"]

            else:
                typePayment = "Desconocido"
                invoice["PaymentDetails"] = ""

            dataAux = ""
            if invoice["PaymentDetails"]:
                    dataAux = ""
                    for key, value in formatDataAux.items():
                        key = key + ":"
                        key = key.ljust(19, " ")
                        value_formatted = self._format_currency(value)
                        dataAux += f"{key}$ {value_formatted}\n"

            data_template = self.dataConfig["template_invoice"]

            # Data Enterprise
            strInvoice = strInvoice.replace("@Empresa", data_template["enterprise"])
            strInvoice = strInvoice.replace("@Direccion", data_template["address"])
            strInvoice = strInvoice.replace("@Telefono", data_template["cellphone"])
            strInvoice = strInvoice.replace("@Nit", data_template["nit"])

            # HEADER
            resolution =  self.resolution
            strInvoice = strInvoice.replace("@ResDIAN", resolution["numResolution"])
            strInvoice = strInvoice.replace("@FechaDIAN", str(resolution["startDate"]))
            strInvoice = strInvoice.replace("@FechaEndDIAN", str(resolution["endDate"]))
            strInvoice = strInvoice.replace("@IdTerminal", resolution["prefijo"])
            strInvoice = strInvoice.replace("@ResINI", str(resolution["startNumber"]))
            strInvoice = strInvoice.replace("@ResFIN", str(resolution["endNumber"]))
            strInvoice = strInvoice.replace("@Recibo", str(resolution["prefijo"]) + "-" + str(invoice["IdInvoice"]))
            strInvoice = strInvoice.replace("@FechaRecibo", str(invoice["InvoiceDate"]))
            strInvoice = strInvoice.replace("@TransaccionId", invoice["Id_Transaction"])

            #ITEMS DESCRIPTION
            strInvoice = strInvoice.replace("@Detalles", str(extraItems))
            strInvoice = strInvoice.replace("@DetailsParking", str(listDetails))

            listItems = listItems.rstrip() + "\n"
            strInvoice = strInvoice.replace("@DatosFactura", str(listItems))

            # DATA PAYMENT
            strInvoice = strInvoice.replace("@Moneda",str(self.currency_symbol))
            strInvoice = strInvoice.replace("@Total",self._format_currency(invoice["Total"]))
            strInvoice = strInvoice.replace("@AjusteAntes",self._format_currency(invoice["TotalAdjustments"]))
            total_without_taxes = float(invoice["TotalWithoutTaxes"])
            strInvoice = strInvoice.replace("@SinImpuestoTotal",self._format_currency(total_without_taxes))
            strInvoice = strInvoice.replace("@ImpuestoTotal", self._format_currency(invoice["TotalTaxes"]))
            strInvoice = strInvoice.replace("@ValorTotal",self._format_currency(invoice["Subtotal"]))

            #Descuentos
            logging.info(sum(convenios_lista) > 0)
            if sum(convenios_lista) > 0:
                data_convenios = ""
                for c in convenios_data:
                    data_convenios += convenios_data[c]['nombre'].rjust(20," ") + ": $ " + f"{convenios_data[c]['valor_aplicado']}".ljust(5," ")
                strInvoice = strInvoice.replace("@Descuentos\n", "\nConvenios Aplicados:\n" + data_convenios + "\n\n--------------------------------------------\n")
            else:
                strInvoice = strInvoice.replace("@Descuentos","")

            #INFORMATION AUX
            strInvoice = strInvoice.replace("@TipoPago",str(typePayment))
            strInvoice = strInvoice.replace("@DataAux",str(dataAux))

            strInvoice = strInvoice.replace("@ImpuestoName", f"{invoice['Tax'][0].get('TaxName')} {invoice['Tax'][0]['TaxValue']} %")

            # FOOTER
            if "footer" in data_template: strInvoice = strInvoice.replace("@Footer",data_template["footer"])
            else: strInvoice = strInvoice.replace("@Footer","")

            invoice["ElectronicData"]["resolution"] = self.resolution

            invoice["ReceiptFailToPay"] = self.aux_fail_to_pay(invoice["IdInvoice"],invoice["PaymentDetails"]) if self.dataConfig.get("ReceiptFailToPay",False) else ""
            try:
                logging.info(f"{json.dumps(invoice)=}")
            except:
                logging.info(f"{invoice=}")
            
            with open(f"{self.pendientes_folder}{invoice.get('Prefix')}{invoice.get('IdInvoice')}.json","w") as f:
                json.dump(invoice, f, indent=4)
                f.close

            if electronicData.get("IsElectronic") and f'{invoice["IdInvoice"]}' != '0':
                electronicValues = electronicData.get("electronicBilling",{})

                from Ci24.services.service_electronic import Electronic
                
                getCufe = Electronic().send(
                    provedor=electronicValues.get("proveedor",""),
                    billing_params=invoice,
                    business_params=electronicValues.get("business_params",{}),
                    resolution=self.resolution,
                    connectionValues=electronicValues.get("connectionValues",{}),
                    timeout=self.dataConfig.get("timeout_fe",15)
                )
                
                logging.info(f"Resultado provedor: {getCufe}")
                        
                invoice["ElectronicData"]["error"]  = str(getCufe.get("error"))
                invoice["ElectronicData"]["status"] = getCufe.get("status")
                
                cufe = "En contigencia"
                
                if electronicData.get("electronicBilling",{}).get("proveedor","") != "carvajal":
                    if getCufe.get("adicional",{}).get("transactionId"):
                        invoice["ElectronicData"]["transactionId"] = getCufe["adicional"]["transactionId"]

                match getCufe.get("status"):
                    case "OK":
                        cufe = getCufe['cufe']
                        invoice["ElectronicData"]["cufe"] = cufe
                        invoice["ElectronicData"]["qr"] = getCufe['qr']
                        invoice["ElectronicData"]["SendDate"] = datetime.strftime(datetime.now(),"%Y-%m-%d %H:%M:%S")
                        logging.info(strInvoice)
                        logging.info(f"CUFE: {cufe}")
                        self.contingencia = False

                    case "ERROR":
                        logging.error(f"Error de conexión con el provedor de facturación electronica -> {getCufe.get('error','')}")
                        self.contingencia = True
                    case "FAIL":
                        logging.error(f"El provedor de facturación electronica respondio error -> {getCufe.get('error','')}")
                        self.contingencia = True
                    case __:
                        logging.error("Estado no contemplado")
                        self.contingencia = True
                strInvoice = strInvoice.replace("@CUFE",cufe)
                    
                logging.info("Factura enviada")
            else:
                strInvoice = strInvoice.replace("CUFE\n@CUFE\n","")
                logging.info(strInvoice)
            
            invoice["Receipt"] = strInvoice
            Invoice_bytes      = strInvoice.encode()
            Invoice_Base64     = base64.b64encode(Invoice_bytes)
            # invoice_decode     = base64.b64decode(Invoice_Base64)

            try:
                self.addInvoiceTurn(invoice)
            except Exception as e:
                logging.error("Error al agregar la factura al turno")

            if   printer == "dict": return invoice
            elif printer == "pdf":  return Invoice_Base64
            else:                   return invoice

        def taxCalculator(item:dict, taxes:list):

            cantidad = item.get("quantity", 1)

            totaltaxes = 0
            if item["taxes"]:
                for idtaxes in item["taxes"]:
                    for taxinfo in taxes:
                        if taxinfo["Id_Tax"] == idtaxes:
                            totaltaxes += taxinfo["TaxValue"]
                            break

            if not item["include"]:
                TotalWithoutTaxes = item["Total"]
                tax   = (item["Total"] * totaltaxes) / 100
                total = item["Total"] + tax

            else:
                total = item["Total"]
                totaltaxes = (totaltaxes / 100) + 1
                TotalWithoutTaxes  = round(total / totaltaxes, 2)
                tax   = round(total - TotalWithoutTaxes, 2)

            if item["Total"] == 1:
                totalRound      = item["Total"]
                totalAdjustment = 0
                total           = item["Total"]
            else:
                adjustment      = self.dataConfig["adjustment"]
                totalRound      = total / adjustment
                totalRound      = round(totalRound) * adjustment
                totalAdjustment = totalRound - total

            description = item["description"]
            return {
                    "Id_Product": item["Id_Product"],
                    "quantity": cantidad,  # ¡NUEVO! Incluir cantidad
                    "description": description,
                    "TotalWithoutTaxes": TotalWithoutTaxes,
                    "tax": tax,
                    "Subtotal": totalRound,
                    "TotalAdjustment": abs(totalAdjustment),
                    "Total": total
                    }

        checkTurn = self.checkTurn()

        if checkTurn:
            invoice = createInvoice()
            if invoice:
                logging.info(f"Invoice:{invoice}")
                invoiceFormat  = formatInvoice(invoice)
                return invoiceFormat
            else:
                logging.info("No se ha podido generar la Factura")
                return False
        else:
            return False

    def checkTurn(self) -> bool:
        """Versión robusta que maneja múltiples formatos de turno"""
        try:
            logging.info("--> Verificando estado del turno")
            logging.info(f"Path del turno: {self.controlShift}")
            
            # 1. Si no existe el archivo, crear uno básico
            if not os.path.exists(self.controlShift):
                logging.info("No existe archivo de turno, creando turno...")
                data_basico = self.generateTemplateTurn()
                data_basico["Status"] = 0  # Abierto por defecto
                os.makedirs(os.path.dirname(self.controlShift), exist_ok=True)
                with open(self.controlShift, 'w') as f:
                    json.dump(data_basico, f, indent=4)
                logging.info("Turno creado Correctamente (abierto)")
                return True
            
            # 2. Leer y normalizar cualquier formato
            with open(self.controlShift, 'r') as f:
                contenido = f.read().strip()
            
            if not contenido:
                logging.warning("Archivo de turno vacío, recreando...")
                data_basico = self.generateTemplateTurn()
                data_basico["Status"] = 0
                with open(self.controlShift, 'w') as f:
                    json.dump(data_basico, f, indent=4)
                return True
            
            data = json.loads(contenido)
            
            # 3. Normalizar el campo de estado (aceptar múltiples formatos)
            estado = None
            
            # Buscar estado en cualquier formato posible
            if "Status" in data:
                estado = data["Status"]
            elif "status" in data:
                estado = data["status"]
            elif "estado" in data:
                estado = data["estado"]
            
            # Convertir a numérico si es necesario
            if isinstance(estado, str):
                estado_str = estado.upper()
                if estado_str in ["OPEN", "ABIERTO", "0", "ABIERTO", "ACTIVO"]:
                    estado = 0
                    data["Status"] = 0
                else:
                    estado = 1
                    data["Status"] = 1
                # Actualizar el archivo con formato correcto
                with open(self.controlShift, 'w') as f:
                    json.dump(data, f, indent=4)
            
            # 4. Determinar si el turno está abierto
            if estado == 0:
                logging.info(f"Turno ABIERTO Correctamente.")
                return True
            else:
                logging.info(f"Turno cerrado, por favor abrir turno.")
                return False
                
        except json.JSONDecodeError as e:
            logging.error(f"Error JSON en archivo de turno: {e}")
            # Recrear archivo corrupto
            data_basico = self.generateTemplateTurn()
            data_basico["Status"] = 0
            with open(self.controlShift, 'w') as f:
                json.dump(data_basico, f, indent=4)
            return True
        except Exception as e:
            logging.error(f"Error verificando turno: {e}")
            return False

    # def checkTurn(self) -> bool:
    #     try:
    #         state = False

    #         logging.info("--> Obteniendo status de turno")
    #         logging.info(f"Este es el path -> {self.controlShift}")
            
    #         """ Validacion de turno abierto y obtencion del ID del turno abierto """
    #         idShift     = None
    #         infoMessage = "Error obteniendo id de turno"

    #         #check if turn file is ok
    #         recreate=False
    #         if not os.path.exists(self.controlShift):
    #             recreate=True
    #         else:
    #             try:
    #                 with open(self.controlShift) as turn: currentShift = json.load(turn)
    #             except Exception as err:
    #                 logging.info(f"Control de turno corrupto: {err}")
    #                 recreate=True

    #         if recreate:
    #             logging.info("--> Archivo de control no encontrado o corrupto")
    #             logging.info("--> Creando archivo de control ...")
    #             infoMessage = "el turno fue creado"
    #             controlShift = self.generateTemplateTurn()
    #             controlShift["Status"]  = 1

    #             if not self.dataGovernor:
    #                 logging.info("--> Solicitando datos del turno al gobernador")
    #                 self.dataGovernor = self.configService()
    #             else:
    #                 logging.info("--> Generando turno con datos de gobernador")

    #             if self.dataGovernor == None:
    #                     logging.info("--> No se obtuvo respuesta de gobernador")
    #                     controlShift["Id_Shift"] = 0
    #             else:
    #                 logging.info("--> Generando turno con datos de gobernador")
    #                 infoMessage = "turno fue creado"
    #                 if self.dataGovernor.get("Shift"):
    #                     # controlShift["Id_Shift"] = self.dataGovernor["Shift"]
    #                     if self.dataGovernor.get("data_shift"):
    #                         data_shift = self.dataGovernor["data_shift"]
    #                         keys_data_shift = data_shift.keys()

    #                         for k in controlShift.keys():
    #                             if k not in keys_data_shift:
    #                                 data_shift[k] = controlShift[k]
                            
    #                         controlShift = data_shift
    #                     else:
    #                         controlShift["Id_Shift"] = self.dataGovernor["Shift"]      
    #                 else: 
    #                     controlShift["Id_Shift"] = 0

    #             controlShift["NextIdShift"]      = controlShift["Id_Shift"] + 1
    #             controlShift["InternalControl"]  = controlShift["InitialCash"]

    #             with open(self.controlShift,'w') as createTurn: json.dump(controlShift, createTurn, indent= 4)
    #             createTurn.close()

    #             idShift = controlShift["Id_Shift"]

    #             currentShift = controlShift
                                
    #             if currentShift.get("Status") == 0:
    #                 infoMessage = f"Turno obtenido exitosamente: ID-{idShift}"
    #                 state       = True

    #         else:
    #             with open(self.controlShift) as turn: currentShift = json.load(turn)

    #             if currentShift.get("Status") == 0:
    #                 idShift     = currentShift["Id_Shift"]
    #                 infoMessage = f"Turno obtenido exitosamente: ID-{idShift}"
    #                 state       = True

    #             else:
    #                 infoMessage = "Turno cerrado, por favor abrir turno"


    #         logging.info(f"Respuesta del status del turno: {infoMessage}")
    #     except Exception as e:
    #         error = str(e) + ": " + traceback.format_exc()
    #         logging.error(f"Error chequeando turno: {error}")

    #     finally: return state

    def openTurn(self, content, idShift = None,is_automatic = True)-> dict:
        self.getSettings()
        response          = False
        invoiceOpenShift  = ""

        try:
            if not content:content =  {"Id_People": 0 , "InitialCash": 0}

            checkResolution, message = self.checkResolution()

            if checkResolution:

                logging.info(f"------------------------------------------------")
                logging.info(f"                 ABRIENDO TURNO                 ")
                logging.info(f"------------------------------------------------")

                
                #* CHECK FILES IN APP
                url_ControlShift  = f"{self.dataPath}shiftControl/"
                if not os.path.isdir(url_ControlShift): os.makedirs(url_ControlShift)

                if os.path.exists(self.controlShift):
                    with open(self.controlShift) as file: controlShift = json.load(file)
                    file.close()

                if controlShift.get("Status") == 0 :

                    if self.dataGovernor:
                        if self.dataGovernor.get("Shift") == None : self.dataGovernor["Shift"] = 0
                        if controlShift.get("Id_Shift") < self.dataGovernor.get("Shift") :
                            logging.info("--> Turno desactualizado, Creando un nuevo turno")

                            dataturn = self.generateTemplateTurn()
                            dataturn["Id_Shift"]         = self.dataGovernor.get("Shift", 1) + 1
                            dataturn["NextIdShift"]      = dataturn["Id_Shift"] + 1

                            with open(self.controlShift,'w') as createTurn: json.dump(dataturn, createTurn, indent= 4)
                            createTurn.close()

                            self.id_shift = dataturn["Id_Shift"]
                            self.backupTurn(self.id_shift)
                            response = True

                    else :
                        currentShift      = "Ya existe un turno Abierto"
                        self.idPeopleTurn = controlShift["Id_PeopleOpening"]

                else :
                    # !JSON CONTROL INTERNAL SHIFTS
                    logging.info("--> Abriendo turno")
                    currentShift = self.generateTemplateTurn()

                    if self.dataGovernor:
                        if not self.dataGovernor.get("Shift"):
                            currentShift["Id_Shift"]         = controlShift["NextIdShift"]
                            currentShift["NextIdShift"]      = controlShift["NextIdShift"] + 1

                        elif controlShift.get("Id_Shift") < self.dataGovernor.get("Shift") :

                            currentShift["Id_Shift"]         = self.dataGovernor.get("Shift") + 1
                            currentShift["NextIdShift"]      = controlShift["Id_Shift"] + 1
                        else:
                            currentShift["Id_Shift"]         = controlShift["NextIdShift"]
                            currentShift["NextIdShift"]      = controlShift["NextIdShift"] + 1
                    else:
                            currentShift["Id_Shift"]         = controlShift["NextIdShift"]
                            currentShift["NextIdShift"]      = controlShift["NextIdShift"] + 1

                    currentShift["Id_PeopleOpening"] = content.get("Id_People", 0)
                    currentShift["InitialCash"]      = content.get("InitialCash", 0)
                    currentShift["InternalControl"]  = currentShift["InitialCash"]

                    self.id_shift     = currentShift["Id_Shift"]
                    self.idPeopleTurn = currentShift["Id_PeopleOpening"]

                    with open(self.controlShift,'w') as createTurn: json.dump(currentShift, createTurn, indent= 4)
                    createTurn.close()


                    # !Generate Invoice OpenShift
                    """
                    @Empresa\n
                    @Direccion\n
                    @Telefono\n
                    NIT: @Nit\n\n\n
                    ID Turno:    @TurnoId\n
                    ID Apertura: @AperturaId\n
                    --------------------------------------------\n
                    @DataAux\n
                    --------------------------------------------\n
                    Fecha Apertura:      @FechaApertura\n
                    Factura Inicio:      @FacturaInicio\n\n
                    Monto Inicial:       @Moneda @MontoInicial\n
                    --------------------------------------------\n\n\n
                    """
                    templateInvoice = "@Empresa\n@Direccion\n@Telefono\nNIT: @Nit\n\n\nID Turno:    @TurnoId\nID Apertura: @AperturaId\n--------------------------------------------\n@DataAux\n--------------------------------------------\nFecha Apertura:      @FechaApertura\nFactura Inicio:      @FacturaInicio\n\nMonto Inicial:       @Moneda @MontoInicial\n--------------------------------------------\n\n\n"

                    enterprise = self.dataConfig["template_invoice"]

                    invoiceOpenShift = templateInvoice
                    invoiceOpenShift = invoiceOpenShift.replace("@Empresa", enterprise["enterprise"])
                    invoiceOpenShift = invoiceOpenShift.replace("@Direccion", enterprise["address"])
                    invoiceOpenShift = invoiceOpenShift.replace("@Telefono", enterprise["cellphone"])
                    invoiceOpenShift = invoiceOpenShift.replace("@Nit", enterprise["nit"])

                    invoiceOpenShift = invoiceOpenShift.replace("@DataAux", "Factura Apertura de Turno")
                    invoiceOpenShift = invoiceOpenShift.replace("@TurnoId", str(self.id_shift))
                    invoiceOpenShift = invoiceOpenShift.replace("@AperturaId", str(self.idPeopleTurn))
                    invoiceOpenShift = invoiceOpenShift.replace("@FechaApertura", str(currentShift["InitialDate"]))
                    invoiceOpenShift = invoiceOpenShift.replace("@FacturaInicio", str(currentShift["InitInvoice"]))

                    invoiceOpenShift = invoiceOpenShift.replace("@Moneda",str(self.currency_symbol))
                    invoiceOpenShift = invoiceOpenShift.replace("@MontoInicial", str(round(currentShift["InitialCash"])))

                    response = True

                    # !JSON SEND OPENSHIFT
                    openTurn = {}
                    #* DATA OpenTurn
                    openTurn["JsonType"]     = 3
                    openTurn["Id_Device"]    =  int(self.idDevice)
                    openTurn["Id_Shift"]     =  int(currentShift["Id_Shift"])
                    openTurn["Id_People"]    =  content["Id_People"]
                    openTurn["InitialCash"]  =  content["InitialCash"]
                    openTurn["FinalCash"]    =  0
                    openTurn["InvoiceCount"] =  0
                    openTurn["InvoiceTotal"] =  0
                    openTurn["InitialDate"]  =  str(currentShift["InitialDate"] )
                    openTurn["Receipt"]      =  str(invoiceOpenShift)
                    openTurn["OpenShift"]    =  True

                    nameShift = f"shiftResult-{int(time.time()*1000)}"
                    with open(self.saveBilling + str(nameShift) + '.json','w') as sendInvoice: json.dump(openTurn, sendInvoice, indent= 4)
                    sendInvoice.close()

                    self.backupTurn(self.id_shift)
                    Invoice_bytes  = invoiceOpenShift.encode()
                    Invoice_Base64 = base64.b64encode(Invoice_bytes)
                    logging.info(invoiceOpenShift)
            else:
                response         = checkResolution
                invoiceOpenShift = message
        except Exception as e:
            currentShift     = str(e) + ": " + traceback.format_exc()
            logging.error(f"Error abriendo turno: {currentShift}")

        finally:
            return response,invoiceOpenShift

    def closeTurn(self, content:dict,str_inventory='')->str:
        """ Funcion para cerrar turno """
        retorno = False
        try:
            if not content: content =  {"Id_People": 0 , "FinalCash": 0}

            checkResolution, message = self.checkResolution()
            if checkResolution:
                logging.info(f"------------------------------------------------")
                logging.info(f"                 CERRANDO TURNO                 ")
                logging.info(f"------------------------------------------------")
                

                #*get Data from "Turn"
                with open(self.controlShift) as dataTurn: turn = json.load(dataTurn)
                dataTurn.close()

                if turn["Status"] == 1:
                    message = "EL TURNO YA FUE CERRADO"
                    invoiceCloseShift = ""
                else:
                    # diference = totalCash - turn["InternalControl"]
                    balance = self.get_balance()

                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                    turn["Id_PeopleClosed"] = content["Id_People"]
                    # turn["FinishInvoice"]   = self.resolution["actualIndexResolution"] - 1
                    turn["FinalCash"]       = content["FinalCash"]
                    turn["FinalDate"]       = str(timestamp)
                    turn["Status"]          = 1
                    totalCash               = turn["FinalCash"] + turn["StackControl"]

                    with open(self.controlShift, 'w', encoding='utf-8') as file: json.dump(turn, file, indent=2)
                    file.close()

                    id_shift        = str(turn['Id_Shift'])
                    url_shiftResult = self.dataPath + "/shiftControl/shiftResults/" + id_shift
                    os.makedirs(url_shiftResult, exist_ok=True)


                    if os.path.isdir( f"{url_shiftResult}" ):
                        nameShift = f"shiftResult-{id_shift}.json"
                        with open(url_shiftResult + '/'+ nameShift, 'w', encoding='utf-8') as file: json.dump(turn, file, indent=4)
                        file.close()

                    # !Generate Invoice CloseShift
                    """
                    @Empresa\n@Direccion\n@Telefono\n
                    NIT: @Nit\n\n\n
                    --------------------------------------------\n
                    @DataAux\n
                    --------------------------------------------\n
                    ID Turno:             @IDTurno\n
                    ID Apertura:          @IDApertura\n
                    ID Cierre:            @IDCierre\n
                    --------------------------------------------\n
                    Fecha Apertura:       @FechaApertura\n
                    Fecha Cierre:         @FechaCierre\n\n
                    --------------------------------------------\n
                    Factura Inicio:       @FacturaInicio\n
                    Factura Final:        @FacturaFinal\n
                    Total Facturas:       @TotalFacturas\n
                    --------------------------------------------\n
                    Base(Efectivo):       @Moneda @MontoInicial\n
                    Recargas:             @Moneda @Recargas\n
                    Retiros:              @Moneda @Retiros\n
                    Vaciados:             @Moneda @Vaciados\n
                    Fallos al devolver:   @Moneda @FallosAlDevolver\n
                    Efectivo Facturado:   @Moneda @Cash\n
                    Efectivo Total:       @Moneda @ControlInterno\n
                    --------------------------------------------\n
                    Detalle de Pagos\n
                    --------------------------------------------\n
                    @PayDetails
                                        ----------------------\n
                    Total Facturado:      @Moneda @Total\n
                    --------------------------------------------\n
                    Detalle de Productos Facturados\n
                    --------------------------------------------\n
                    @TypeItem
                    Total Facturado  :      @Moneda @Total\n
                    """
                    
                    templateInvoice = """@Empresa\n@Direccion\n@Telefono\nNIT: @Nit\n\n\n--------------------------------------------\n@DataAux\n--------------------------------------------\nID Turno:             @IDTurno\nID Apertura:          @IDApertura\nID Cierre:            @IDCierre\n--------------------------------------------\nFecha Apertura:       @FechaApertura\nFecha Cierre:         @FechaCierre\n--------------------------------------------\nFactura Inicio:       @FacturaInicio\nFactura Final:        @FacturaFinal\nTotal Facturas:       @TotalFacturas\n--------------------------------------------\nBase(Efectivo):       @Moneda @MontoInicial\nRecargas:             @Moneda @Recargas\nRetiros:              @Moneda @Retiros\nVaciados:             @Moneda @Vaciados\nFallos al devolver:   @Moneda @FallosAlDevolver\nEfectivo Facturado:   @Moneda @Cash\n                    ------------------------\n\nEfectivo Total:       @Moneda @ControlInterno\n--------------------------------------------\nDetalle de Pagos\n--------------------------------------------\n@PayDetails                    ----------------------\nTotal Facturado:      @Moneda @Total\n--------------------------------------------\nDetalle de Productos Facturados\n--------------------------------------------\n@TypeItem                    ------------------------\n\nTotal Facturado:      @Moneda @Total\n--------------------------------------------\n@List_Recharge\n--------------------------------------------\n@List_Withdrawal\n--------------------------------------------\n@List_Emptied\n--------------------------------------------\n@List_FailReturn\n--------------------------------------------\n"""

                    enterprise = self.dataConfig["template_invoice"]

                    invoiceCloseShift = templateInvoice
                    invoiceCloseShift = invoiceCloseShift.replace("@Empresa", enterprise["enterprise"])
                    invoiceCloseShift = invoiceCloseShift.replace("@Direccion", enterprise["address"])
                    invoiceCloseShift = invoiceCloseShift.replace("@Telefono", enterprise["cellphone"])
                    invoiceCloseShift = invoiceCloseShift.replace("@Nit", enterprise["nit"])

                    invoiceCloseShift = invoiceCloseShift.replace("@DataAux", "Factura Cierre de Turno")

                    invoiceCloseShift = invoiceCloseShift.replace("@IDTurno", str(turn["Id_Shift"]))
                    invoiceCloseShift = invoiceCloseShift.replace("@IDApertura", str(turn["Id_PeopleOpening"]))
                    invoiceCloseShift = invoiceCloseShift.replace("@IDCierre", str(turn["Id_PeopleClosed"]))

                    invoiceCloseShift = invoiceCloseShift.replace("@FechaApertura", str(turn["InitialDate"]))
                    invoiceCloseShift = invoiceCloseShift.replace("@FechaCierre", str(turn["FinalDate"]))

                    invoiceCloseShift = invoiceCloseShift.replace("@FacturaInicio", str(turn["InitInvoice"]))
                    invoiceCloseShift = invoiceCloseShift.replace("@FacturaFinal", str(turn["FinishInvoice"]))
                    invoiceCloseShift = invoiceCloseShift.replace("@TotalFacturas", str(turn["TotalInvoices"]))

                    invoiceCloseShift = invoiceCloseShift.replace("@Moneda", str(self.currency_symbol))
                    invoiceCloseShift = invoiceCloseShift.replace("@MontoInicial", str(round(turn["InitialCash"])))
                    invoiceCloseShift = invoiceCloseShift.replace("@Recargas", str(round(turn["Recharge"])))
                    invoiceCloseShift = invoiceCloseShift.replace("@Retiros", str(round(turn["Withdrawal"])))
                    invoiceCloseShift = invoiceCloseShift.replace("@Vaciados", str(round(turn["Emptied"])))
                    invoiceCloseShift = invoiceCloseShift.replace("@FallosAlDevolver", str(round(turn["FailReturn"])))
                    #invoiceCloseShift = invoiceCloseShift.replace("@Cash", str(round(turn["MethodsPay"])))
                    invoiceCloseShift = invoiceCloseShift.replace("@ControlInterno", str(round(totalCash)))
                    invoiceCloseShift = invoiceCloseShift.replace("@Total", str(round(turn["TotalwhitTaxes"])))

                    if turn.get("Recharge",0) > 0:
                        recargas = "Lista de Recargas\n--------------------------------------------\n"
                        for r in turn.get("List_Recharge",[]):
                            recargas += f'{r["time"]} {self.currency_symbol} {r["value"]}\n'
                        invoiceCloseShift = invoiceCloseShift.replace("@List_Recharge", recargas)
                    else:
                        invoiceCloseShift = invoiceCloseShift.replace("@List_Recharge\n--------------------------------------------\n", "")

                    if turn.get("Withdrawal",0) > 0:
                        retiros = "Lista de Retiros\n--------------------------------------------\n"
                        for w in turn.get("List_Withdrawal",[]):
                            retiros += f'{w["time"]} {self.currency_symbol} {w["value"]}\n'
                        invoiceCloseShift = invoiceCloseShift.replace("@List_Withdrawal", retiros)
                    else:
                        invoiceCloseShift = invoiceCloseShift.replace("@List_Withdrawal\n--------------------------------------------\n", "")

                    if turn.get("Emptied",0) > 0:
                        vaciados = "Lista de Vaciados\n--------------------------------------------\n"
                        for e in turn.get("List_Emptied",[]):
                            vaciados += f'{e["time"]} {self.currency_symbol} {e["value"]}\n'
                        invoiceCloseShift = invoiceCloseShift.replace("@List_Emptied", vaciados)
                    else:
                        invoiceCloseShift = invoiceCloseShift.replace("@List_Emptied\n--------------------------------------------\n", "")

                    if turn.get("FailReturn",0) > 0:
                        fallos = "Fallos al pagar\n--------------------------------------------\n"
                        for e in turn.get("List_FailReturn",[]):
                            fallos += f'{e["time"]} {self.currency_symbol} {e["value"]}\n'
                        invoiceCloseShift = invoiceCloseShift.replace("@List_FailReturn", fallos)
                    else:
                        invoiceCloseShift = invoiceCloseShift.replace("@List_FailReturn\n--------------------------------------------\n", "")

                    detail = ""
                    cash = 0
                    for key in balance["pay_methods"]:
                        detail += f"{key.ljust(22, ' ')}\n"
                        if key[:2] == "0-": cash += balance['pay_methods'][key]['total']
                        c = 0
                        for keyp in balance["pay_methods"][key]["products"]:
                            c += 1
                            detail += f"  {keyp.ljust(20,' ')}({str(balance['pay_methods'][key]['products'][keyp]['cantidad']).rjust(3,' ')}) $ {balance['pay_methods'][key]['products'][keyp]['total']}\n"
                        if c > 1:
                            detail += f"{' ' * 22}{'-' * 10}\n"
                            detail += f"{' ' * 22}$ {balance['pay_methods'][key]['total']}\n"

                    invoiceCloseShift = invoiceCloseShift.replace("@PayDetails", detail)
                    invoiceCloseShift = invoiceCloseShift.replace("@Cash", str(cash))

                    detail = ""
                    cash = 0
                    for key in balance["products"]:
                        detail += f"{key.ljust(22,' ')}({str(balance['products'][key]['cantidad']).rjust(3,' ')}) $ {balance['products'][key]['total']}\n"

                    invoiceCloseShift = invoiceCloseShift.replace("@TypeItem", detail)

                    invoiceCloseShift += str_inventory

                    # !JSON SEND CLOSE SHIFT
                    closeTurn = {}
                    #* DATA OpenTurn
                    closeTurn["JsonType"] = 3
                    closeTurn["Id_Device"]       =  int(turn["Id_Device"])
                    closeTurn["Id_Shift"]        =  int(turn["Id_Shift"])
                    closeTurn["Id_People"]       =  turn["Id_PeopleOpening"]
                    closeTurn["InitialCash"]     =  turn["InitialCash"]
                    closeTurn["FinalCash"]       =  turn["FinalCash"]
                    closeTurn["InvoiceCount"]    =  turn["TotalInvoices"]
                    closeTurn["InvoiceTotal"]    =  turn["TotalwhitTaxes"]
                    closeTurn["InitialDate"]     =  turn["InitialDate"]
                    closeTurn["FinalDate"]       =  turn["FinalDate"]
                    closeTurn["Receipt"]         =  str(invoiceCloseShift)
                    closeTurn["OpenShift"]       =  False


                    # url_billings = f"{self.dataPath}transactions/trans/"
                    if not os.path.isdir(self.saveBilling):
                        logging.info(" ERROR ---> No se encuentra la ruta para enviar la factura de cierre ")
                        return False
                    else:
                        nameShift = f"shiftResult-{int(time.time()*1000)}"
                        logging.info("//////////////////////////////////////////////////////////////////////////////////////////////////////////")
                        logging.info(f"El nombre del archivo que se está poniendo en transacciones es: {nameShift}")
                        with open(self.saveBilling + str(nameShift) + '.json','w') as sendInvoice: json.dump(closeTurn, sendInvoice, indent= 4)
                        sendInvoice.close()

                    retorno = True
                    message = "TURNO CERRADO EXITOSAMENTE"
                    logging.info(f"Respuesta al cerrar turno: {message}")
                    logging.info(invoiceCloseShift)

                    Invoice_bytes  = invoiceCloseShift.encode()
                    Invoice_Base64 = base64.b64encode(Invoice_bytes)
            else:
                logging.info("--> No se genero el cierre de turno, resolución invalida")
                invoiceCloseShift = ""
                
        except Exception as e:
            currentShift     = str(e) + ": " + traceback.format_exc()
            logging.error(f"Error cerrando turno: {currentShift}")
            invoiceCloseShift = ""
            retorno = False

        finally:
            return retorno,invoiceCloseShift

    def backupTurn(self,idShift:int)-> bool:
        """ Escribe el JSON del turno y lo guarda localmente """
        try:
            url_shiftResult = self.dataPath + "shiftControl/shiftResults/"
            os.makedirs(url_shiftResult, exist_ok=True)

            shiftPackage = url_shiftResult + f"/{idShift}/"
            if not os.path.exists(shiftPackage ): os.makedirs(shiftPackage)

            logging.info("-----------------------------------------------------")
            logging.info("---> Creando Backup del turno")
            logging.info("-----------------------------------------------------")
            return True
        except Exception as e:
            logging.error(f"Error al Crear el Backup: {e}")
            return False

    def get_product(self,product_id):
        product= {}
        if self.products:
            for p in self.products:
                if p["product_id"]==product_id:
                    product=p
                    break
        return product

    def get_balance(self,shift_id=None) -> dict:
        import glob
        if not shift_id:
            with open(self.controlShift) as f:
                shift = json.load(f)

        shift_id=shift["Id_Shift"]
        path = self.dataPath + "/shiftControl/shiftResults/"+str(shift_id)+"/"
        #print (shift)
        balance={"invoices":{},"products":{},"pay_methods":{}}

        for file in glob.glob(path + '*.json'):
            invoice = None
            try:
                with open(file) as f:
                    invoice_data = f.read()
                if len(invoice_data)>0:
                    invoice=json.loads(invoice_data)
                else:
                    logging.info(f"Error size:0 {file}")
            except Exception as err:
                logging.info(f"Error reading: {file}, {err}")
                invoice=None

            if invoice:
                if invoice.get("JsonType",0)==2:
                    # if balance.get("invoices"):
                    # balance["invoices"][invoice["IdInvoice"]]=invoice
                    paymethod = invoice.get("PaymentMethod",0)
                    pay_method_key=str(paymethod)+"-"+self.pay_methods.get(paymethod,"")
                    if not balance["pay_methods"].get(pay_method_key):balance["pay_methods"][pay_method_key]={}
                    balance["pay_methods"][pay_method_key]["total"] = balance["pay_methods"][pay_method_key].get("total",0) + invoice["Total"]
                    if not balance["pay_methods"][pay_method_key].get("products"): balance["pay_methods"][pay_method_key]["products"]={}
                    for item in invoice["items"]:
                        amount=item["Subtotal"]
                        product=item["Id_Product"]
                        # logging.info(f"product:{product}")
                        product_key=str(product)+"-"+self.get_product(product).get("description","")
                        
                        if not balance["pay_methods"][pay_method_key]["products"].get(product_key):
                            balance["pay_methods"][pay_method_key]["products"][product_key] = {"total":0, "cantidad":0}
                        if not balance["products"].get(product_key):
                            balance["products"][product_key] = {"total":0, "cantidad":0}

                        balance["pay_methods"][pay_method_key]["products"][product_key]["total"]    += amount
                        balance["pay_methods"][pay_method_key]["products"][product_key]["cantidad"] += 1
                        balance["products"][product_key]["total"]   += amount
                        balance["products"][product_key]["cantidad"]+= 1

        return balance

    def balanceTurn(self, inventario)->str:
        """ Funcion Obtener balance turno """
        retorno = False
        try:
            logging.info("-----------------------------------------------------")
            logging.info("                           Balance del turno                           ")
            logging.info("-----------------------------------------------------")

            #*get Data from "Turn"
            with open(self.controlShift) as dataTurn: turn = json.load(dataTurn)
            dataTurn.close()

            logging.info(f"{turn=}")
            totalCash = turn["InternalControl"]

            if turn["Status"] == 1:
                message = "NO SE GENERA BALANCE,EL TURNO YA FUE CERRADO"
                retorno = False
                invoiceBalanceShift = ""
            else:
                balance = self.get_balance()
                logging.info(f"{balance=}")

                # !Generate Invoice BalanceShift
                """
                --------------------------------------------
                BALANCE TURNO
                --------------------------------------------
                ID Turno:              @IDTurno
                Fecha Apertura:        @FechaApertura
                Factura Inicio:        @FacturaInicio
                Total Facturas:        @TotalFacturas
                --------------------------------------------
                Descripcion
                --------------------------------------------
                Base(Efectivo):     @Moneda @MontoInicial
                Total Recargas:     @Moneda @Recharge
                Total Retiros:      @Moneda @Withdrawal
                Total Vaciados:     @Moneda @Emptied
                Fallos al devolver: @Moneda @FallosAlDevolver
                Efectivo Facturado: @Moneda @Cash
                                    ---------------------
                Control Interno:    @Moneda @ControlInterno
                --------------------------------------------
                Inventario:         @Moneda @Inventario
                Dinero en Stack:    @Moneda @Stack
                                    ---------------------
                Inventario Total:   @Moneda @InventarioTotal
                --------------------------------------------
                Diferencia:         @Moneda @Diferencia

                Detalle de Productos Facturados
                --------------------------------------------
                @TypeItem--------------------------------------------
                Detalle de Pagos
                --------------------------------------------
                @PayDetails                    --------------------

                Total Facturado:      @Moneda @Total
                --------------------------------------------
                @List_Recharge
                --------------------------------------------
                @List_Withdrawal
                --------------------------------------------
                @List_Emptied
                --------------------------------------------
                @List_FailReturn
                --------------------------------------------
                @Billetes_Stacked
                --------------------------------------------
                @DataAux
                --------------------------------------------
                """
                
                templateInvoice = "--------------------------------------------\nBALANCE TURNO\n--------------------------------------------\nID Turno:              @IDTurno\nFecha Apertura:        @FechaApertura\nFactura Inicio:        @FacturaInicio\nTotal Facturas:        @TotalFacturas\n--------------------------------------------\nDescripcion\n--------------------------------------------\nBase(Efectivo):     @Moneda @MontoInicial\nTotal Recargas:     @Moneda @Recharge\nTotal Retiros:      @Moneda @Withdrawal\nTotal Vaciados:     @Moneda @Emptied\nFallos al devolver: @Moneda @FallosAlDevolver\nEfectivo Facturado: @Moneda @Cash\n                    ---------------------\nControl Interno:    @Moneda @ControlInterno\n--------------------------------------------\nInventario:         @Moneda @Inventario\nDinero en Stack:    @Moneda @Stack\n                    ---------------------\nInventario Total:   @Moneda @InventarioTotal\n--------------------------------------------\nDiferencia:         @Moneda @Diferencia\n\nDetalle de Productos Facturados\n--------------------------------------------\n@TypeItem--------------------------------------------\nDetalle de Pagos\n--------------------------------------------\n@PayDetails                    --------------------\n\nTotal Facturado:      @Moneda @Total\n--------------------------------------------\n@List_Recharge\n--------------------------------------------\n@List_Withdrawal\n--------------------------------------------\n@List_Emptied\n--------------------------------------------\n@List_FailReturn\n--------------------------------------------\n@Billetes_Stacked\n--------------------------------------------\n@DataAux\n--------------------------------------------\n"
                enterprise = self.dataConfig["template_invoice"]

                invoiceBalanceShift = templateInvoice
                invoiceBalanceShift = invoiceBalanceShift.replace("@IDTurno", str(turn["Id_Shift"]))
                invoiceBalanceShift = invoiceBalanceShift.replace("@FechaApertura", str(turn["InitialDate"]))
                invoiceBalanceShift = invoiceBalanceShift.replace("@FacturaInicio", str(turn["InitInvoice"]))
                invoiceBalanceShift = invoiceBalanceShift.replace("@TotalFacturas", str(turn["TotalInvoices"]))
                invoiceBalanceShift = invoiceBalanceShift.replace("@Moneda", str(self.currency_symbol))
                invoiceBalanceShift = invoiceBalanceShift.replace("@MontoInicial", str(round(turn["InitialCash"])))
                invoiceBalanceShift = invoiceBalanceShift.replace("@FallosAlDevolver", str(round(turn["FailReturn"])))

                invoiceBalanceShift = invoiceBalanceShift.replace("@Recharge", str(round(turn.get("Recharge",0))))
                invoiceBalanceShift = invoiceBalanceShift.replace("@Withdrawal", str(round(turn.get("Withdrawal",0))))
                invoiceBalanceShift = invoiceBalanceShift.replace("@Emptied", str(round(turn.get("Emptied",0))))

                invoiceBalanceShift = invoiceBalanceShift.replace("@ControlInterno", str(round(totalCash)))
                invoiceBalanceShift = invoiceBalanceShift.replace("@Total", str(round(turn["TotalwhitTaxes"])))


                invoiceBalanceShift = invoiceBalanceShift.replace("@DataAux", "Factura Balance de Turno")

                if turn.get("Recharge",0) > 0:
                    recargas = "Lista de Recargas\n--------------------------------------------\n"
                    for r in turn.get("List_Recharge",[]):
                        recargas += f'{r["time"]} {self.currency_symbol} {r["value"]}\n'
                    invoiceBalanceShift = invoiceBalanceShift.replace("@List_Recharge", recargas)
                else:
                    invoiceBalanceShift = invoiceBalanceShift.replace("@List_Recharge\n--------------------------------------------\n", "")

                if turn.get("Withdrawal",0) > 0:
                    retiros = "Lista de Retiros\n--------------------------------------------\n"
                    for w in turn.get("List_Withdrawal",[]):
                        retiros += f'{w["time"]} {self.currency_symbol} {w["value"]}\n'
                    invoiceBalanceShift = invoiceBalanceShift.replace("@List_Withdrawal", retiros)
                else:
                    invoiceBalanceShift = invoiceBalanceShift.replace("@List_Withdrawal\n--------------------------------------------\n", "")

                if turn.get("Emptied",0) > 0:
                    vaciados = "Lista de Vaciados\n--------------------------------------------\n"
                    for e in turn.get("List_Emptied",[]):
                        vaciados += f'{e["time"]} {self.currency_symbol} {e["value"]}\n'
                    invoiceBalanceShift = invoiceBalanceShift.replace("@List_Emptied", vaciados)
                else:
                    invoiceBalanceShift = invoiceBalanceShift.replace("@List_Emptied\n--------------------------------------------\n", "")

                if turn.get("FailReturn",0) > 0:
                    fallos = "Fallos al pagar\n--------------------------------------------\n"
                    for e in turn.get("List_FailReturn",[]):
                        fallos += f'{e["time"]} {self.currency_symbol} {e["value"]}\n'
                    invoiceBalanceShift = invoiceBalanceShift.replace("@List_FailReturn", fallos)
                else:
                    invoiceBalanceShift = invoiceBalanceShift.replace("@List_FailReturn\n--------------------------------------------\n", "")

                if len(turn.get("Billetes_Stacked",{}).keys()) > 0:
                    Billetes_Stacked = "Billetes en Stack\n--------------------------------------------\n"
                    for e in turn["Billetes_Stacked"]:
                        Billetes_Stacked += f'{str(self.currency_symbol)} {e} - {turn["Billetes_Stacked"][e]}\n'
                    invoiceBalanceShift = invoiceBalanceShift.replace("@Billetes_Stacked", Billetes_Stacked)
                else:
                    invoiceBalanceShift = invoiceBalanceShift.replace("@Billetes_Stacked\n--------------------------------------------\n", "")
                
                detail=""
                cash=0
                for key in balance["pay_methods"]:
                    detail+=f"{key.ljust(22, ' ')}\n"
                    if key[:2]=="0-": cash+=balance['pay_methods'][key]['total']
                    c=0
                    for keyp in balance["pay_methods"][key]["products"]:
                        c+=1
                        detail+=f"  {keyp.ljust(20,' ')}({str(balance['pay_methods'][key]['products'][keyp]['cantidad']).rjust(3,' ')}) $ {balance['pay_methods'][key]['products'][keyp]['total']}\n"
                    if c>1:
                        detail += f"{' ' * 22}{'-'*10}\n"
                        detail += f"{' '*22}$ {balance['pay_methods'][key]['total']}\n"

                invoiceBalanceShift = invoiceBalanceShift.replace("@PayDetails", detail)
                invoiceBalanceShift = invoiceBalanceShift.replace("@Cash", str(cash))

                detail=""
                for key in balance["products"]:
                    detail+=f"{key.ljust(22, ' ')}({str(balance['products'][key]['cantidad']).rjust(3,' ')}) $ {balance['products'][key]['total']}\n"

                invoiceBalanceShift = invoiceBalanceShift.replace("@TypeItem", detail)

                # !JSON SEND BALANCE SHIFT
                balanceShift = {}
                #* DATA OpenTurn
                balanceShift["ID Turno"]            = int(turn["Id_Shift"])
                balanceShift["Fecha Apertura"]      = turn["InitialDate"]
                balanceShift["Total Facturas"]      = turn["TotalInvoices"]
                balanceShift["Base"]                = '${:,.2f}'.format(int(turn["InitialCash"]))
                balanceShift["Efectivo Facturado"]  = '${:,.2f}'.format(int(cash))
                balanceShift["Fallos al devolver"]  = '${:,.2f}'.format(int(turn["FailReturn"]))
                balanceShift["Recargas"]            = '${:,.2f}'.format(int(turn["Recharge"]))
                balanceShift["Retiros"]             = '${:,.2f}'.format(int(turn["Withdrawal"]))
                balanceShift["Vaciados"]            = '${:,.2f}'.format(int(turn["Emptied"]))
                balanceShift["Control Interno"]     = '${:,.2f}'.format(int(totalCash))
                # balanceShift["InternalControl"]     = totalCash
                cash=0

                invoiceBalanceShift = invoiceBalanceShift.replace("@Stack", str(round(turn["StackControl"])))
                
                real_money = inventario + int(turn["StackControl"])
                invoiceBalanceShift = invoiceBalanceShift.replace("@InventarioTotal",str(real_money))
                invoiceBalanceShift = invoiceBalanceShift.replace("@Inventario",str(inventario))
                invoiceBalanceShift = invoiceBalanceShift.replace("@Diferencia",str(real_money - totalCash))

                
                balanceShift["Inventario"]	= '${:,.2f}'.format(int(inventario))
                balanceShift["Stack"]		= '${:,.2f}'.format(int(turn["StackControl"]))
                balanceShift["Diferencia"]	= '${:,.2f}'.format(int(real_money - totalCash))


                # balanceShift["InitInvoice"]         = int(turn["InitInvoice"])
                # balanceShift["MethodsPay"]          = turn["MethodsPay"]
                # balanceShift["StackControl"]        = turn["StackControl"]
                balanceShift["Receipt"]             = str(invoiceBalanceShift)

                retorno = True
                message = "Balance del turno generado"
                logging.info(invoiceBalanceShift)

        except Exception as e:
            currentShift     = str(e) + ": " + traceback.format_exc()
            logging.error(f"Error al generar balance: {currentShift}")
            message      = "Balance del turno no fue generado"
            balanceShift = ""

        finally :
            logging.info(f"Respuesta del balance turno: {message}")
            return retorno,balanceShift

    def statusTurn(self, content:dict):

        if not content: content =  {"Id_People": 0 , "CurrentCash": 0}

        try:
            logging.info("-----------------------------------------------------")
            logging.info("                Estatus del turno                    ")
            logging.info("-----------------------------------------------------")

            #*get Data from "Turn"
            with open(self.controlShift) as dataTurn: turn = json.load(dataTurn)
            dataTurn.close()

            if turn["Status"] == 1:
                message = "EL TURNO YA FUE CERRADO"
                retorno = False
                invoiceStatusShift = ""
            else:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                turn["Id_PeopleClosed"] = content["Id_People"]
                turn["FinishInvoice"]   = self.resolution["actualIndexResolution"]
                totalCash               = turn["CurrentCash"] + turn["StackControl"]

                with open(self.controlShift, 'w', encoding='utf-8') as file: json.dump(turn, file, indent=2)
                file.close()

                id_shift = str(turn['Id_Shift'])

                # !Generate Invoice StatusShift
                """
                @Empresa\n@Direccion\n@Telefono\n
                NIT: @Nit\n\n\n
                --------------------------------------------\n
                @DataAux\n
                --------------------------------------------\n
                ID Turno:             @IDTurno\n
                ID Apertura:          @IDApertura\n
                ID Cierre:            @IDCierre\n
                --------------------------------------------\n
                Fecha Apertura:       @FechaApertura\n
                Fecha Cierre:         @FechaCierre\n\n
                --------------------------------------------\n
                Factura Inicio:       @FacturaInicio\n
                Factura Final:        @FacturaFinal\n
                Total Facturas:       @TotalFacturas\n
                --------------------------------------------\n
                Base(Efectivo):       @Moneda @MontoInicial\n
                Recargas:             @Moneda @Recargas\n
                Retiros:              @Moneda @Vaciados\n
                Fallos al devolver:   @Moneda @FallosAlDevolver\n
                Efectivo Facturado:   @Moneda @Cash\n
                Efectivo Total:       @Moneda @ControlInterno\n
                --------------------------------------------\n
                Detalle de Pagos\n
                --------------------------------------------\n
                @pay_methods
                
                Total Facturado:      @Moneda @Total\n
                --------------------------------------------\n
                Detalle de Productos Facturados\n
                --------------------------------------------\n
                @TypeItem
                Total Facturado:      @Moneda @Total\n
                """

                balance = self.get_balance()

                templateInvoice = "@Empresa\n@Direccion\n@Telefono\nNIT: @Nit\n\n\n--------------------------------------------\n@DataAux\n--------------------------------------------\nID Turno:             @IDTurno\nID Apertura:          @IDApertura\nID Cierre:            @IDCierre\n--------------------------------------------\nFecha Apertura:       @FechaApertura\nFecha Cierre:         @FechaCierre\n\n--------------------------------------------\nFactura Inicio:       @FacturaInicio\nFactura Final:        @FacturaFinal\nTotal Facturas:       @TotalFacturas\n--------------------------------------------\nBase(Efectivo):       @Moneda @MontoInicial\nRecargas:             @Moneda @Recargas\nRetiros:              @Moneda @Vaciados\nFallos al devolver:   @Moneda @FallosAlDevolver\nEfectivo Facturado:   @Moneda @Cash\n                    ------------------------\n\nEfectivo Total:       @Moneda @ControlInterno\n--------------------------------------------\nDetalle de Pagos\n--------------------------------------------\n@PayDetailsTotal Facturado:      @Moneda @Total\n--------------------------------------------\nDetalle de Productos Facturados\n--------------------------------------------\n@TypeItem                    ------------------------\n\nTotal Facturado:      @Moneda @Total\n\n\n\n"
                enterprise = self.dataConfig["template_invoice"]

                invoiceStatusShift = templateInvoice
                invoiceStatusShift = invoiceStatusShift.replace("@Empresa", enterprise["enterprise"])
                invoiceStatusShift = invoiceStatusShift.replace("@Direccion", enterprise["address"])
                invoiceStatusShift = invoiceStatusShift.replace("@Telefono", enterprise["cellphone"])
                invoiceStatusShift = invoiceStatusShift.replace("@Nit", enterprise["nit"])

                invoiceStatusShift = invoiceStatusShift.replace("@DataAux", "Factura Cierre de Turno")

                invoiceStatusShift = invoiceStatusShift.replace("@IDTurno", str(turn["Id_Shift"]))
                invoiceStatusShift = invoiceStatusShift.replace("@IDApertura", str(turn["Id_PeopleOpening"]))
                invoiceStatusShift = invoiceStatusShift.replace("@IDCierre", str(turn["Id_PeopleClosed"]))

                invoiceStatusShift = invoiceStatusShift.replace("@FechaApertura", str(turn["InitialDate"]))
                invoiceStatusShift = invoiceStatusShift.replace("@FechaCierre", str(turn["FinalDate"]))

                invoiceStatusShift = invoiceStatusShift.replace("@FacturaInicio", str(turn["InitInvoice"]))
                invoiceStatusShift = invoiceStatusShift.replace("@FacturaFinal", str(turn["FinishInvoice"]))
                invoiceStatusShift = invoiceStatusShift.replace("@TotalFacturas", str(turn["TotalInvoices"]))

                invoiceStatusShift = invoiceStatusShift.replace("@Moneda", str(self.currency_symbol))
                invoiceStatusShift = invoiceStatusShift.replace("@MontoInicial", str(round(turn["InitialCash"])))
                invoiceStatusShift = invoiceStatusShift.replace("@Recargas", str(round(turn["Recharge"])))
                invoiceStatusShift = invoiceStatusShift.replace("@Retiros", str(round(turn["Withdrawal"])))
                invoiceStatusShift = invoiceStatusShift.replace("@Vaciados", str(round(turn["Emptied"])))
                invoiceStatusShift = invoiceStatusShift.replace("@FallosAlDevolver", str(round(turn["FailReturn"])))
                #invoiceStatusShift = invoiceStatusShift.replace("@Cash", str(round(turn["MethodsPay"])))
                invoiceStatusShift = invoiceStatusShift.replace("@ControlInterno", str(round(totalCash)))
                invoiceStatusShift = invoiceStatusShift.replace("@Total", str(round(turn["TotalwhitTaxes"])))

                detail=""
                cash=0
                for key in balance["pay_methods"]:
                    detail+=f"{key.ljust(22, ' ')}$ {balance['pay_methods'][key]['total']}\n"
                    if key[:2]=="0-": cash+=balance['pay_methods'][key]['total']
                    for keyp in balance["pay_methods"][key]["products"]:
                        detail+=f"{keyp.ljust(22, ' ')}({str(balance['pay_methods'][key]['products'][keyp]['cantidad']).rjust(2,' ')}) $ {balance['pay_methods'][key]['products'][keyp]['total']}\n"
                invoiceStatusShift = invoiceStatusShift.replace("@PayDetails", detail)
                invoiceStatusShift = invoiceStatusShift.replace("@Cash", str(cash))

                detail=""
                cash=0
                for key in balance["products"]:
                    detail+=f"{key.ljust(22, ' ')}({str(balance['products'][key]['cantidad']).rjust(3,' ')}) $ {balance['products'][key]['total']}\n"

                invoiceStatusShift = invoiceStatusShift.replace("@TypeItem", detail)


                retorno = True

                logging.info(f"Respuesta estatus turno: {message}")
                logging.info(invoiceStatusShift)

                Invoice_bytes  = invoiceStatusShift.encode()
                Invoice_Base64 = base64.b64encode(Invoice_bytes)

        except Exception as e:
            logging.error(f"Error al generar estatus turno: {e}")
            retorno = False
            invoiceStatusShift = ""
            return {"Error" : str(e)}
        finally:
            return retorno,invoiceStatusShift

    def addInvoiceTurn(self, dataShift:dict):
        try:
            url_shiftResult = self.dataPath + "/shiftControl/shiftResults/"
            idTransaction = dataShift.get("epoch")
            
            # Logs más descriptivos
            logging.info(f"addInvoiceTurn - Iniciando procesamiento para factura {dataShift.get('Prefix', '')}{dataShift.get('IdInvoice', '')}")
            
            # Verificar datos esenciales
            if not idTransaction:
                logging.error("addInvoiceTurn - Error: No se encontró campo 'epoch' en dataShift")
                idTransaction = int(time.time())
                dataShift["epoch"] = idTransaction
                
            if "epoch" in dataShift:
                dataShift.pop("epoch")
            
            totalItems = dataShift.get("TotalItems", {})
            logging.info(f"addInvoiceTurn - TotalItems: {totalItems}")
            
            if "TotalItems" in dataShift:
                dataShift.pop("TotalItems")
            
            # Verificar campos esenciales
            required_fields = ["IdShift", "Prefix", "IdInvoice"]
            for field in required_fields:
                if field not in dataShift:
                    logging.error(f"addInvoiceTurn - Error: Campo faltante {field}")
                    return
            
            # Crear estructura de carpetas
            shiftPackage = os.path.join(url_shiftResult, str(dataShift['IdShift']))
            os.makedirs(shiftPackage, exist_ok=True)
            
            # Nombre del archivo de backup en shiftResults
            nameInvoice = f"{dataShift['Prefix']}{dataShift['IdInvoice']}"
            backup_path = os.path.join(shiftPackage, nameInvoice + ".json")
            
            logging.info(f"addInvoiceTurn - Guardando backup en: {backup_path}")
            with open(backup_path, "w", encoding='utf-8') as backupShift:
                json.dump(dataShift, backupShift, indent=4, ensure_ascii=False)
            
            # Eliminar archivo pendiente si existe
            pending_file = os.path.join(self.pendientes_folder, nameInvoice + ".json")
            if os.path.exists(pending_file):
                try:
                    os.remove(pending_file)
                    logging.info(f"addInvoiceTurn - Archivo pendiente eliminado: {pending_file}")
                except Exception as e:
                    logging.warning(f"addInvoiceTurn - No se pudo eliminar archivo pendiente {pending_file}: {e}")
            else:
                logging.info(f"addInvoiceTurn - No existe archivo pendiente: {pending_file}")
            
            # Insertar factura en transacciones
            trans_name = f"billingResult-{idTransaction}"
            os.makedirs(os.path.dirname(self.saveBilling), exist_ok=True)
            trans_path = os.path.join(self.saveBilling, trans_name + ".json")
            
            logging.info(f"addInvoiceTurn - Guardando transacción en: {trans_path}")
            with open(trans_path, "w", encoding='utf-8') as uploadShift:
                json.dump(dataShift, uploadShift, indent=4, ensure_ascii=False)
            
            logging.info(f"addInvoiceTurn - Proceso completado exitosamente para factura {nameInvoice}")
            
        except Exception as e:
            logging.error(f"addInvoiceTurn - Error crítico: {str(e)}")
            logging.error(traceback.format_exc())

    def generateTemplateTurn(self):

        self.getSettings()
        # !JSON CONTROL INTERNAL SHIFTS

        timestamp    = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        currentShift = {}
        # DATA SHIFT
        currentShift["Id_Shift"]    = 0
        currentShift["Id_Device"]   = int(self.idDevice)
        currentShift["InitialDate"] = str(timestamp)
        currentShift["FinalDate"]   = ""
        currentShift["Status"]      = 0

        # DATA OPEN SHIFT
        # currentShift["InitInvoice"]         = self.resolution["actualIndexResolution"]
        currentShift["InitInvoice"]         = 0
        currentShift["FinishInvoice"]       = 0
        currentShift["Id_PeopleOpening"]    = 0
        currentShift["InitialCash"]         = 0
        currentShift["InternalControl"]     = 0
        currentShift["Diference"]           = 0


        #DATA CLOSE SHIFT
        currentShift["Id_PeopleClosed"] = 0
        currentShift["FinalCash"]       = 0
        currentShift["MethodsPay"]      = {}

        #TOTAL INFO SHIFT
        currentShift["TotalInvoices"]      = 0
        currentShift["TotalTaxes"]         = 0
        currentShift["TotalwhitTaxes"]     = 0
        currentShift["TotalwhitOutTaxes"]   = 0
        currentShift["FailReturn"]          = 0
        currentShift["List_FailReturn"]     = []
        currentShift["Emptied"]             = 0
        currentShift["List_Emptied"]        = []
        currentShift["Withdrawal"]          = 0
        currentShift["List_Withdrawal"]     = []
        currentShift["Recharge"]            = 0
        currentShift["List_Recharge"]       = []
        currentShift["StackControl"]        = 0
        currentShift["Billetes_Stacked"]    = {}
        currentShift["LastInsert"]          = str(timestamp)
        currentShift["TotalItems"]          = {}

        currentShift["NextIdShift"] = 1

        return currentShift

    def aux_fail_to_pay(self, idInvoice, pay_details, *args):
        if pay_details.get("notDispense",0) > 0:
            separator =  "-"*40
            data_template = self.dataConfig["template_invoice"]
            sub_receipt = f"\x1B\x61\x30{'-'*48}\n@Empresa\nNIT: @Nit\n{separator}\nFactura N. @IdTerminal-@IdInvoice\nFecha de emisión: @FechaFactura\n{separator}\n@FailName: @FalloAlPagar\n{separator}\n@SubAuxText\n"

            sub_receipt = sub_receipt.replace("@Empresa",data_template["enterprise"])
            sub_receipt = sub_receipt.replace("@Nit",data_template["nit"])

            sub_receipt = sub_receipt.replace("@IdTerminal",self.resolution["prefijo"])
            sub_receipt = sub_receipt.replace("@IdInvoice",str(idInvoice))
            sub_receipt = sub_receipt.replace("@FechaFactura",datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

            sub_receipt = sub_receipt.replace("@FailName",data_template.get("FailName","Importe"))
            sub_receipt = sub_receipt.replace("@FalloAlPagar","${:,.2f}".format(int(pay_details["notDispense"])))

            sub_receipt = sub_receipt.replace("@SubAuxText",data_template.get("SubAuxText",""))
        else:
            sub_receipt = ""
        return sub_receipt

    #GESTOR RESOLUCION
    def checkResolution(self)-> bool:
        logging.info(self.resolution)
        if not self.resolution: return False,"No existe"

        indexResolution      = self.resolution["actualIndexResolution"]
        dateNow              = datetime.now()
        initResolution       = self.resolution["startNumber"]
        finishResolution     = self.resolution["endNumber"]
        initDateResolution   = self.resolution["startDate"]
        finishDateResolution = self.resolution["endDate"]

        initDateResolution   = datetime.strptime(initDateResolution, '%Y-%m-%d')
        finishDateResolution = datetime.strptime(finishDateResolution, '%Y-%m-%d')

        dateNow     = datetime.strftime(dateNow,'%Y-%m-%d')
        dateNow     = datetime.strptime(dateNow,'%Y-%m-%d')
        dateInvoice = dateNow
        infoMessage = ""

        check = False
        if dateInvoice >= initDateResolution and dateInvoice <= finishDateResolution :
            logging.info("FACTURA DENTRO DE FECHAS DE RESOLUCION")
            if indexResolution >= initResolution and indexResolution <= finishResolution:
                logging.info(f"FACTURA {indexResolution} de {finishResolution}")

                alertResolution = (indexResolution * 100) / finishResolution

                if alertResolution == 90: logging.info("Consecutivos de la resolucion al 10% de finalizar")

                check = True
            elif indexResolution < initResolution:
                
                logging.info("VALIDAR RESOLUCION")
                infoMessage = "VALIDAR RESOLUCION"
                check = False
                
            else:
                logging.info("RESOLUCION SIN CONSECUTIVOS")
                infoMessage = "RESOLUCION SIN CONSECUTIVOS"
                check = False
        else:
            logging.info("FACTURA FUERA DE FECHAS DE RESOLUCION")
            infoMessage = "FACTURA FUERA DE FECHAS DE RESOLUCION"
            check       = False

        return check, infoMessage

    def updateResolution (self)-> None:
        try:
            url_ControlShift  = f"{self.dataPath}/shiftControl/"
            if not os.path.isdir(url_ControlShift): os.makedirs(url_ControlShift)

            if os.path.exists(self.nextInvoice):

                # *Get Data Resolution
                with open(self.nextInvoice, "r") as file: self.resolution = json.load(file)
                file.close()

            else:
                logging.info(" ----------------> No se encontro Resolucion Local")
                logging.info(" ----------------> Creando Resolucion Local ...")

                nextinvoice = {
                                "prefijo": "Empty",
                                "numResolution": "0000",
                                "startNumber": 1,
                                "endNumber": 1,
                                "orderToUse": 1,
                                "startDate": "2000-01-01",
                                "endDate": "2000-01-01",
                                "actualIndexResolution": 0
                                }

                with open(self.nextInvoice, "w") as createResolution: json.dump(nextinvoice, createResolution, indent = 4)
                createResolution.close()

                with open(self.nextInvoice,'r') as file: self.resolution = json.load(file)
                file.close()

            if self.resolution:
                if self.resolution.get("prefijo") == "Empty" or self.resolution.get("actualIndexResolution") == 0:

                    self.dataGovernor = self.configService()

                    if self.dataGovernor:
                         # * Update Local Resolution
                        nextinvoice = {}
                        nextinvoice['prefijo']       = self.dataGovernor["Prefijo"]
                        nextinvoice['numResolution'] = self.dataGovernor["ResolutionNumber"]
                        nextinvoice['startNumber']   = self.dataGovernor["BillingIniNumber"]
                        nextinvoice['endNumber']     = self.dataGovernor["BillingEndNumber"]
                        nextinvoice['startDate']     = self.dataGovernor["DateIniResolution"]
                        nextinvoice['endDate']       = self.dataGovernor["DateEndResolution"]
                        nextinvoice["actualIndexResolution"] = self.dataGovernor["BillingNumber"] + 1

                        with open(self.nextInvoice, "w") as updateResolution: json.dump(nextinvoice, updateResolution, indent = 4)
                        updateResolution.close()

                        logging.info((f" -------------> Resolucion actualizada"))
                        with open(self.nextInvoice,'r') as file: self.resolution = json.load(file)
                        file.close()
                    else:
                        logging.info(f" --------------> Ha ocurrido un error al Actualizar la resolucion")
                        logging.info(f" --------------> Se Usara resolucion local ")

                        with open(self.nextInvoice,'r') as file: self.resolution = json.load(file)
                        file.close()
                else:
                    with open(self.nextInvoice,'r') as file: self.resolution = json.load(file)
                    file.close()

        except Exception as e:
            currentShift     = str(e) + ": " + traceback.format_exc()
            logging.error(f"Error Actualizando Resolucion: {currentShift}")

    def configService(self) -> None:
        try:
            event = threading.Event()
            def on_message(client, topic, id, mcmd, session, raw1):
                logging.info("----------------------------")
                logging.info(f"ID      : {id}")
                logging.info(f"MCMD    : {mcmd}")
                logging.info(f"RESPONSE: {raw1}")
                logging.info("----------------------------")
                self.responseData = raw1
                event.set()

            self.responseData = None
            credential = {"id": self.idDevice }
            credential = json.dumps(credential)
            command    = "GETINVOICESTATUS"
            session    = self._mqtt.newsession(None)

            self._mqtt._callback[session] = on_message
            self._mqtt.sendcommand(self.topic,command,credential,session)
            logging.info(f"START: MQTT({self._mqtt})	Session Token({session})")
            event.wait(10)
            # i = 0
            # while not self.responseData:
            #     i += 1
            #     time.sleep(1)
            #     if i == 10 :
            #         logging.info("sin respuesta")
            #         break

            if self.responseData:
                settings = self.responseData.decode("utf-8")
                return eval(settings)
            else:
                logging.info("Sin Respuesta")

        except Exception as e:
            error = str(e) + ": " + traceback.format_exc()
            logging.error(f"Error Configurando Servicio Facturacion: {error}")

    # RECARGAS Y VACIADOS
    def moneyManager(self, dataInvoice:dict)-> str:
        # TEMPLATE INVOICE
        """
            --------------------------------------------\n
                @Tipo\n
            --------------------------------------------\n
                Usuario: @Usuario\n
                ID: @IdVaciado\n
            --------------------------------------------\n
                Cantidad           Denominacion         \n
            --------------------------------------------\n
                @DatosFactura\n\n
                                -------------------\n
                Valor :              $@Valor\n
            --------------------------------------------\n
                Motivo: @Motivo\n
                Fecha:  @Fecha\n
            --------------------------------------------\n
        """
        try:
            checkshift = self.checkTurn()

            if checkshift:
                templateInvoice = "--------------------------------------------\n    @Tipo\n--------------------------------------------\n    Usuario: @Usuario\n    ID: @IdVaciado\n--------------------------------------------\n    Cantidad           Denominacion         \n--------------------------------------------\n@DatosFactura\n                    -------------------\n    Valor :             $@Valor\n--------------------------------------------\n    Motivo: @Motivo\n    Fecha:  @Fecha\n--------------------------------------------\n"

                #* Get DATATURN
                # url_ControlShift  = f"{self.dataPath}shiftControl/controlShift.json"
                with open(self.controlShift) as file: turn = json.load(file)
                file.close()
                status = True
                is_fail_to_pay = False
                invoice = ""
                match dataInvoice.get("typeInvoice"):
                    case 1:
                        logging.info("---> Realizando Recarga")
                        typeInvoice = "Recarga"
                        turn["Recharge"] += dataInvoice['total']
                        turn["InternalControl"] += dataInvoice['total']
                        turn["List_Recharge"].append({"time":datetime.strftime(datetime.now(),"%Y-%m-%d %H:%M:%S"), "value":dataInvoice["total"]})
                    case 2:
                        logging.info("---> Realizando Vaciado")
                        typeInvoice     = "Vaciado"
                        turn["Emptied"] += dataInvoice['total']
                        turn["InternalControl"] -= dataInvoice['total']
                        turn["List_Emptied"].append({"time":datetime.strftime(datetime.now(),"%Y-%m-%d %H:%M:%S"), "value":dataInvoice["total"]})
                    case 4:
                        logging.info("---> Llegó fallo al pagar")
                        typeInvoice     = "Fallo al pagar"
                        if dataInvoice.get("aux_data"):
                            is_fail_to_pay = True
                            turn["InternalControl"] += dataInvoice["aux_data"]["notDispense"]
                            turn["FailReturn"]      += dataInvoice["aux_data"]["notDispense"]
                            turn["List_FailReturn"].append({"time":datetime.strftime(datetime.now(),"%Y-%m-%d %H:%M:%S"), "value":dataInvoice["aux_data"]["notDispense"]})
                    case 5:
                        logging.info("---> Realizando Retiro")
                        typeInvoice     = "Retiro"
                        turn["Withdrawal"] += dataInvoice['total']
                        turn["InternalControl"] -= dataInvoice['total']
                        turn["List_Withdrawal"].append({"time":datetime.strftime(datetime.now(),"%Y-%m-%d %H:%M:%S"), "value":dataInvoice["total"]})
                    case 6:
                        logging.info(f"---> Billete de {dataInvoice['total']} al stack")
                        typeInvoice     = "Billetes_Stacked"
                        turn["StackControl"] += dataInvoice["total"]
                        if "Billetes_Stacked" not in turn.keys():
                            turn["Billetes_Stacked"] = {}
                        turn["Billetes_Stacked"][str(dataInvoice["total"])] = turn["Billetes_Stacked"].get(str(dataInvoice["total"]), 0) + 1
                    case __:
                        logging.info(f"---> No existe el tipo de factura seleccionada - {dataInvoice.get('typeInvoice')=}")
                        status = False

                idRecharge = int(datetime.timestamp(datetime.now()))
                dateInvoce = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                infoInvoice =""
                if status:
                    if is_fail_to_pay:
                        infoInvoice += f"  Dinero a entregar: $ {str(dataInvoice['aux_data']['change']).rjust(7,' ')}\n"
                        infoInvoice += f"  Dinero entregado:  $ {str(dataInvoice['aux_data']['change']-dataInvoice['aux_data']['notDispense']).rjust(7,' ')}\n"
                        infoInvoice += f"  Dinero faltante:   $ {str(dataInvoice['aux_data']['notDispense']).rjust(7,' ')}\n"
                        # formatDataAux["Efectivo"]        = invoice["PaymentDetails"]["valuePaid"]
                        # formatDataAux["Cambio"]          = invoice["PaymentDetails"]["change"]
                        # formatDataAux["Dinero Faltante"] = invoice["PaymentDetails"]["notDispense"]
                    else:
                        for money in dataInvoice["money"]:

                            denomination = int(money["Denominacion"])
                            amount       = str(money["Cantidad"])

                            # if len(amount) == 1:
                            #     infoInvoice += f"       {amount}{('$'+str(denomination)).rjust(21)}\n"
                            # if len(amount) == 2:
                            #     infoInvoice += f"       {amount}{('$'+str(denomination)).rjust(20)}\n"
                            # if len(amount) == 3:
                            infoInvoice += f"       {amount}{('$'+str(denomination)).rjust(18 + len(amount))}\n"

                    invoice = templateInvoice
                    invoice = invoice.replace("@Tipo", f"{typeInvoice}")
                    invoice = invoice.replace("@Usuario", str(self.idDevice))
                    invoice = invoice.replace("@IdVaciado", str(idRecharge))
                    invoice = invoice.replace("@DatosFactura", infoInvoice)
                    invoice = invoice.replace("@Valor", f"{dataInvoice['total']}")
                    invoice = invoice.replace("@Motivo", dataInvoice["textInvoice"])
                    invoice = invoice.replace("@Fecha", dateInvoce)

                        #* UPDATE DATA TURN
                    with open(self.controlShift,'w', encoding='utf-8') as file: json.dump(turn, file, indent=4)
                    file.close()

                    # !JSON SEND MoneyManager
                    invoiceManager = {}
                    #* DATA MoneyManager
                    dateBilling    = datetime.now()
                    epoch          = int(datetime.timestamp(dateBilling)*1)

                    invoiceManager = {}
                    invoiceManager["JsonType"] =  4
                    invoiceManager["Administrativa"]   = {}
                    invoiceManager["Administrativa"]["Id_Device"]              =  int(self.idDevice)
                    invoiceManager["Administrativa"]["Id_BillTransaction"]     =  f"{self.idDevice}{epoch}"
                    invoiceManager["Administrativa"]["Id_BillTransactionType"] =  dataInvoice["typeInvoice"]
                    invoiceManager["Administrativa"]["Id_Shift"]               =  int(turn["Id_Shift"])
                    invoiceManager["Administrativa"]["Id_People"]              =  turn["Id_PeopleOpening"]
                    invoiceManager["Administrativa"]["Date"]                   =  str(dateInvoce)
                    invoiceManager["Administrativa"]["Value"]                  =  dataInvoice['total']
                    invoiceManager["Administrativa"]["AuxValue"]               =  dataInvoice.get("admin_card","0")
                    invoiceManager["Administrativa"]["Text"]                   =  str(dataInvoice["textInvoice"])

                    nameInvoice = f"shiftResult-{int(time.time()*1000)}"
                    with open(self.saveBilling + str(nameInvoice) + '.json','w') as sendInvoice: json.dump(invoiceManager, sendInvoice, indent= 4)
                    sendInvoice.close()

                    invoiceManager["Receipt"] =  str(invoice)

            else:
                logging.info("---> El turno no fue encontrado")
                status         = False
                invoiceManager = ""

        except Exception as e:
            error   = str(e) + ": " + traceback.format_exc()
            logging.error(f"Ha ocurrido un error en moneyManager: --> {error}")
            status = False

        finally: return status, invoiceManager

    def stackControl(self, totalAmount, type) -> None:
        try:
            # url_ControlShift  = f"{self.dataPath}shiftControl/controlShift.json"
            with open(self.controlShift) as file: turn = json.load(file)
            file.close()

            if type == 1:
                turn["StackControl"] += totalAmount
                logging.info(f"SE ALMACENO EN STACK: ${totalAmount}")
            if type == 2:
                turn["StackControl"] -= totalAmount
                logging.info(f"SE RETIRO DEL STACK: ${totalAmount}")
            if type == 2:
                turn["StackControl"]
                logging.info(f"Total en STACK: ${turn['StackControl']}")

            with open(self.controlShift,'w', encoding='utf-8') as file:
                json.dump(turn, file, indent=4)
            file.close()

            return turn["StackControl"]

        except Exception as e:
            logging.error(f"Ha Ocurrido un error --> StackControl {e}")

    def _save_invoice_to_database(self, invoice_data):
        """
        Guarda la factura en la base de datos SQL Server
        """
        try:
            logging.info("Guardando factura en base de datos...")
            
            # Conexión a la base de datos
            connection = QueriesSQLServer.create_connection()
            if not connection:
                logging.error("No se pudo conectar a la base de datos")
                return False
            
            # Extraer datos de la factura
            total = invoice_data.get("Total", 0)
            subtotal = invoice_data.get("Subtotal", 0) or total
            impuestos = invoice_data.get("TotalTaxes", 0)
            fecha_str = invoice_data.get("InvoiceDate", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            
            # Convertir string a datetime para SQL
            try:
                fecha = datetime.strptime(fecha_str, "%Y-%m-%d %H:%M:%S")
            except:
                fecha = datetime.now()
            
            # Método de pago y detalles
            metodo_pago = invoice_data.get("PaymentMethod", 0)
            detalles_pago = json.dumps(invoice_data.get("PaymentDetails", {}))
            
            # Datos de facturación
            id_factura = f"{invoice_data.get('Prefix', '')}-{invoice_data.get('IdInvoice', '')}"
            id_turno = invoice_data.get("IdShift", 1)
            consecutivo = invoice_data.get("IdInvoice", 0)
            
            # Receipt como texto
            receipt_text = invoice_data.get("Receipt", "")
            json_factura = json.dumps(invoice_data, ensure_ascii=False)

            username = invoice_data.get("username")

            if not username:
                raise ValueError("username no recibido en invoice_data")

            cursor = connection.cursor()
            cursor.execute("SELECT 1 FROM usuarios WHERE username = ?", (username,))
            if not cursor.fetchone():
                raise ValueError(f"Usuario '{username}' no existe en tabla usuarios")

            # Insertar en tabla ventas
            query_venta = """
            INSERT INTO ventas (
                total, fecha, username, 
                id_factura, id_turno, id_dispositivo, prefijo_resolucion, num_resolucion, 
                consecutivo, subtotal, impuestos, metodo_pago, detalles_pago, 
                receipt_data, json_factura
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            
            data_tuple = (
                total, 
                fecha, 
                username, 
                id_factura, 
                id_turno, 
                invoice_data.get("IdDevice", 1),
                invoice_data.get("Prefix", ""),
                invoice_data.get("numResolution", ""),
                consecutivo,
                subtotal,
                impuestos,
                metodo_pago,
                detalles_pago,
                receipt_text,
                json_factura
            )
            
            # Ejecutar inserción
            venta_id = QueriesSQLServer.execute_query(connection, query_venta, data_tuple)
            
            if venta_id:
                logging.info(f"Venta guardada en BD con ID: {venta_id}")
                
                # Guardar los items en ventas_detalle
                items = invoice_data.get("items", [])
                for item in items:
                    query_detalle = """
                    INSERT INTO ventas_detalle (id_venta, producto, precio, cantidad)
                    VALUES (?, ?, ?, ?)
                    """
                    
                    detalle_tuple = (
                        venta_id,
                        item.get("Id_Product", ""),
                        item.get("Total", 0),
                        1  # Cantidad - ajustar si tu sistema maneja cantidades
                    )
                    
                    QueriesSQLServer.execute_query(connection, query_detalle, detalle_tuple)
                
                logging.info(f"{len(items)} items guardados en ventas_detalle")
                return True
            else:
                logging.error("No se pudo obtener ID de venta insertada")
                return False
                
        except Exception as e:
            logging.error(f"Error al guardar en base de datos: {str(e)}")
            import traceback
            logging.error(traceback.format_exc())
            return False

if __name__ == "__mainx__":
    logging.basicConfig(level=logging.INFO,  format='%(levelname)s::%(asctime)s::%(module)s::%(funcName)s::line %(lineno)d %(message)s')

    # Test
    dataPath = "C:/mascotas/kiosTag/copia/python/kiosk_tag/data/"

    dataConfig = {
                    "Currency_symbol": "$",
                    "adjustment": 100,
                    "template_invoice":{
                        "enterprise": "BOREALIX SAS.",
                        "nit": "901131640",
                        "address": "Calle 128 # 50 - 52, Bogota D.C.",
                        "cellphone":"(+57) 3167801948",
                        "footer": "NO SOMOS AUTORETENEDORES\nNO SOMOS GRANDES CONTRIBUYENTES\nREGIMEN COMUN\n\nGARANTIA DE 3 MESES POR FALLAS O DEFECTOS DE\nFABRICACION ENTREGADA POR EL PROVEEDOR\n"
                    }
                }

    settings = 1

    dataResolution = [
                        {
                            "BillinPrefix": "PET99",
                            "BillinResolution": "000231",
                            "BillinNumbreStart": 100,
                            "BillinNumberEnd": 500,
                            "BillinDateStart": "2022-12-01",
                            "BillinDateEnd": "2023-12-31"
                        }
                    ]
    saveBilling    = "C:/mascotas/kiosTag/copia/python/kiosk_tag/data/transactions/"
    dataOpen       = {"Id_People": 1 , "InitialCash": 0}
    dataClose      = {"Id_People": 1 , "FinalCash": 0}
    dataInvoice    = {
                    "isElectronic": False,
                    "Details": {
                        "Nombre":"placa prueba",
                        "Telefono":310235478,
                        "email": "NOEMAIL"
                    },
                    "Tax": [
                            {
                            "Id_Tax": 2,
                            "TaxValue": 19
                            }
                    ],
                    "items":[
                        {
                            "Id_Product": 11,
                            "description":"hueso grande",
                            "Total": 16000,
                            "taxes": [2],
                            "include":True,
                        }
                    ],
                    "PaymentMethod": 1,
                    "PaymentDetails":{
                                "valuePaid": 16000,
                                "change": 0,
                                "notDispense": 0
                    },
                    "Note": {
                        "Nombre":"nombretest",
                        "Telefono": 31254896,
                        "email": "NOEMAIL"
                    },
                }

    # Create INSTANCE
    invoicing = Service_invoicing()
    invoicing.start(dataPath,dataConfig, settings, dataResolution, saveBilling)
    invoicing.openTurn(dataOpen)

    for i in range(1,5):
        invoicing.invoice(dataInvoice)
        invoicing.checkTurn()
        sleep(4)

    invoicing.closeTurn(dataClose)
    pass


if __name__ == "__main__":
    config={"Currency_symbol": "$",
            "adjustment": 100,
            "template_invoice": {
                "enterprise": "CORPAUL\nCLINICA LAS AMERICAS",
                "nit": "890.981.683-8",
                "address": "Diagonal 75B 2A - 140",
                "cellphone": "",
                "footer": "\nNO SOMOS GRANDES CONTRIBUYENTES\t\t\t\nIVA Regimen Comun, Somos autorretenedores\nsegun resolucion 011990 del 06/11/2009.\nPolizas #010-10248 y #013-467890 Suramericana.\nSi tienes alguna PQRS,\nregistrala en el boton de PQRS de\nnuestro sitio web www.zonap.com.\nCuentas con 10 MINUTOS minutos para salir.\nGracias por tu visita.\n---\n\n"}
            }

    taxdata= {"TaxData": {"Tax": [{"Id_Tax": 1, "TaxValue": 19}]}}

    products=[{"product_id": 3, "product_type": 9, "description": "Tarjeta Perdida", "vehicle_type": 1, "validate": False, "value1": 15000, "value2": 0}, {"product_id": 4, "product_type": 8, "description": "Miscelaneo", "vehicle_type": 1, "validate": False, "value1": 0, "value2": 0}, {"product_id": 5, "product_type": 1, "description": "Mensual Carros ", "vehicle_type": 1, "validate": True, "value1": 152300, "value2": 0}, {"product_id": 6, "product_type": 1, "description": "Mensual Motos ", "vehicle_type": 2, "validate": True, "value1": 52800, "value2": 0}, {"product_id": 7, "product_type": 2, "description": "Pase Dia Motos", "vehicle_type": 2, "validate": True, "value1": 7200, "value2": 24}, {"product_id": 8, "product_type": 2, "description": "Pase Dia Carros", "vehicle_type": 1, "validate": True, "value1": 14000, "value2": 24}, {"product_id": 9, "product_type": 0, "description": "Americas Carros", "vehicle_type": 1, "validate": True, "value1": 0, "value2": 0}, {"product_id": 10, "product_type": 0, "description": "Americas Motos", "vehicle_type": 2, "validate": True, "value1": 0, "value2": 0}, {"product_id": 11, "product_type": 0, "description": "Promotora Carros", "vehicle_type": 1, "validate": True, "value1": 0, "value2": 0, "zone": 2}, {"product_id": 12, "product_type": 0, "description": "Promotoras Motos", "vehicle_type": 2, "validate": True, "value1": 0, "value2": 0, "zone": 2}]
    pay_methods={0:"Efectivo",1:"Credibanco",2:"Redeban",3:"Flypass",4:"Nequi",5:"Bancolombia",6:"Daviplata",7:"Transferencia"}
    
    inv=Invoicing()
    inv.start("/python/PPA/data/",config,3,"/python/PPA/data/transactions/",None, "transaction",products=products, pay_methods=pay_methods)
    print (inv.balanceTurn()) ####13