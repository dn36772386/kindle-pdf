; Inno Setup 6 script
#define MyAppName "Kindless"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "Your Company"
#define MyAppEXE "KindlessUI.exe"

[Setup]
AppId={{C9A2C132-0E9F-4E0B-9F94-19C6075E2F8B}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputBaseFilename=Kindless-Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern

[Files]
; 事前に PyInstaller の成果物を dist\ 以下に用意
Source: "dist\Kindless\Kindless.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\KindlessUI\KindlessUI.exe"; DestDir: "{app}"; Flags: ignoreversion
; 既定の INI をユーザー毎に配置
Source: "kindless.simple.ini"; DestDir: "{userappdata}\Kindless"; DestName: "kindless.ini"; Flags: onlyifdoesntexist

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppEXE}"
Name: "{commondesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppEXE}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "デスクトップにショートカットを作成"; GroupDescription: "追加タスク:"; Flags: unchecked

[Run]
Filename: "{app}\{#MyAppEXE}"; Description: "起動"; Flags: nowait postinstall skipifsilent
