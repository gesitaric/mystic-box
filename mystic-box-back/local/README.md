# Rodar o Mystic Box localmente

Só o banco (DynamoDB Local) roda em Docker. As Lambdas rodam num único processo
Python (`dev_server.py`), que lê rotas, variáveis e tabelas do `template.yaml`.
O login continua no Cognito real (stack `mystic-box-back`); os dados do jogo
(coleção, carteira, sorteios) ficam só no banco local.

Docker: Docker Engine instalado dentro do Ubuntu do WSL (sem Docker Desktop).
O disco do WSL fica em `D:\WSL\Ubuntu`, então imagens e dados ficam no D.

## Instalar o Docker (uma vez)

No terminal do Ubuntu (`wsl -d Ubuntu`):

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
```

Feche o terminal, rode `wsl --shutdown` no Windows e abra o Ubuntu de novo.

## Preparar o Python (uma vez, a partir de `mystic-box-back/`)

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --no-cache-dir -r local\requirements.txt
```

## Subir

1. Banco (no Ubuntu/WSL):
   ```bash
   cd /mnt/d/WebProjects/mystic-box-2/mystic-box-back
   docker compose -f local/docker-compose.yml up -d
   ```
2. API (PowerShell, em `mystic-box-back/`): `.\.venv\Scripts\python.exe local\dev_server.py`
   - Tempo de espera menor para testar: `$env:SUMMON_COOLDOWN_SECONDS="10"` antes de rodar.
3. Frontend (em `mystic-box/`): `npm run dev:local` (usa `.env.localapi`, não versionado:
   `VITE_API_URL=http://localhost:3000` + IDs do Cognito).

Para parar o banco: `docker compose -f local/docker-compose.yml down`
(com `-v` apaga também os dados locais).

## Diferenças em relação à AWS

- A assinatura do token do Cognito **não** é verificada localmente (só `exp`,
  `token_use` e `sub`). O servidor escuta apenas em 127.0.0.1.
- A chave do `summonToken` é fixa (`LOCAL_SUMMON_SECRET`), sem Secrets Manager.
- Credenciais falsas e todo endpoint da AWS aponta para o DynamoDB Local:
  nada do servidor local acessa a conta real.
- Python da máquina, não o runtime `python3.14` da Lambda.
