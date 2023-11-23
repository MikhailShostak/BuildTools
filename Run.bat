@echo off
set ROOT=%~dp0
set CONAN_HOME=%ROOT%\.conan
set VS_VERSION=2022

call %ROOT%\DevTools\conanrun

REM call "%ProgramFiles%\Microsoft Visual Studio\%VS_VERSION%\Enterprise\VC\Auxiliary\Build\vcvars64.bat" >NUL
REM call "%ProgramFiles%\Microsoft Visual Studio\%VS_VERSION%\Professional\VC\Auxiliary\Build\vcvars64.bat" >NUL
REM call "%ProgramFiles%\Microsoft Visual Studio\%VS_VERSION%\Community\VC\Auxiliary\Build\vcvars64.bat" >NUL
call %ROOT%\.venv\Scripts\activate.bat >NUL

%*
