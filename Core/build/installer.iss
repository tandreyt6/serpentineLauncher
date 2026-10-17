#ifndef SourceDirectory
  #error SourceDirectory is required
#endif
#ifndef ReleaseVersion
  #error ReleaseVersion is required
#endif
#ifndef OutputDirectory
  #error OutputDirectory is required
#endif

[Setup]
AppId={{73D4BE7F-860C-4593-A82A-D6086A52204F}
AppName=Serpentine Launcher
AppVersion={#ReleaseVersion}
AppPublisher=Serpentine Launcher
AppPublisherURL=https://github.com/tandreyt6/serpentineLauncher
DefaultDirName={localappdata}\Programs\SerpentineLauncher
DefaultGroupName=Serpentine Launcher
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#OutputDirectory}
OutputBaseFilename=serpentineLauncher-{#ReleaseVersion}-windows-x64-setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\SerpantineLauncher.exe
CloseApplications=yes
RestartApplications=no
#if FileExists(SourceDirectory + "\LICENSE")
LicenseFile={#SourceDirectory}\LICENSE
#endif

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; Flags: unchecked

[Files]
Source: "{#SourceDirectory}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Serpentine Launcher"; Filename: "{app}\SerpantineLauncher.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\Serpentine Launcher"; Filename: "{app}\SerpantineLauncher.exe"; WorkingDir: "{app}"; Tasks: desktopicon
