# ⬡ NexusOSINT

Dashboard de investigação OSINT para análise de usernames e emails.

![Python](https://img.shields.io/badge/Python-3.10-blue)
![Streamlit](https://img.shields.io/badge/Streamlit-1.35-red)

## Funcionalidades

- 💥 **Vazamentos** — busca em bancos de breaches via OathNet API
- 🦠 **Stealer Logs** — credenciais capturadas por malware infostealer
- 🌐 **Redes Sociais** — presença em 25+ plataformas via Sherlock
- 📧 **Holehe** — serviços com conta cadastrada para um email
- 📤 **Exportar** — relatórios em HTML dark-mode, PDF e Excel
- 🗂️ **Casos** — histórico de investigações persistido localmente

## Deploy no Streamlit Cloud

1. Faça fork deste repositório
2. Acesse [share.streamlit.io](https://share.streamlit.io)
3. Conecte seu GitHub e selecione este repositório
4. Em **Settings → Secrets**, adicione:

```toml
OATHNET_API_KEY = "sua_chave_aqui"
```

5. Clique em **Deploy** ✅

## Rodar localmente

```bash
# Com Docker (recomendado)
cp .env.example .env
# Edite .env com sua chave
docker build -t nexus-osint .
docker run -p 8501:8501 --env-file .env -v %cd%:/app nexus-osint

# Sem Docker
pip install -r requirements.txt
# Crie .streamlit/secrets.toml com sua chave
streamlit run app.py
```

## Variáveis de ambiente

| Variável | Descrição |
|---|---|
| `OATHNET_API_KEY` | Chave da API OathNet (obrigatória) |
| `DEBUG` | `true` para ativar aba de diagnóstico (apenas local) |

## Uso ético e legal

Esta ferramenta é destinada exclusivamente para uso legal e ético:
investigação de segurança, OSINT defensivo e pesquisa autorizada.
