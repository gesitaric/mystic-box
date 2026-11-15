# mystic-box (frontend do jogo)

Cliente web do Mystic Box: React 19 + Vite, publicado em `https://mystic-box.geskee.com.br` (S3 + CloudFront, ver `infra/README.md`).

**Importante:** o frontend não define NENHUMA regra do jogo (preços, raridades, sorteio, saldo, tempo de espera, limites). Ele só mostra o que a API devolve e envia intenções e identificadores (ex.: o `summonToken` de um sorteio, o `listingId` do anúncio a comprar). Veja o `CLAUDE.md` e o `README.md` na raiz do repositório.

## Configuração (AWS Cognito + API)

1. Copie `.env.example` para `.env`.
2. Preencha com os outputs da stack `mystic-box-back`:
   - `VITE_API_URL`: output `ApiUrl` (`https://mystic-box-api.geskee.com.br`, o CloudFront na frente do API Gateway)
   - `VITE_COGNITO_USER_POOL_ID`: output `UserPoolId`
   - `VITE_COGNITO_CLIENT_ID`: output `UserPoolClientId`
3. `npm install` e `npm run dev`.

### Rodar contra a API local (testes)

Use `npm run dev:local` com o `.env.localapi` (copie de `.env.localapi.example`).
O passo a passo completo (Docker, banco e API) está em `../mystic-box-back/local/README.md`.

## Fluxo da invocação

Invocar exige login. Ao abrir o portal, o servidor confere o tempo de espera, sorteia as cartas, começa o tempo de espera na hora e devolve as cartas com um `summonToken` assinado, ligado ao jogador. O frontend guarda as cartas logo em seguida, enviando só o token para `POST /users/me/cards`, e mantém o sorteio no `localStorage` até ser guardado (para tentar de novo se a página recarregar).

Enquanto o sorteio não é guardado, abrir o portal de novo devolve o mesmo sorteio. Se ele foi aberto em outro aparelho, `GET /users/me/summon-status` devolve o sorteio pendente e o frontend o guarda. As cartas repetidas servem para ascender a carta ou ser anunciadas no mercado, pelo preço escolhido pelo jogador dentro da faixa que a API informa.

## Comandos

| Comando | O que faz |
| --- | --- |
| `npm run dev` / `npm run dev:local` | Servidor de desenvolvimento (API de produção / API local) |
| `npx eslint src` | Lint |
| `npx vite build` | Build de produção em `dist/` |
| `npm run test:ui` | Testes de tela (Playwright no Edge instalado, 4 tamanhos de tela); detalhes no `CLAUDE.md` |
| `npm run test:ui:update` / `npm run test:ui:report` | Atualiza as imagens de referência do Windows / abre o relatório |
| `npm run images` | Converte as ilustrações originais para WebP |
| `npm run deploy` | Build e publicação no S3 + invalidação no CloudFront (`scripts/deploy.ps1`), com o `.env` de produção |
