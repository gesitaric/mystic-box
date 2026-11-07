# Mystic Box

Monorepo do jogo de invocação de cartas:

- `mystic-box/`: frontend (React + Vite).
- `mystic-box-back/`: backend serverless (AWS SAM: API Gateway + Lambda em Python + DynamoDB + Cognito).

## Regra principal: TODAS as regras do jogo ficam no backend

O frontend **não define NADA** do jogo. Ele só mostra o que o backend devolve e pede ações ao backend. Vale para qualquer implementação futura, sem exceções.

Isso significa:

- **Nada de regra de jogo no frontend**: preços, raridades, probabilidades, sorteios, recompensas, saldos, tempo de espera, limites, validações do que o jogador pode ou não fazer. Tudo isso é calculado e validado numa Lambda.
- **Nunca confiar em dados de jogo vindos do cliente.** Requisições levam só a *intenção* e identificadores (ex.: `listingId` do anúncio a comprar, o `summonToken` de um sorteio). Nome, raridade, preço, quantidade de moeda etc. são lidos no servidor. Um campo como `price` ou `rarity` enviado pelo cliente deve ser ignorado. A única escolha livre do jogador é o preço pedido ao **anunciar** uma carta no mercado, e mesmo esse é validado no servidor contra a faixa da raridade.
- **Valores que o frontend exibe vêm da API** (ex.: `listingPriceRange` em `GET /users/me/cards`, `balance` em `GET /users/me/wallet`, `retryAfterSeconds` no tempo de espera). O frontend não recalcula nem guarda cópias dessas tabelas.
- **Operações que mexem em mais de um dado são atômicas** (`TransactWriteItems` com condições), para evitar duplicação (ex.: anunciar ou comprar a mesma carta duas vezes, guardar o mesmo sorteio duas vezes).
- O que pode ficar no frontend: apresentação. Layout, animações, textos, ordem de exibição, efeitos visuais de raridade a partir do que a API devolveu.

## Onde ficam as regras

- `mystic-box-back/shared/mystic_shared/` é a Lambda Layer `SharedLayer`, compartilhada entre as Lambdas:
  - `cards.py`: **fonte única** das definições das cartas (`name`, `rarity`, `file_name`), das regras do mercado (`LISTING_PRICE_LIMITS`, `MAX_LISTING_QUANTITY`, `MAX_ACTIVE_LISTINGS`, `listing_price_range`) e das regras do sorteio (pesos por raridade, tamanho da invocação). Para achar uma carta, use `get_character(file_name)`.
  - `summon_token.py`: token assinado (HMAC, chave no Secrets Manager) que comprova que um sorteio foi feito pelo servidor.
  - `stats.py`: atributos de batalha (vitality, might, arcana, bulwark, resolve, celerity, fate), elementos e arquétipos. Os atributos saem da raridade, do arquétipo e do nível; elemento e arquétipo de cada carta ficam em `cards.py`.
  - `battle.py`: motor da batalha contra o computador (turnos, Aether, habilidades, efeitos, IA, dificuldades e experiência ganha).
  - `pvp.py`: regras do duelo online (validade do desafio, limite de desafios, tempo de turno, vezes perdidas até abandonar, histórico de eventos). A batalha em si é a de `battle.py` com `mode: "pvp"`.
  - `progression.py`: curva de experiência, nível máximo e Fragmentos Arcanos ganhos ao subir de nível.
  - `usernames.py`: regras do nome de usuário (tamanho, caracteres, 30 dias de espera entre trocas) e da busca de jogadores.
  - `rules.py`: monta a explicação das regras para o jogador (`GET /rules`) a partir das constantes dos módulos acima. Não duplica valores: mudar uma regra lá muda o que a ajuda mostra.
- Uma Lambda nova que precise dessas regras deve declarar `Layers: [!Ref SharedLayer]` no `template.yaml` e importar de `mystic_shared`. Não copie as definições para outra Lambda nem para o frontend.

## Fluxos atuais

- **Invocar**: `POST /box/open` (público) sorteia no servidor e devolve as cartas + `summonToken`. Para guardá-las, o frontend envia **só** o `summonToken` para `POST /users/me/cards`. O token é de uso único, expira em 30 minutos e consome o tempo de espera do usuário.
- **Coleção**: `GET /users/me/cards` devolve as cartas **agrupadas por carta** (`file_name`), com `quantity`, `listingPriceRange` (faixa de preço por cópia aceita ao anunciar) e `maxListingQuantity` calculados no servidor, além de `totalCards`. Cada carta traz em `battle` o elemento, o arquétipo, os atributos e as habilidades de batalha.
- **Mercado (loja)**: há **controle de estoque**. Cartas novas só nascem do sorteio; a loja só vende cartas que outros jogadores anunciaram, pelo preço que eles escolheram. Não existe venda para o sistema nem compra de cartas "do nada".
  - Anunciar: `POST /shop/listings` com `{"fileName", "quantity", "price"}`. O preço precisa estar na faixa da raridade (`LISTING_PRICE_LIMITS`). As cópias mais recentes **saem da coleção** e entram em `ShopListingsTable` (uma por cópia), na mesma transação; o contador `activeListings` na `UserWalletTable` limita os anúncios ativos (`MAX_ACTIVE_LISTINGS`).
  - Ver: `GET /shop/listings` devolve as cartas de **outros** jogadores agrupadas por carta (anúncio mais barato em `listingId`/`price`, `available`, `canAfford`), os anúncios do próprio jogador em `myListings`, `maxActiveListings` e o `balance`.
  - Comprar: `POST /shop/listings/{listingId}/buy`. Numa só transação: apaga o anúncio (condição: ainda existe com o mesmo preço e vendedor), debita o comprador (só se o saldo cobrir), credita o vendedor (sem taxa) e põe a carta na coleção do comprador. Não dá para comprar o próprio anúncio.
  - Cancelar: `POST /shop/listings/{listingId}/cancel` devolve a carta à coleção (mesmo `ownedCardId`).
