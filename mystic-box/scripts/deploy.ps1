# Publica o frontend: build -> S3 -> invalida o index.html no CloudFront.
# Uso (PowerShell, em mystic-box/): .\scripts\deploy.ps1
# Requer a stack mystic-box-frontend (infra/template.yaml) ja criada. Ver infra/README.md.
param(
    [string]$StackName = "mystic-box-frontend",
    [switch]$SkipBuild
)
$ErrorActionPreference = "Stop"

function Invoke-Native {
    & $args[0] $args[1..($args.Length - 1)]
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
$url = Get-StackOutput "FrontendUrl"

if (-not $SkipBuild) { Invoke-Native npm run build }

# Arquivos com hash no nome (dist/assets) nunca mudam: cache de 1 ano.
Invoke-Native aws s3 sync dist/assets "s3://$bucket/assets" --delete `
    --cache-control "public, max-age=31536000, immutable"

# Demais arquivos (index.html, favicon...): o navegador sempre revalida,
# para pegar a versao nova logo apos o deploy.
Invoke-Native aws s3 sync dist "s3://$bucket" --delete --exclude "assets/*" `
    --cache-control "no-cache"

# So o que nao tem hash precisa sair do cache do CloudFront.
Invoke-Native aws cloudfront create-invalidation --distribution-id $distributionId `
    --paths "/index.html" "/" "/favicon.svg" "/icons.svg" --query "Invalidation.Id" --output text

Write-Host "Publicado em $url"
