@echo off
set ROOT=%~dp0

pushd %ROOT%
%ROOT%\..\Run.bat conan install conanfile.txt --settings=build_type=Release -c tools.cmake.cmaketoolchain:generator=Ninja
popd
