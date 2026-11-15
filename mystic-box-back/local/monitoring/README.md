# Grafana local lendo a produção

Um Grafana roda no Docker do WSL, na própria máquina, e lê o **CloudWatch da
conta de produção** (stack `mystic-box-back`, us-east-1). Não tem servidor
novo nem serviço pago de monitoramento, e não muda nada na AWS.

```
Navegador → http://localhost:3001 → Grafana (Docker no WSL) → CloudWatch (só leitura)
```

## Arquivos

| Arquivo | Para quê |
|---|---|
| `../docker-compose.yml` | serviço `grafana` (perfil `monitoring`, porta 3001 só em 127.0.0.1) |
| `grafana/provisioning/datasources/cloudwatch.yml` | fonte de dados CloudWatch (chave lida do `grafana.env`) |
| `grafana/provisioning/dashboards/dashboards.yml` | carrega os painéis da pasta `grafana/dashboards` |
| `grafana/dashboards/mystic-box-producao.json` | o painel "Mystic Box: produção" (abre como página inicial) |
| `iam-policy.json` | permissões do usuário IAM `mystic-box-grafana` |
| `grafana.env.example` | modelo do `grafana.env` (a chave, **fora do git**) |

## Usuário IAM (uma vez)

O usuário `mystic-box-grafana` só lê métricas e logs. Ele não chama as
Lambdas, não lê o DynamoDB e não muda nada. Para recriá-lo (PowerShell, em
`mystic-box-back/local/monitoring/`, com uma credencial que possa criar
usuários IAM):

```powershell
aws iam create-user --user-name mystic-box-grafana
aws iam put-user-policy --user-name mystic-box-grafana `
  --policy-name mystic-box-grafana-readonly --policy-document file://iam-policy.json
aws iam create-access-key --user-name mystic-box-grafana
```

Copie `grafana.env.example` para `grafana.env` e preencha com o
`AccessKeyId` e a `SecretAccessKey` da saída.

Mudou a policy? Rode de novo só o `put-user-policy`. Para trocar a chave:
`create-access-key`, atualize o `grafana.env`, reinicie o Grafana e apague a
antiga com `aws iam delete-access-key --user-name mystic-box-grafana --access-key-id <antiga>`.

## Subir e parar

No Ubuntu/WSL, a partir de `mystic-box-back/`:

```bash
docker compose -f local/docker-compose.yml --profile monitoring up -d grafana
docker compose -f local/docker-compose.yml stop grafana
```

Abra http://localhost:3001. O painel abre sem login, só para ver. Para
editar ou usar o Explore, clique em **Sign in** e entre com `admin` / `admin`.
A porta só fica aberta na própria máquina.

O `up -d` de sempre (sem `--profile monitoring`) continua subindo só o DynamoDB Local.

Painel alterado na tela não volta para o arquivo. Para manter a mudança, use
**Export → JSON**, substitua `grafana/dashboards/mystic-box-producao.json` e
faça o commit. O Grafana relê a pasta a cada 30 s.

## O que o painel mostra

- **Visão geral**: pedidos, 4xx e 5xx do API Gateway (stage Prod), erros e
  throttles das Lambdas, logins no Cognito, e a latência da API e das Lambdas.
- **Atividade do jogo**: chamadas por Lambda (cada uma é uma ação: OpenBox =
  invocar, BuyListing = comprar no mercado, PlayBattle = turno contra o
  computador…) e as ações principais ao longo do tempo.
- **Lambdas em detalhe** e **DynamoDB**: linhas fechadas que só consultam ao
  serem abertas. Mostram erros, duração p95, throttles e concorrência por
  Lambda, e capacidade consumida, throttles e erros por tabela.
- **Logs**: avisos e erros das Lambdas (Logs Insights nos grupos de log do stack).

O CloudFront da API (`ApiDistribution`) não está no painel. Os pedidos de
`GET /rules` e `GET /world` respondidos pelo cache dele não chegam no API
Gateway, então não aparecem nos gráficos de pedidos nem nas chamadas das
Lambdas `GetRules` e `GetWorld`. Para ver esse tráfego, use as métricas do
CloudFront no console (região Global).

As Lambdas e tabelas são achadas pelo nome (`SEARCH` com `mystic-box-back`),
então uma Lambda ou tabela nova aparece sozinha nos gráficos de métricas. A
exceção é o **painel de logs**: o grupo de log da Lambda nova precisa entrar
na lista `logGroups` do JSON. O teste `tests/unit/test_monitoring_dashboard.py` cobra isso.

## Custo

- As métricas de Lambda, API Gateway, DynamoDB e Cognito já são gravadas pela
  AWS de graça.
- Cada leitura do Grafana cobra US$ 0,01 a cada 1.000 métricas, só com o
  painel aberto. A visão padrão lê umas 75 métricas por atualização (a busca
  por Lambda conta uma métrica por função). Atualizando a cada 5 min, 8 h por
  dia, dá cerca de US$ 2 por mês. As linhas fechadas não consultam nada até
  serem abertas.
- O painel de logs cobra US$ 0,005 por GB lido. Os logs são pequenos (nível
  WARN, 14 dias de retenção), então o custo fica perto de zero.
- **Não** ligue `MetricsEnabled` (métricas por rota) no `MethodSettings` da API.
  Elas são cobradas como métricas próprias, cerca de 5 por rota a US$ 0,30 cada
  por mês.
