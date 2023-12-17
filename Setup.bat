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

echo Detecting conan profile...
set CONAN_HOME=%ROOT%\.conan
conan profile detect

echo Setting conan to use c++20...
pushd %ROOT%
powershell -Command "(Get-Content .conan/profiles/default) -replace 'compiler.cppstd=14', 'compiler.cppstd=20' | Set-Content .conan/profiles/default"
popd

echo Setting up Artifactory...
IF NOT DEFINED ARTIFACTORY_HOST set /p ARTIFACTORY_HOST="Enter Artifactory host (e.g., http://artifactory.example.com): "
IF NOT DEFINED ARTIFACTORY_USER set /p ARTIFACTORY_USER="Enter Artifactory username: "
IF NOT DEFINED ARTIFACTORY_PASSWORD set /p ARTIFACTORY_PASSWORD="Enter Artifactory password: "
conan remote add Artifactory %ARTIFACTORY_HOST%/artifactory/api/conan/conan-local
conan remote login --password %ARTIFACTORY_PASSWORD% Artifactory %ARTIFACTORY_USER%

echo Installing DevTools...
pushd %ROOT%\DevTools
conan install .
popd

call %ROOT%\Terminal.bat

if errorlevel 1 pause
