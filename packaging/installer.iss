; Inno Setup script — builds a true Windows installer (CodePal-Setup.exe)
; Compile with Inno Setup (iscc.exe) after running build_windows.py:
;     iscc packaging\installer.iss
;
; The script bundles the PyInstaller one-file executable (dist\CodePal.exe)
; and creates a Start Menu + Desktop shortcut.

[Setup]
AppName=CodePal AI 编程助手
AppVersion=1.0.0
AppPublisher=CodePal
DefaultDirName={pf}\CodePal
DefaultGroupName=CodePal
OutputDir=release
OutputBaseFilename=CodePal-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64
SetupIconFile=packaging\icon.ico

[Files]
Source: "dist\CodePal.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\CodePal"; Filename: "{app}\CodePal.exe"
Name: "{autodesktop}\CodePal"; Filename: "{app}\CodePal.exe"

[Run]
Filename: "{app}\CodePal.exe"; Description: "启动 CodePal"; Flags: nowait postinstall skipifsilent
