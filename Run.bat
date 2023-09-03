@echo off
set ROOT=%~dp0
set CONAN_HOME=%ROOT%\.conan
set VS_VERSION=2022

call "%ProgramFiles%\Microsoft Visual Studio\%VS_VERSION%\Professional\VC\Auxiliary\Build\vcvars64.bat"
call %ROOT%\.venv\Scripts\activate.bat

%*
