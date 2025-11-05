import io
import os
import logging as logs
import win32ui
import win32print

from logging.handlers   import TimedRotatingFileHandler

from PIL import Image, ImageWin

class Printer():
    justify_right   = b"\x1B\x61\x02"
    justify_center  = b"\x1B\x61\x01"
    justify_left    = b"\x1B\x61\x00"
    em_mode_on      = b"\x1B\x21\x30"
    em_mode_off     = b"\x1B\x21\x0A\x1B\x45\x0A"
    bold_on         = b"\x1B\x45\x0D"
    bold_off        = b"\x1B\x45\x0A"
    character_codes = b"\x1B\x74\x10" #WPC1252
    characters      = b"\x1B\x52\x0C" #conjunto de caracteres latino

    def __init__(self) -> None:
        pass

    def print(self, to_print: list, name = "Impresión_Python"):
        res = False
        try: 
            self.impresora_p = win32print.GetDefaultPrinter()
            self.impresora = win32print.OpenPrinter(self.impresora_p)
            self.printer_info = win32print.GetPrinter(self.impresora,2)
            
            attributes = self.printer_info['Attributes']

            # Atributos de conectividad
            PRINTER_ATTRIBUTE_WORK_OFFLINE = 0x00000400
            PRINTER_ATTRIBUTE_OFFLINE = 0x00000080

            # Verificar si está desconectada
            is_offline = attributes & PRINTER_ATTRIBUTE_OFFLINE
            is_working_offline = attributes & PRINTER_ATTRIBUTE_WORK_OFFLINE

            if is_offline or is_working_offline:
                logs.warning("Impresora desconectada")
                win32print.ClosePrinter(self.impresora)
                return True

            win32print.StartDocPrinter(self.impresora, 1, (name, None, "RAW"))
            win32print.StartPagePrinter(self.impresora)

            for e in to_print:
                if e["data"] != "":
                    match e["type"]:
                        case "text":
                            logs.info(f"Texto a imprimir: {e['data']}")
                            match e.get("align","left"):
                                case "left":
                                    align = self.justify_left
                                case "center":
                                    align = self.justify_center
                                case "right":
                                    align = self.justify_right

                            em_mode = self.em_mode_off
                            if e.get("em_mode"): em_mode = self.em_mode_on

                            bold = self.bold_off
                            if e.get("bold"): bold = self.bold_on

                            self.print_text(self.characters + align + em_mode + bold + e["data"].encode("latin-1"))
                        case "qr":
                            logs.info(f"QR a imprimir: {e['data']}")
                            self.print_qr_o(e["data"], e["size"])
                        case "image":
                            logs.info("Pendiente por ajuste de la impresión de imagenes")
                            # self.print_image(e["data"])
                    # win32print.WritePrinter(self.impresora, "\n\n".encode())


            win32print.WritePrinter(self.impresora, b"\n\n\n\n\n\n\n\n")
            win32print.WritePrinter(self.impresora, b"\x1B\x69")
            win32print.WritePrinter(self.impresora, bytes([27, 112, 48, 55, 121]))
            win32print.EndPagePrinter(self.impresora)
            win32print.EndDocPrinter(self.impresora)
            win32print.ClosePrinter(self.impresora)
            res = True
        except Exception as e:
            logs.error(f"Error: {e}")
        finally:
            return res

    def print_text(self, text_encode):
        win32print.WritePrinter(self.impresora, text_encode)

    def print_qr(self, to_qr:str, size:int = 6):
        win32print.WritePrinter(self.impresora, b"\n")
        qr_model        = b"\x32" # 31 or 32
        qr_size         = bytes([size])
        qr_eclevel      = b"\x49" # error correction level (30, 31, 32, 33 - higher)
        qr_data         = b'\n' + to_qr.encode('utf-8')
        qr_pL           = bytes([(len(qr_data) + 3) % 256])
        qr_pH           = bytes([int((len(qr_data) + 3) / 256)])
        qrToPrint = (self.justify_center + # Centralizar texto
                    b"\x1D\x28\x6B\x04\x00\x31\x41" + qr_model + b"\x00" + # Select the model
                    b"\x1D\x28\x6B\x03\x00\x31\x43" + qr_size + # Size of the model
                    b"\x1D\x28\x6B\x03\x00\x31\x45" + qr_eclevel + # Set n for error correction
                    b"\x1D\x28\x6B" + qr_pL + qr_pH + b"\x31\x50\x30" + qr_data + # Store data
                    b"\x1D\x28\x6B\x03\x00\x31\x51\x30" + b'\n')
        
        win32print.WritePrinter(self.impresora, qrToPrint)

    def print_qr_o(self, to_qr:str, size:int = 8):
        win32print.WritePrinter(self.impresora, b"\n")
        buffer_print = io.BytesIO()

        # Add \n
        buffer_print.write(b'\n')

        qr_data = to_qr.encode('utf-8')

        # Store len - QRLen plus 3 auxiliar bytes in the array
        store_len = len(qr_data) + 3
        store_pl = store_len % 256
        store_ph = store_len // 256

        # Center text
        buffer_print.write(bytes([0x1b, 0x61, 0x01]))

        # Function 180
        # QR storing
        buffer_print.write(bytes([0x1D, 0x28, 0x6B, store_pl, store_ph, 0x31, 0x50, 0x30]))
        buffer_print.write(qr_data)

        # Function 169
        # Correction level low - last digit 48
        buffer_print.write(bytes([0x1D, 0x28, 0x6B, 0x03, 0x00, 0x31, 0x45, 48]))
        
        # Function 167
        # Size of module - last digit - 5
        buffer_print.write(bytes([0x1D, 0x28, 0x6B, 0x03, 0x00, 0x31, 0x43, size]))
        
        # Function 165
        # Select the model
        # Model 50 -> 2
        buffer_print.write(bytes([0x1D, 0x28, 0x6B, 0x04, 0x00, 0x31, 0x41, 50, 0]))

        # Function 181
        # Print the QR
        # Last data - M -> Defined by the documentation
        buffer_print.write(bytes([0x1D, 0x28, 0x6B, 0x03, 0x00, 0x31, 0x51, 48]))

        # Add lines
        buffer_print.write(b'\n\n')

        # Left Align again
        buffer_print.write(bytes([0x1b, 0x61, 0x00]))
        win32print.WritePrinter(self.impresora, buffer_print.getvalue())

    def print_image(self, image_path):
        if os.path.exists(image_path):
            hDC = win32ui.CreateDC ()
            hDC.CreatePrinterDC (self.impresora_p)

            bmp = Image.open (image_path)

            hDC.StartDoc (image_path)
            hDC.StartPage ()

            dib = ImageWin.Dib(bmp)
            # BT Printer 385
            # SAT Printer 576

            height = (dib.size[1] * 576) // dib.size[0]
            dib.draw (hDC.GetHandleOutput (), (0,0,385,height))

            hDC.EndPage()
            hDC.EndDoc()
            hDC.DeleteDC()
        else:
            logs.info(f"Ruta {image_path} de la imagen no existe")

