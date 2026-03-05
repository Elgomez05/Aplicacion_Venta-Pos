@echo off
echo Instalando dependencias...
pip install kivy pyinstaller pymssql Pillow

echo Compilando aplicación...
pyinstaller --name PuntoVentasPos ^
--noconsole ^
--onefile ^
--icon=Src/Asset/Img-venta-Pos.ico ^
--add-data "Src;Src" ^
--hidden-import "kivy" ^
--hidden-import "kivy.graphics" ^
--hidden-import "kivy.core.window" ^
--hidden-import "kivy.core.text" ^
--hidden-import "pymssql" ^
--hidden-import "PIL" ^
--hidden-import "logging" ^
main.py

echo Compilacion completada!
pause