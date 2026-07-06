@echo off
setlocal EnableExtensions
cd /d "%~dp0"

if "%~1"=="" goto :usage
set "TARGET=%~1"
set "CLEAN=%~2"

if /I "%TARGET%"=="sil" (
  set "CFG_PRESET=sil-release"
  set "BLD_PRESET=sil-release"
  set "BUILD_DIR=%~dp0build-sil-release"
) else if /I "%TARGET%"=="gtest" (
  set "CFG_PRESET=gtest-release"
  set "BLD_PRESET=gtest-release"
  set "BUILD_DIR=%~dp0build-gtest-release"
) else (
  echo ERROR: Unknown target "%TARGET%"
  goto :usage
)

where conan >nul 2>&1
if errorlevel 1 (
  echo ERROR: Conan is not installed or not in PATH.
  exit /b 1
)

if exist "%USERPROFILE%\.conan2\profiles\default" (
  findstr /b /c:"compiler=" "%USERPROFILE%\.conan2\profiles\default" >nul 2>&1
  if errorlevel 1 (
    echo WARNING: No C++ compiler entry found in the Conan default profile.
    echo If Visual Studio is already installed, this may just be a stale
    echo profile - continuing anyway. The conan install step below will
    echo report the real error if a toolchain genuinely cannot be found.
  )
)

if /I "%CLEAN%"=="clean" (
  echo Cleaning %BUILD_DIR% ...
  if exist "%BUILD_DIR%" rmdir /s /q "%BUILD_DIR%"
)

echo Installing Conan dependencies...
conan install . --output-folder "%BUILD_DIR%" --build=missing -s build_type=Release
if errorlevel 1 exit /b 1

echo Configuring preset %CFG_PRESET% ...
cmake --preset %CFG_PRESET%
if errorlevel 1 exit /b 1

echo Building preset %BLD_PRESET% ...
cmake --build --preset %BLD_PRESET%
if errorlevel 1 exit /b 1

if /I "%TARGET%"=="gtest" (
  echo Running tests...
  ctest --preset gtest-release
  if errorlevel 1 exit /b 1
)

echo.
echo Build finished for target: %TARGET%
exit /b 0

:usage
echo Usage: build.bat ^<sil^|gtest^> [clean]
exit /b 1
