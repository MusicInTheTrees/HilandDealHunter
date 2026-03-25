@echo off
echo Cleaning previous builds...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist HilandDealHunter.spec del HilandDealHunter.spec

echo Installing dependencies...
pip install requests beautifulsoup4 pyinstaller

echo Packaging Hiland's Cigars Deal Hunter into a standalone executable...
pyinstaller --noconsole --onefile --name HilandDealHunter hilands_deals.py

echo.
echo Build complete! Check the "dist" folder for HilandDealHunter.exe.
pause