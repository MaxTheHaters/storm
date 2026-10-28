param([switch]$SkipInstall)
$ErrorActionPreference = 'Stop'
$stormRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$stormPython = Join-Path $stormRoot '.venv\Scripts\python.exe'
$stormRuntime = [IO.Path]::GetFullPath((Join-Path $stormRoot 'local\launcher'))
$stormBuild = [IO.Path]::GetFullPath((Join-Path $stormRoot 'build\windows-launcher'))
foreach ($stormTarget in @($stormRuntime, $stormBuild)) {
    if (-not $stormTarget.StartsWith($stormRoot.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Build output must stay inside the project.'
    }
}

Push-Location $stormRoot
try {
    if (-not (Test-Path -LiteralPath $stormPython)) {
        python -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw 'Unable to create .venv.' }
    }
    if (-not $SkipInstall) {
        & $stormPython -m pip install -e . -r frontend/demo_light/requirements.txt pyinstaller pillow 'pyarrow<21'
        if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
    }
    New-Item -ItemType Directory -Force -Path $stormRuntime, $stormBuild | Out-Null
    $stormIcon = Join-Path $stormRuntime 'storm.ico'
    $stormIconProgram = @'
import sys
from PIL import Image, ImageDraw
image = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
draw = ImageDraw.Draw(image)
draw.rounded_rectangle((4, 4, 252, 252), radius=52, fill="#2869C7")
draw.polygon([(148, 28), (70, 140), (118, 140), (98, 228), (194, 108), (144, 108)], fill="white")
image.save(sys.argv[1], format="ICO", sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])
'@
    & $stormPython -c $stormIconProgram $stormIcon
    if ($LASTEXITCODE -ne 0) { throw 'Icon generation failed.' }
    & $stormPython -m PyInstaller --noconfirm --onedir --windowed --name STORM `
        --distpath $stormRuntime --workpath $stormBuild --specpath $stormBuild `
        --icon $stormIcon --exclude-module torch --exclude-module transformers `
        --exclude-module streamlit --exclude-module dspy --exclude-module knowledge_storm `
        (Join-Path $PSScriptRoot 'storm_launcher.py')
    if ($LASTEXITCODE -ne 0) { throw 'Launcher packaging failed.' }
    $stormExe = Join-Path $stormRuntime 'STORM\STORM.exe'
    [IO.File]::WriteAllText((Join-Path $stormRuntime 'STORM\project-root.txt'), $stormRoot, [Text.UTF8Encoding]::new($false))

    $stormShell = New-Object -ComObject WScript.Shell
    $stormDesktop = [Environment]::GetFolderPath('Desktop')
    $stormPrograms = [Environment]::GetFolderPath('Programs')
    foreach ($stormFolder in @($stormDesktop, $stormPrograms)) {
        $stormLink = Join-Path $stormFolder 'STORM.lnk'
        $stormShortcut = $stormShell.CreateShortcut($stormLink)
        if ((Test-Path -LiteralPath $stormLink) -and $stormShortcut.TargetPath -and $stormShortcut.TargetPath -ne $stormExe) {
            throw "A different STORM shortcut already exists at $stormLink; it was not overwritten."
        }
        $stormShortcut.TargetPath = $stormExe
        $stormShortcut.Arguments = '--project-root "' + $stormRoot + '"'
        $stormShortcut.WorkingDirectory = $stormRoot
        $stormShortcut.IconLocation = $stormExe + ',0'
        $stormShortcut.Description = 'STORM 繁體中文研究'
        $stormShortcut.Save()
    }
    Write-Output "Installed: $stormExe"
    Write-Output "Desktop shortcut: $(Join-Path $stormDesktop 'STORM.lnk')"
} finally {
    Pop-Location
}
