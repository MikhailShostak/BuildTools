@echo off
setlocal
set ROOT=%~dp0
set CONAN_HOME=%ROOT%\.conan
set VS_VERSION=2022
set "VS_EDITIONS=Enterprise Professional Community"

call %ROOT%\.venv\Scripts\activate.bat >NUL

where cmake.exe >NUL 2>&1
if %ERRORLEVEL% == 0 (
    goto End
)
for %%i in (%VS_EDITIONS%) do (
    if exist "%ProgramFiles%\Microsoft Visual Studio\%VS_VERSION%\%%i\VC\Auxiliary\Build\vcvars64.bat" (
        echo Using VS%VS_VERSION% %VS_EDITIONS%...
        call "%ProgramFiles%\Microsoft Visual Studio\%VS_VERSION%\%%i\VC\Auxiliary\Build\vcvars64.bat" >NUL
        goto End
    )
)
:End

call %ROOT%\DevTools\conanrun

%*
endlocal
