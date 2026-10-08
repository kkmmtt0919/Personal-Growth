param([switch]$Demo)

$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw '请先安装项目依赖（uv sync）。' }
foreach ($servicePort in @(8000, 5173)) {
    if (Get-NetTCPConnection -LocalPort $servicePort -State Listen -ErrorAction SilentlyContinue) {
        throw "端口 $servicePort 已被占用，请先停止原服务。"
    }
}
if ($Demo) { $env:GROWTH_PRODUCT_DEMO = '1' } else { Remove-Item Env:GROWTH_PRODUCT_DEMO -ErrorAction SilentlyContinue }
$logDirectory = Join-Path $projectRoot 'tmp\product-service'
New-Item -ItemType Directory -Force -Path $logDirectory | Out-Null
$backendProcess = Start-Process -FilePath $pythonPath -ArgumentList @('-m','uvicorn','growth_os.api.product:create_local_product_app','--factory','--host','127.0.0.1','--port','8000') -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logDirectory 'backend.log') -RedirectStandardError (Join-Path $logDirectory 'backend-error.log')
try {
    $ready = $false
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        if ($backendProcess.HasExited) { throw '后端启动失败，请查看 tmp/product-service/backend-error.log。' }
        try {
            $status = Invoke-RestMethod 'http://127.0.0.1:8000/api/product' -TimeoutSec 2
            if ($status.enabled) { $ready = $true; break }
        } catch { Start-Sleep -Milliseconds 500 }
    }
    if (-not $ready) { throw '后端启动超时，请查看 tmp/product-service/backend-error.log。' }
    Write-Host 'Growth OS: http://127.0.0.1:5173/'
    Write-Host '保留此终端；按 Ctrl+C 停止前后端。'
    & npm.cmd --prefix (Join-Path $projectRoot 'frontend') run dev -- --host 127.0.0.1 --port 5173 --strictPort
} finally {
    if (-not $backendProcess.HasExited) { Stop-Process -Id $backendProcess.Id -ErrorAction SilentlyContinue }
}