- **Nível**: `GET /users/me/profile` devolve nível e progresso. Só a experiência total fica salva (`UserProgressTable`); o nível é sempre calculado no servidor.
- **Nome de usuário**: `GET /users/me/profile` também devolve `userId`, `username` (`null` se não definido), `usernameChange` (`canChange`, `retryAfterSeconds`, `nextChangeAt`) e `usernameRules`. Definir/trocar é `POST /users/me/username` com `{"username"}`: valida em `usernames.py`, confere o tempo de espera e, numa só transação, grava o perfil (`UserProfilesTable`), reserva o nome em minúsculas (`UsernamesTable`, um dono por nome) e libera o nome antigo. Sem nome, o jogador continua identificado pelo `sub` do Cognito e não aparece na busca.
- **Busca de jogadores**: `GET /users/search?q=` procura pelo começo do nome (sem diferenciar maiúsculas) no índice `UsernameSearchIndex` e devolve `username`, `level` e `isYou` (o id do Cognito dos outros não é exposto). A rota tem limite de requisições no API Gateway (`MethodSettings` do `MysticBoxApi` no `template.yaml`, somando todos os jogadores); acima dele o API Gateway responde `429` sem chamar a Lambda (`GatewayResponses.THROTTLED` traz os cabeçalhos CORS). O limite não vale no `dev_server.py` local. O frontend só busca ao apertar o botão (ou Enter) e não repete a busca do mesmo nome.
- **Regras (Grimório)**: `GET /rules` (público) devolve chances do sorteio, tempo de espera, limites do mercado (faixas de preço, quantidade por anúncio, anúncios ativos), curva de nível e todas as regras de batalha (Aether, dano, elementos, classes, efeitos, dificuldades, experiência). O componente `Grimoire.jsx` só exibe essa resposta; texto explicativo fica no frontend, números e catálogos vêm da API.
- **Batalha**: `GET /battles/current` devolve a batalha ativa (ou `null`), as dificuldades liberadas pelo nível, o progresso e `pvpBattleId` (duelo online ativo ou `null`). `POST /battles` com `{"team": [fileName x3], "difficulty"}` começa uma batalha (posse das cartas conferida no servidor). `POST /battles/current/actions` com `{"battleId", "type": "skill"|"auto"|"forfeit", "skill", "target"}` joga o turno da carta da vez e os turnos do computador, devolvendo a batalha e os `events` para o frontend animar. O estado fica em `BattlesTable` com versão (condição em cada gravação). No fim, resultado, experiência (vitória > derrota; desistir = 0) e Fragmentos Arcanos de subida de nível são gravados numa só transação.
- **Duelo online**: mesmas regras da batalha, os dois lados são jogadores. Quem desafia precisa ter nome de usuário e acha o adversário pelo nome. `GET /pvp` devolve desafios recebidos/enviados, o duelo ativo e as regras. `POST /pvp/challenges` com `{"username", "team"}` cria o desafio (`PvpChallengesTable`, um por par, expira); o desafiado aceita com `POST /pvp/challenges/accept` `{"challengeId", "team"}` ou recusa com `/decline`; quem desafiou cancela com `/cancel`. Aceitar confere a posse das cartas dos dois e, numa só transação, apaga o desafio, cria o duelo (`PvpBattlesTable`) e marca os dois em `PvpPlayersTable` (um duelo ativo por jogador). `GET /pvp/battle?since=N&battleId=X` devolve o duelo do ponto de vista de quem pede (o próprio time sempre como `player`, ids `p*`) e os eventos depois do lote `N` (com `battleId` lê só o duelo; se nada mudou, devolve só `unchanged` e o tempo de turno); `POST /pvp/battle/actions` com `{"battleId", "type", "skill", "target", "since"}` só vale na vez de uma carta do jogador (desistir vale sempre). Vez com tempo esgotado é jogada no automático na próxima requisição de qualquer um dos dois; muitas seguidas = abandono. Rodadas esgotadas = empate. No fim, resultado e experiência dos dois são gravados numa só transação.

## Rodar localmente

Passo a passo em `mystic-box-back/local/README.md`. Resumo:

1. Banco (Ubuntu/WSL, a partir de `mystic-box-back/`): `docker compose -f local/docker-compose.yml up -d` (DynamoDB Local em `localhost:8000`).
2. API (PowerShell, em `mystic-box-back/`): `.\.venv\Scripts\python.exe local\dev_server.py` (porta 3000). Lê rotas, variáveis e tabelas do `template.yaml`; uma Lambda nova no template aparece sozinha. `SUMMON_COOLDOWN_SECONDS` pode ser sobrescrito pelo ambiente.
3. Frontend (em `mystic-box/`): `npm run dev:local` (usa `.env.localapi`, copiado de `.env.localapi.example`).

O disco C está sem espaço: Docker, WSL (`D:\WSL\Ubuntu`), `.venv` e dados ficam no D. Não instale nada que grave no C.

## Testes

Backend (a partir de `mystic-box-back/`): `python -m pytest tests/unit`. O `tests/unit/conftest.py` coloca `shared/` no `sys.path` e usa uma chave de teste para o token.

Frontend (a partir de `mystic-box/`): `npx eslint src` e `npx vite build`.
