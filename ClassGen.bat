@echo off

if exist "W:\Projects\ClassGen\.Build\ClassGenCompiler\Package\conanrun.bat" (
    call W:\Projects\ClassGen\.Build\ClassGenCompiler\Package\conanrun.bat
)

if exist "W:\Projects\ClassGen\.Build\ClassGenCompiler\Debug\ClassGenCompiler.exe" (
    REM call W:\Projects\ClassGen\.Build\ClassGenCompiler\Debug\ClassGenCompiler.exe %*
)
