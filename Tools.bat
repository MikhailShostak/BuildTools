@echo off
set ROOT=%~dp0

call %ROOT%\Run.bat python -u %ROOT%\Conan\tools.py %*
