; Inno Setup script: wraps the PyInstaller build (dist\OtterData) into OtterData-Setup-<version>.exe.
; Build: iscc /DAppVersion=1.0.0 packaging\installer.iss   (run after packaging\otterdata.spec)
; Installs per user (no administrator rights) under %LOCALAPPDATA%\Programs\Otter Data.
; Saved as UTF-8 with BOM so Inno Setup reads the Portuguese messages correctly.

#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif

[Setup]
AppId={{6B1E2B8C-9F7A-4C55-9A2D-0D7E3C4A1F21}
AppName=Otter Data
AppVersion={#AppVersion}
AppVerName=Otter Data {#AppVersion}
AppPublisher=Rafael Costa
DefaultDirName={localappdata}\Programs\Otter Data
DefaultGroupName=Otter Data
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=OtterData-Setup-{#AppVersion}
SetupIconFile=..\frontend\assets\otter.ico
UninstallDisplayIcon={app}\OtterData.exe
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
LicenseFile=..\LICENSE

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[CustomMessages]
english.Uninstall=Uninstall Otter Data
english.OpenApp=Open Otter Data
english.OllamaMissing=Otter Data uses Ollama to chat and analyze.%nInstall it from https://ollama.com and, for the default cloud model, run "ollama signin".
brazilianportuguese.Uninstall=Desinstalar Otter Data
brazilianportuguese.OpenApp=Abrir o Otter Data
brazilianportuguese.OllamaMissing=O Otter Data usa o Ollama para conversar e analisar.%nInstale em https://ollama.com e, para o modelo padrão na nuvem, rode "ollama signin".

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\dist\OtterData\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Otter Data"; Filename: "{app}\OtterData.exe"
Name: "{group}\{cm:Uninstall}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Otter Data"; Filename: "{app}\OtterData.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\OtterData.exe"; Description: "{cm:OpenApp}"; Flags: nowait postinstall skipifsilent

[Code]
// Otter Data answers through Ollama; remind the user when it is not installed.
function OllamaInstalled(): Boolean;
begin
  Result := FileExists(ExpandConstant('{localappdata}\Programs\Ollama\ollama.exe'))
    or FileExists(ExpandConstant('{pf}\Ollama\ollama.exe'));
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if (CurStep = ssPostInstall) and (not OllamaInstalled()) and (not WizardSilent()) then
    MsgBox(CustomMessage('OllamaMissing'), mbInformation, MB_OK);
end;
