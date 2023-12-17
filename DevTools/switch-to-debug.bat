@echo off
set ROOT=%~dp0

pushd %ROOT%
%ROOT%\..\Run.bat conan install conanfile-debug.txt --settings=build_type=Debug -c tools.cmake.cmaketoolchain:generator=Ninja
popd
