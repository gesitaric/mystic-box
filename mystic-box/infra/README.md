# Infra do frontend (CloudFront + S3)

O build do frontend (`dist/`) fica no bucket S3 `mystic-box-frontend-465926092387`
(us-east-1) e é servido pelo CloudFront. O bucket **não é público**: só a
distribuição lê os arquivos, via Origin Access Control (OAC).

`cloudfront.yaml` cria a stack `mystic-box-frontend` com:

- a distribuição (HTTPS obrigatório, HTTP/2 e 3, compressão, `PriceClass_100`);
- cache pela política gerenciada `CachingOptimized`, que respeita o `Cache-Control`
  gravado em cada objeto pelo deploy;
- headers de segurança pela política gerenciada `SecurityHeadersPolicy`;
- 403/404 devolvendo `index.html` (o app usa rotas por hash, como `#portal`);
- a política do bucket liberando `s3:GetObject` só para esta distribuição
  (substitui a antiga política pública).

O bucket em si foi criado à mão e não faz parte da stack.

## Criar ou atualizar a stack

Em `mystic-box/`:

```powershell
aws cloudformation deploy --stack-name mystic-box-frontend --template-file infra/cloudfront.yaml --region us-east-1
aws cloudformation describe-stacks --stack-name mystic-box-frontend --query "Stacks[0].Outputs" --region us-east-1
```

A distribuição leva alguns minutos para ficar pronta. A URL do jogo é o output `FrontendUrl`.

## Publicar o frontend

Em `mystic-box/`, com o `.env` de produção preenchido:

```powershell
npm run deploy
```

O script (`scripts/deploy.ps1`) faz o build, envia `dist/assets` com cache de 1 ano
(os nomes têm hash), envia o resto com `no-cache` e invalida no CloudFront só os
arquivos sem hash (`index.html` etc.).
