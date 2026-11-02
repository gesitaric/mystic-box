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
- **Vender**: `POST /users/me/cards/{ownedCardId}/sell` remove a carta e credita o preço de `sell_price` (`cards.py`) na carteira, na mesma transação.
- **Loja**: `GET /shop/cards` devolve o catálogo (`shop_catalog`) com `buyPrice` e `canAfford` calculados no servidor, além do `balance`. Comprar é `POST /shop/cards/{fileName}/buy`, que debita o preço de `buy_price` (só se o saldo cobrir, condição na transação) e adiciona a carta à coleção, na mesma transação. A aba "Vender" da loja usa o fluxo de venda acima.

## Testes

Backend (a partir de `mystic-box-back/`): `python -m pytest tests/unit`. O `tests/unit/conftest.py` coloca `shared/` no `sys.path` e usa uma chave de teste para o token.

Frontend (a partir de `mystic-box/`): `npx eslint src` e `npx vite build`.