if __name__ == "__main__":
    folderLogs = os.getcwd() + "/logs"

    if not os.path.exists(folderLogs):
        os.mkdir(folderLogs)

    impresora = Printer()

    logs.basicConfig(
        level       = logs.INFO,
        format      = "%(asctime)s [%(levelname)s]    %(module)s:%(lineno)d    %(funcName)s    | %(message)s" ,
        datefmt     = '%Y-%m-%d %H:%M:%S',
        handlers    = [TimedRotatingFileHandler(folderLogs + "/logs.log", when    = "d", interval    = 1, backupCount    = 3), logs.StreamHandler()]
        )

    to_print = [{"type":"text","data":"ESTO VA ARRIBA"},{"type":"qr","data":"-QR-", "size":8},{"type":"text","data":"ESTO VA ABAJO\n","align":"right", "em_mode":True, "bold": True},{"type":"text","data":"OTRO TEXTO","align":"center", "bold": True}]
    # to_print = [{"type":"image","data":"C:/Gobernador/Apps/CI_AppPersonas/screens/resources/Logo-CI24.png"},{"type":"text","data":"ESTO VA ARRIBA"},{"type":"qr","data":"-QR-"},{"type":"text","data":"ESTO VA ABAJO","align":"right"}]
    # to_print = [{"type":"image","data":"C:/Gobernador/Apps/CI_AppPersonas/screens/resources/Logo-CI24.png"}]
    
    impresora.print(to_print)