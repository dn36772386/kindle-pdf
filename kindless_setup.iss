; Inno Setup 6.4.3 用設定ファイル

#define MyAppName "Kindless"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Your Name"
#define MyAppURL "https://example.com"
#define MyAppExeName "Kindless.exe"

[Setup]
; アプリケーション情報
AppId={{8B5F6A2C-4E7D-4B3A-9C1E-2D3F4A5B6C7D}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}

; インストール先
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes

; 出力設定
OutputDir=installer
OutputBaseFilename=KindlessSetup_{#MyAppVersion}
SetupIconFile=icon.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

; 管理者権限不要
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

; アーキテクチャ設定
ArchitecturesInstallIn64BitMode=x64

[Languages]
Name: "japanese"; MessagesFile: "compiler:Languages\Japanese.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; メインプログラム（PyInstallerでビルドしたもの）
Source: "dist\Kindless\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

; 設定ファイル（初回のみコピー）
Source: "kindless.ini"; DestDir: "{userappdata}\Kindless"; Flags: onlyifdoesntexist

; 必要なPythonファイル（exe化に含まれない場合）
Source: "dataclass.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "WindowInfo.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "wxdialog.py"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
// 初回起動時の設定
procedure InitializeWizard();
begin
  // 日本語を優先
  if ActiveLanguage = 'japanese' then
  begin
    WizardForm.Caption := 'Kindless セットアップ';
  end;
end;

// アンインストール時の確認
function InitializeUninstall(): Boolean;
var
  ResultCode: Integer;
begin
  if ActiveLanguage = 'japanese' then
  begin
    Result := MsgBox('Kindlessをアンインストールしてもよろしいですか？' + #13#10 + 
                     '設定ファイルは保持されます。', 
                     mbConfirmation, MB_YESNO) = IDYES;
  end
  else
  begin
    Result := MsgBox('Are you sure you want to uninstall Kindless?' + #13#10 + 
                     'Configuration files will be preserved.', 
                     mbConfirmation, MB_YESNO) = IDYES;
  end;
end;

[UninstallDelete]
; アンインストール時にプログラムフォルダのみ削除（設定は残す）
Type: filesandordirs; Name: "{app}"