param([switch]$NoBuild)
. (Join-Path $PSScriptRoot 'Common.ps1')
$configPath = Join-Path $AppRoot '.env'
if (-not (Test-Path -LiteralPath $configPath)) {
    $databasePassword = New-AppSecret
    $demoPassword = New-AppSecret
    $config = @(
        'APP_HTTP_PORT=8094'
        "APP_DB_PASSWORD=$databasePassword"
        "APP_DEMO_PASSWORD=$demoPassword"
        'APP_DEMO_MODE=true'
        'APP_SEED_DEMO=true'
        'APP_COOKIE_SECURE=false'
        'APP_ALLOWED_ORIGINS=http://localhost:8094,http://127.0.0.1:8094'
    )
    [IO.File]::WriteAllLines($configPath, $config)
    $privateDirectory = Join-Path $AppRoot '.local'
    New-Item -ItemType Directory -Path $privateDirectory -Force | Out-Null
    $credentialText = @(
        'LeaveFlow HRIS - akun Training lokal. Jangan unggah berkas ini.'
        'URL: http://localhost:8094'
        'manager@leaveflow.test'
        'manager2@leaveflow.test'
        'employee@leaveflow.test'
        'colleague@leaveflow.test'
        'second@leaveflow.test'
        "Sandi latihan: $demoPassword"
        'Sandi hanya diatur saat seed pertama. Mengubah .env tidak mereset akun yang sudah tersimpan.'
    )
    [IO.File]::WriteAllLines((Join-Path $privateDirectory 'LOCAL-CREDENTIALS.txt'), $credentialText)
}
$arguments = @('up', '-d', '--wait', '--wait-timeout', '180')
if (-not $NoBuild) { $arguments += '--build' }
Invoke-AppCompose -ComposeArguments $arguments
Write-Output 'LeaveFlow HRIS siap: http://localhost:8094 (atau port pada .env).'
Write-Output 'Akun Training: .local\LOCAL-CREDENTIALS.txt; konfigurasi manual memakai sandi saat seed pertama.'
