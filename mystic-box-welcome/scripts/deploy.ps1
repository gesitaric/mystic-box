# Publica a landing page: build -> S3 -> invalida o index.html no CloudFront.
# Uso (PowerShell, em mystic-box-welcome/): .\scripts\deploy.ps1
# Requer a stack mystic-box-welcome (infra/template.yaml) ja criada. Ver infra/README.md.
param(
    [string]$StackName = "mystic-box-welcome",
    [switch]$SkipBuild
)
$ErrorActionPreference = "Stop"

function Invoke-Native {
    $command, $arguments = $args
    & $command @arguments
    if ($LASTEXITCODE -ne 0) { throw "Falhou ($LASTEXITCODE): $($args -join ' ')" }
}

function Get-StackOutput([string]$Key) {
    $value = aws cloudformation describe-stacks --stack-name $StackName `
        --query "Stacks[0].Outputs[?OutputKey=='$Key'].OutputValue" --output text
    if ($LASTEXITCODE -ne 0 -or -not $value -or $value -eq "None") {
        throw "Output '$Key' nao encontrado na stack '$StackName'."
    }
    return $value.Trim()
}

Set-Location (Split-Path $PSScriptRoot -Parent)

$bucket = Get-StackOutput "BucketName"
$distributionId = Get-StackOutput "DistributionId"
$url = Get-StackOutput "WelcomeUrl"

if (-not $SkipBuild) { Invoke-Native npm run build }

# Arquivos com hash no nome (dist/assets) nunca mudam: cache de 1 ano.
$assetsCache = "public, max-age=31536000, immutable"
Invoke-Native aws s3 sync dist/assets "s3://$bucket/assets" --delete `
    --exclude "*.webp" --cache-control $assetsCache

# O AWS CLI no Windows nao reconhece .webp e grava binary/octet-stream:
# envia as imagens a parte com o tipo explicito.
Invoke-Native aws s3 sync dist/assets "s3://$bucket/assets" --delete `
    --exclude "*" --include "*.webp" --content-type "image/webp" --cache-control $assetsCache

# Demais arquivos (index.html, favicon...): o navegador sempre revalida,
# para pegar a versao nova logo apos o deploy.
Invoke-Native aws s3 sync dist "s3://$bucket" --delete --exclude "assets/*" `
    --cache-control "no-cache"

# So o que nao tem hash precisa sair do cache do CloudFront.
Invoke-Native aws cloudfront create-invalidation --distribution-id $distributionId `
    --paths "/index.html" "/" "/favicon.svg" --query "Invalidation.Id" --output text

Write-Host "Publicado em $url"
