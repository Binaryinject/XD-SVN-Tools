param(
    [string]$Python = 'python',
    [switch]$SkipTests
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$repoRoot = Split-Path $PSScriptRoot -Parent
$version = (Get-Content -LiteralPath (Join-Path $repoRoot 'VERSION') -Raw).Trim()
if ($version -notmatch '^\d+\.\d+\.\d+([-.][A-Za-z0-9.-]+)?$') { throw 'Invalid VERSION.' }
if ($env:GITHUB_REF_TYPE -eq 'tag' -and $env:GITHUB_REF_NAME -ne ('v' + $version)) {
    throw 'Git tag must equal v<VERSION>.'
}
$runRoot = Join-Path $repoRoot ('.build\run-' + [Guid]::NewGuid().ToString('N'))
$artifactRoot = Join-Path $repoRoot 'artifacts'
$portableRoot = Join-Path $runRoot 'portable'
$appRoot = Join-Path $portableRoot 'XD-SVN-Tools'
$framework = Join-Path $env:SystemRoot 'Microsoft.NET\Framework64\v4.0.30319'
$compiler = Join-Path $framework 'csc.exe'
if (-not (Test-Path -LiteralPath $compiler)) { throw '.NET Framework C# compiler not found. Build on Windows x64 with .NET Framework 4.8.' }
New-Item -ItemType Directory -Force $runRoot, $artifactRoot | Out-Null
Push-Location $repoRoot
try {
    if (-not $SkipTests) {
        & $Python -m unittest discover -v
        if ($LASTEXITCODE -ne 0) { throw 'Tests failed.' }
    }
    & $Python -m PyInstaller --noconfirm --clean --windowed --onedir --name XD-SVN-Tools `
        --add-data ((Join-Path $repoRoot 'VERSION') + ';.') --distpath $portableRoot --workpath (Join-Path $runRoot 'pyinstaller') `
        --specpath $runRoot xd_svn.py
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller build failed.' }

    Copy-Item -LiteralPath LICENSE, THIRD_PARTY_NOTICES.txt, README.md, README.en.md -Destination $appRoot
    Copy-Item -LiteralPath licenses, docs -Destination $appRoot -Recurse
    Copy-Item -LiteralPath scripts\Register-TortoiseSVN.ps1 -Destination $appRoot
    $sourceRoot = Join-Path $appRoot 'source'
    New-Item -ItemType Directory -Force $sourceRoot | Out-Null
    Get-ChildItem -LiteralPath $repoRoot -Filter '*.py' -File | Copy-Item -Destination $sourceRoot
    Copy-Item -LiteralPath VERSION, requirements-build.txt, LICENSE, README.md, README.en.md -Destination $sourceRoot
    Copy-Item -LiteralPath installer, scripts, licenses, docs -Destination $sourceRoot -Recurse
    $copying = & $Python -c "from pathlib import Path; import PyInstaller; print(Path(PyInstaller.__file__).parent / 'COPYING.txt')"
    if ($LASTEXITCODE -ne 0) { throw 'Could not locate PyInstaller license.' }
    if (Test-Path -LiteralPath $copying) { Copy-Item -LiteralPath $copying -Destination (Join-Path $appRoot 'licenses\runtime\PyInstaller-COPYING.txt') }
    $pythonLicense = & $Python -c "from pathlib import Path; import sys; print(Path(sys.base_prefix) / 'LICENSE.txt')"
    if ($LASTEXITCODE -ne 0) { throw 'Could not locate Python license.' }
    if (Test-Path -LiteralPath $pythonLicense) { Copy-Item -LiteralPath $pythonLicense -Destination (Join-Path $appRoot 'licenses\runtime\CPython-LICENSE.txt') -Force }

    $template = Get-Content -LiteralPath installer\Setup.cs -Raw
    if (-not $template.Contains('__APP_VERSION__')) { throw 'Installer version placeholder missing.' }
    $generated = Join-Path $runRoot 'Setup.cs'
    [System.IO.File]::WriteAllText($generated, $template.Replace('__APP_VERSION__', $version), [System.Text.UTF8Encoding]::new($false))
    $references = @('/r:System.Windows.Forms.dll', '/r:System.Drawing.dll', '/r:Microsoft.CSharp.dll', ('/r:' + (Join-Path $framework 'System.IO.Compression.dll')))
    & $compiler /nologo /target:winexe /platform:x64 /define:UNINSTALLER ('/out:' + (Join-Path $appRoot 'XD-SVN-Tools-Uninstall.exe')) @references $generated
    if ($LASTEXITCODE -ne 0) { throw 'Uninstaller compilation failed.' }
    $portableZip = Join-Path $artifactRoot ('XD-SVN-Tools-' + $version + '-win-x64.zip')
    Compress-Archive -LiteralPath $appRoot -DestinationPath $portableZip -CompressionLevel Optimal -Force
    $setupExe = Join-Path $artifactRoot ('XD-SVN-Tools-Setup-' + $version + '.exe')
    & $compiler /nologo /target:winexe /platform:x64 ('/out:' + $setupExe) ('/resource:' + $portableZip + ',payload.zip') @references $generated
    if ($LASTEXITCODE -ne 0) { throw 'Installer compilation failed.' }

    # Exercise the frozen program without installing or changing registry settings.
    & $Python scripts\smoke-build.py (Join-Path $appRoot 'XD-SVN-Tools.exe')
    if ($LASTEXITCODE -ne 0) { throw 'Packaged executable smoke check failed.' }
    $checksums = Join-Path $artifactRoot ('SHA256SUMS-' + $version + '.txt')
    @($setupExe, $portableZip) | ForEach-Object {
        $hash = Get-FileHash -LiteralPath $_ -Algorithm SHA256
        $hash.Hash.ToLowerInvariant() + '  ' + (Split-Path $_ -Leaf)
    } | Set-Content -LiteralPath $checksums -Encoding utf8
    if ($env:GITHUB_OUTPUT) { Add-Content -LiteralPath $env:GITHUB_OUTPUT -Value ('version=' + $version) -Encoding utf8 }
    Write-Host "Built Windows x64 release $version in $artifactRoot"
} finally { Pop-Location }
