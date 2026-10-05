; Inno Setup script: wraps the PyInstaller build (dist\OtterData) into OtterData-Setup-<version>.exe.
; Build: iscc /DAppVersion=1.0.0 packaging\installer.iss   (run after packaging\otterdata.spec)
; Installs per user (no administrator rights) under %LOCALAPPDATA%\Programs\Otter Data.
; Saved as UTF-8 with BOM so Inno Setup reads the Portuguese messages correctly.

#if VER < EncodeVer(6, 7, 0)
  #error Inno Setup 6.7 or newer is required (PNG wizard images and automatic dark mode).
#endif

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
; Same look as the app: its paper and dark backgrounds, logo and otter, following the
; Windows light or dark setting. Images come from scripts/build_installer_images.py.
WizardStyle=modern dynamic hidebevels
DisableWelcomePage=no
WizardBackColor=#F6F0E4
WizardBackColorDynamicDark=#151B1D
WizardImageFile=images\wizard-light-100.png,images\wizard-light-150.png,images\wizard-light-200.png,images\wizard-light-250.png
WizardImageFileDynamicDark=images\wizard-dark-100.png,images\wizard-dark-150.png,images\wizard-dark-200.png,images\wizard-dark-250.png
WizardSmallImageFile=images\wizard-small-100.png,images\wizard-small-150.png,images\wizard-small-200.png,images\wizard-small-250.png
WizardSmallImageFileDynamicDark=images\wizard-small-100.png,images\wizard-small-150.png,images\wizard-small-200.png,images\wizard-small-250.png
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
LicenseFile=..\LICENSE

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Messages]
english.WelcomeLabel2=This will install [name/ver] on your computer.%n%nAsk questions about your databases and spreadsheets in plain language: Otter Data writes read-only SQL, checks it before running and shows where every number comes from.
brazilianportuguese.WelcomeLabel2=Isto vai instalar o [name/ver] no seu computador.%n%nFaça perguntas sobre seus bancos de dados e planilhas em linguagem natural: o Otter Data escreve SQL somente leitura, confere antes de executar e mostra de onde vem cada número.

[CustomMessages]
english.Uninstall=Uninstall Otter Data
english.OpenApp=Open Otter Data
english.OllamaMissing=One more step: Otter Data uses Ollama to understand questions and write answers, and it is not installed yet. Download it from ollama.com and, for the default cloud model, run "ollama signin" in a terminal.
english.GetOllama=Download Ollama (opens ollama.com)
brazilianportuguese.Uninstall=Desinstalar Otter Data
brazilianportuguese.OpenApp=Abrir o Otter Data
brazilianportuguese.OllamaMissing=Falta um passo: o Otter Data usa o Ollama para entender as perguntas e escrever as respostas, e ele ainda não está instalado. Baixe em ollama.com e, para o modelo padrão na nuvem, rode "ollama signin" num terminal.
brazilianportuguese.GetOllama=Baixar o Ollama (abre ollama.com)

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
Filename: "https://ollama.com/download"; Description: "{cm:GetOllama}"; Flags: shellexec nowait postinstall skipifsilent; Check: NeedsOllama

[Code]
// Otter Data answers through Ollama. When it is missing, the finish page says so and offers a
// checked box that opens the download page (the app also explains it on the first question).
function NeedsOllama(): Boolean;
begin
  Result := not (FileExists(ExpandConstant('{localappdata}\Programs\Ollama\ollama.exe'))
    or FileExists(ExpandConstant('{pf}\Ollama\ollama.exe')));
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  if (CurPageID = wpFinished) and NeedsOllama() then
  begin
    WizardForm.FinishedLabel.Caption := WizardForm.FinishedLabel.Caption + #13#10#13#10
      + CustomMessage('OllamaMissing');
    // The label keeps its original height; grow it and move the checkboxes below the text.
    WizardForm.FinishedLabel.AdjustHeight();
    WizardForm.RunList.Top := WizardForm.FinishedLabel.Top + WizardForm.FinishedLabel.Height
      + ScaleY(12);
  end;
end;
