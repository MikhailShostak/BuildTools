@echo off
set ROOT=%~dp0

call %ROOT%\Run.bat python %ROOT%\Conan\tools.py %*
