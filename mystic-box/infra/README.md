# Infra do frontend (S3 + CloudFront)

O build do frontend (`dist/`) fica no bucket S3 `mystic-box-frontend-465926092387`
(us-east-1) e é servido pelo CloudFront. O bucket **não é público**: só a
distribuição lê os arquivos, via Origin Access Control (OAC).

A infra do frontend é uma stack própria (`mystic-box-frontend`), separada da do
backend (`mystic-box-back`), e também é publicada com `sam deploy`.

`template.yaml` define:

- o bucket, com acesso público bloqueado e sem website hosting
  (`DeletionPolicy: Retain`: apagar a stack não apaga o bucket);
- a distribuição (HTTPS obrigatório, HTTP/2 e 3, compressão, `PriceClass_100`);
- cache pela política gerenciada `CachingOptimized`, que respeita o `Cache-Control`
  gravado em cada objeto pelo deploy;
- headers de segurança pela política gerenciada `SecurityHeadersPolicy`;
- 403/404 devolvendo `index.html` (o app usa rotas por hash, como `#portal`);
- a política do bucket liberando `s3:GetObject` só para esta distribuição.

## Atualizar a infra

Na pasta `mystic-box/infra/` (PowerShell):

```powershell
sam validate
sam deploy
```

O `samconfig.toml` já define stack, região e confirmação do changeset.
Mudanças na distribuição levam alguns minutos para propagar.

## Publicar o frontend

Em `mystic-box/`, com o `.env` de produção preenchido:

```powershell
npm run deploy
```

O script (`scripts/deploy.ps1`) lê bucket e distribuição dos outputs da stack, faz o
build, envia `dist/assets` com cache de 1 ano (os nomes têm hash), envia o resto com
`no-cache` e invalida no CloudFront só os arquivos sem hash (`index.html` etc.).

## Import do bucket (feito uma única vez)

O bucket foi criado à mão antes de existir a stack. Para trazê-lo para a stack sem
recriá-lo, a stack nasce de um changeset de IMPORT com `import/bucket.yaml`, que
descreve o bucket exatamente como ele estava (público, com website hosting). Só
depois o `sam deploy` aplica `template.yaml`, que bloqueia o acesso público, tira o
website hosting e cria o CloudFront.

Na pasta `mystic-box/infra/` (PowerShell):

```powershell
aws cloudformation create-change-set --region us-east-1 --stack-name mystic-box-frontend `
  --change-set-name import-bucket --change-set-type IMPORT `
  --template-body file://import/bucket.yaml --resources-to-import file://import/resources.json
aws cloudformation wait change-set-create-complete --region us-east-1 --stack-name mystic-box-frontend --change-set-name import-bucket
aws cloudformation execute-change-set --region us-east-1 --stack-name mystic-box-frontend --change-set-name import-bucket
aws cloudformation wait stack-import-complete --region us-east-1 --stack-name mystic-box-frontend
sam deploy
```

Depois do `sam deploy`, o endereço de website do S3 deixa de funcionar e o jogo
passa a ser acessado só pela URL do output `FrontendUrl`.
