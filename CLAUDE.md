# Mystic Box

Monorepo do jogo de invocação de cartas:

- `mystic-box/`: frontend (React + Vite).
- `mystic-box-back/`: backend serverless (AWS SAM: API Gateway + Lambda em Python + DynamoDB + Cognito).

## Regra principal: TODAS as regras do jogo ficam no backend

O frontend **não define NADA** do jogo. Ele só mostra o que o backend devolve e pede ações ao backend. Vale para qualquer implementação futura, sem exceções.

Isso significa:

- **Nada de regra de jogo no frontend**: preços, raridades, probabilidades, sorteios, recompensas, saldos, tempo de espera, limites, validações do que o jogador pode ou não fazer. Tudo isso é calculado e validado numa Lambda.
- **Nunca confiar em dados de jogo vindos do cliente.** Requisições levam só a *intenção* e identificadores (ex.: `ownedCardId` da carta a vender, o `summonToken` de um sorteio). Nome, raridade, preço, quantidade de moeda etc. são lidos no servidor. Um campo como `price` ou `rarity` enviado pelo cliente deve ser ignorado.
- **Valores que o frontend exibe vêm da API** (ex.: `sellPrice` em `GET /users/me/cards`, `balance` em `GET /users/me/wallet`, `retryAfterSeconds` no tempo de espera). O frontend não recalcula nem guarda cópias dessas tabelas.
- **Operações que mexem em mais de um dado são atômicas** (`TransactWriteItems` com condições), para evitar duplicação (ex.: vender a mesma carta duas vezes, guardar o mesmo sorteio duas vezes).
- O que pode ficar no frontend: apresentação. Layout, animações, textos, ordem de exibição, efeitos visuais de raridade a partir do que a API devolveu.

## Onde ficam as regras

- `mystic-box-back/shared/mystic_shared/` é a Lambda Layer `SharedLayer`, compartilhada entre as Lambdas:
  - `cards.py`: **fonte única** das definições das cartas (`name`, `rarity`, `file_name`, `price`), das regras da loja (`buy_price`, `sell_price`, `shop_catalog`) e das regras do sorteio (pesos por raridade, tamanho da invocação). Para achar uma carta, use `get_character(file_name)`.
  - `summon_token.py`: token assinado (HMAC, chave no Secrets Manager) que comprova que um sorteio foi feito pelo servidor.
- Uma Lambda nova que precise dessas regras deve declarar `Layers: [!Ref SharedLayer]` no `template.yaml` e importar de `mystic_shared`. Não copie as definições para outra Lambda nem para o frontend.

## Fluxos atuais

- **Invocar**: `POST /box/open` (público) sorteia no servidor e devolve as cartas + `summonToken`. Para guardá-las, o frontend envia **só** o `summonToken` para `POST /users/me/cards`. O token é de uso único, expira em 30 minutos e consome o tempo de espera do usuário.
- **Coleção**: `GET /users/me/cards` devolve as cartas **agrupadas por carta** (`file_name`), com `quantity`, `sellPrice` (por cópia) e `maxSellQuantity` calculados no servidor, além de `totalCards`.
- **Vender**: `POST /users/me/cards/sell` com `{"fileName", "quantity"}`. O servidor escolhe quais cópias saem (as mais recentes), remove todas e credita `sell_total` (`cards.py`) na carteira, na mesma transação. O limite por venda é `MAX_SELL_QUANTITY`.
- **Loja**: `GET /shop/cards` devolve o catálogo (`shop_catalog`) com `buyPrice` e `canAfford` calculados no servidor, além do `balance`. Comprar é `POST /shop/cards/{fileName}/buy`, que debita o preço de `buy_price` (só se o saldo cobrir, condição na transação) e adiciona a carta à coleção, na mesma transação. A aba "Vender" da loja usa o fluxo de venda acima.

## Rodar localmente

Passo a passo em `mystic-box-back/local/README.md`. Resumo:

1. Banco (Ubuntu/WSL, a partir de `mystic-box-back/`): `docker compose -f local/docker-compose.yml up -d` (DynamoDB Local em `localhost:8000`).
2. API (PowerShell, em `mystic-box-back/`): `.\.venv\Scripts\python.exe local\dev_server.py` (porta 3000). Lê rotas, variáveis e tabelas do `template.yaml`; uma Lambda nova no template aparece sozinha. `SUMMON_COOLDOWN_SECONDS` pode ser sobrescrito pelo ambiente.
3. Frontend (em `mystic-box/`): `npm run dev:local` (usa `.env.localapi`, copiado de `.env.localapi.example`).

O disco C está sem espaço: Docker, WSL (`D:\WSL\Ubuntu`), `.venv` e dados ficam no D. Não instale nada que grave no C.

## Testes

Backend (a partir de `mystic-box-back/`): `python -m pytest tests/unit`. O `tests/unit/conftest.py` coloca `shared/` no `sys.path` e usa uma chave de teste para o token.

Frontend (a partir de `mystic-box/`): `npx eslint src` e `npx vite build`.
