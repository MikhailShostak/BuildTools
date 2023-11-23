@echo off
set ROOT=%~dp0

echo Initializing .venv...
python -m venv %ROOT%\.venv

echo Activating .venv...
call %ROOT%\.venv\Scripts\activate.bat

echo Checking python executables...
where python

echo Installing packages...
python -m pip install --upgrade pip

pip install -r %ROOT%\requirements.txt

pushd %ROOT%\DevTools
conan install .
popd

call %ROOT%\Terminal.bat

if errorlevel 1 pause
