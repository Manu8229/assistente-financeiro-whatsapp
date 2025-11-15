# 🤖 Assistente Financeiro Inteligente

Um assistente financeiro completo que funciona via **WhatsApp** com suporte a:
- 🎤 **Comando de voz** (Whisper)
- 📸 **Leitura de nota fiscal** (OCR)
- 🧠 **Análise inteligente de gastos**
- 📊 **Relatórios automáticos**
- 💾 **Banco de dados estruturado**

Desenvolvido seguindo as especificações do `Prompt2.txt` e as diretrizes de codificação Python do `Instruct.instructions.md`.

## 🎯 Funcionalidades

### 📝 **Entrada de Dados Múltipla**
- **Texto**: `"Gastei 50 reais no mercado"`
- **Voz**: Grave um áudio falando seus gastos
- **Imagem**: Envie foto da nota fiscal

### 🧠 **Inteligência Financeira**
- Categorização automática (alimentação, transporte, moradia, etc.)
- Detecção inteligente de entrada/saída
- Análise de padrões de gasto
- Insights personalizados

### 📊 **Relatórios Inteligentes**
- Resumo semanal/mensal
- Gastos por categoria
- Alertas de limite
- Projeções baseadas no histórico

### 🔍 **Sistema de Inspeção Visual** 🆕
- Dashboard interativo com visualização de dados em tempo real
- Filtros avançados por usuário, data, categoria e tipo
- Estatísticas gerais: receitas, gastos e saldo líquido
- Tabela completa de lançamentos com ordenação
- Gráficos de gastos por categoria
- Timeline de evolução diária
- Interface moderna e responsiva
- Acesso via navegador web em `/inspecao`

### 🔗 **Integração WhatsApp**
- Webhook via Twilio
- Processamento em tempo real
- Respostas conversacionais
- Suporte a múltiplos usuários

## 🚀 Instalação e Configuração

### 1. **Clone o Repositório**
```bash
git clone <url-do-repositorio>
cd "Assistente Financeiro"
```

### 2. **Configure o Ambiente Python**
```bash
# Crie um ambiente virtual
python -m venv .venv

# Ative o ambiente virtual
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate
```

### 3. **Instale as Dependências**
```bash
pip install -r requirements.txt
```

### 4. **Configure as Variáveis de Ambiente**
```bash
# Copie o arquivo de exemplo
copy .env.example .env

# Edite o arquivo .env com suas credenciais
```

**Configurações necessárias:**
- `TWILIO_ACCOUNT_SID`: Sua Account SID do Twilio
- `TWILIO_AUTH_TOKEN`: Seu Auth Token do Twilio  
- `TWILIO_PHONE_NUMBER`: Número do WhatsApp Business

### 5. **Configure o Tesseract (OCR)**

**Windows:**
```bash
# Baixe e instale o Tesseract de: https://github.com/UB-Mannheim/tesseract/wiki
# Adicione ao PATH: C:\Program Files\Tesseract-OCR
```

**Linux:**
```bash
sudo apt update
sudo apt install tesseract-ocr tesseract-ocr-por
```

**Mac:**
```bash
brew install tesseract tesseract-lang
```

### 6. **Execute o Assistente**
```bash
python assistente_financeiro.py
```

## 📱 Configuração do WhatsApp

### 1. **Conta Twilio**
1. Crie uma conta em [twilio.com](https://www.twilio.com/)
2. Configure o WhatsApp Business API
3. Obtenha suas credenciais (Account SID e Auth Token)

### 2. **Webhook Configuration**
1. Configure o webhook URL: `https://seu-dominio.com/webhook`
2. Método: `POST`
3. Ative para mensagens de entrada

### 3. **Teste a Integração**
Envie uma mensagem para o número do WhatsApp Business:
```
"Gastei 25 reais no almoço"
```

## 🎤 Como Usar

### **Comandos de Texto**
```
Entrada 3000 salário
Saída 200 mercado  
Gastei 50 reais na farmácia
Recebi 1500 freelance
```

### **Comandos de Voz**
1. Grave um áudio falando:
   - "Paguei quarenta reais de gasolina"
   - "Recebi dois mil de salário"
   - "Gastei cem reais no supermercado"

### **Foto da Nota Fiscal**
1. Tire uma foto clara da nota
2. Envie pelo WhatsApp
3. O sistema extrai automaticamente:
   - Valor total
   - Estabelecimento
   - Data (se disponível)

### **Relatórios**
```
relatório
resumo
saldo semanal
```

## 🏗️ Arquitetura do Sistema

```
[WhatsApp] → [Twilio API] → [Flask Webhook] → [Assistente Financeiro]
                                                       ↓
[Processador Voz] ← [Analisador Inteligente] → [Processador OCR]
        ↓                      ↓                        ↓
[Whisper API]           [Categorização]           [Tesseract OCR]
                               ↓
                    [Banco de Dados SQLite]
                               ↓
                    [Gerador de Relatórios]
```

## 📊 Estrutura do Banco de Dados

### Tabela: `lancamentos`
```sql
- id: INTEGER (PK)
- usuario_phone: STRING (Telefone do usuário)
- data_lancamento: DATETIME
- tipo: STRING (entrada/saida)
- valor: FLOAT
- categoria: STRING
- descricao: TEXT
- origem: STRING (texto/voz/imagem)
- dados_extras: TEXT (JSON)
```

## 🔧 APIs Disponíveis

### **Status da Aplicação**
```http
GET /status
```

### **Sistema de Inspeção Visual** 🆕
```http
GET /inspecao
```
Dashboard completo para análise e visualização de dados financeiros com:
- 📊 Estatísticas gerais (receitas, gastos, saldo)
- 🎯 Filtros avançados (usuário, data, categoria, tipo)
- 📋 Lista detalhada de lançamentos
- 🏷️ Gastos por categoria
- 📈 Evolução diária de receitas e gastos
- 🎨 Interface moderna e responsiva

**Parâmetros de Query (opcionais):**
- `usuario`: Filtrar por telefone do usuário
- `data_inicio`: Data inicial (formato: YYYY-MM-DD)
- `data_fim`: Data final (formato: YYYY-MM-DD)
- `categoria`: Filtrar por categoria específica
- `tipo`: Filtrar por tipo (receita/gasto)

### **Relatório de Usuário**
```http
GET /relatorio/{phone_number}
```

### **Webhook do WhatsApp**
```http
POST /webhook
```

## 🧪 Testes

### **Teste Local**
```bash
# Inicie o servidor
python assistente_financeiro.py

# Teste o status
curl http://localhost:5000/status
```

### **Teste de Componentes**
```python
# Teste o analisador
from assistente_financeiro import AnalisadorInteligente, ConfiguracaoAssistente

config = ConfiguracaoAssistente()
analisador = AnalisadorInteligente(config)
resultado = analisador.processar_comando_texto("Gastei 50 reais no mercado")
print(resultado)
```

## 📈 Categorias Automáticas

- **Alimentação**: mercado, supermercado, restaurante, lanche
- **Transporte**: uber, taxi, gasolina, ônibus
- **Moradia**: aluguel, luz, água, gás, internet
- **Saúde**: farmácia, médico, hospital, clínica
- **Lazer**: cinema, teatro, festa, viagem
- **Educação**: curso, livro, escola, faculdade
- **Vestuário**: roupa, sapato, acessório
- **Outros**: categoria padrão

## 🛠️ Desenvolvimento

### **Estrutura de Classes**
- `ConfiguracaoAssistente`: Configurações do sistema
- `LancamentoFinanceiro`: Modelo de dados
- `ProcessadorVoz`: Processamento de áudio (Whisper)
- `ProcessadorOCR`: Leitura de imagens (Tesseract)
- `AnalisadorInteligente`: Análise de texto e categorização
- `GeradorRelatorios`: Geração de relatórios e gráficos
- `AssistenteFinanceiro`: Classe principal

### **Padrões de Código**
- Seguindo **PEP 8**
- Type hints em todas as funções
- Docstrings completas
- Tratamento de exceções
- Logging estruturado

## 🔒 Segurança

- Validação de entrada de dados
- Sanitização de comandos
- Logs de auditoria
- Tratamento seguro de arquivos temporários

## 📝 Logs

```
2025-08-24 10:30:15 - INFO - Modelo Whisper carregado com sucesso
2025-08-24 10:30:20 - INFO - Assistente financeiro inicializado
2025-08-24 10:31:45 - INFO - Lançamento salvo: saida R$ 50.00 (alimentacao)
```

## 🚀 Deploy

### **Heroku**
```bash
# Crie um arquivo Procfile
echo "web: python assistente_financeiro.py" > Procfile

# Deploy
git add .
git commit -m "Deploy assistente financeiro"
git push heroku main
```

### **Docker**
```dockerfile
FROM python:3.9
COPY . /app
WORKDIR /app
RUN pip install -r requirements.txt
EXPOSE 5000
CMD ["python", "assistente_financeiro.py"]
```

## 📞 Suporte

Para dúvidas ou problemas:
1. Verifique os logs da aplicação
2. Teste as configurações das APIs
3. Valide as variáveis de ambiente
4. Consulte a documentação das dependências

## 📄 Licença

Este projeto foi desenvolvido seguindo as especificações técnicas fornecidas e as melhores práticas de desenvolvimento Python.

---

## 🎉 Exemplo de Uso Completo

```
Usuário: [Áudio] "Gastei sessenta reais no posto de gasolina"

Assistente: 
🚗 *Saída registrada:*
• Valor: R$ 60.00
• Categoria: Transporte
• Descrição: posto de gasolina

🎤 *Transcrição:* "Gastei sessenta reais no posto de gasolina"

---

Usuário: [Foto da nota fiscal do mercado]

Assistente:
🧾 *Nota fiscal registrada:*
• Valor: R$ 127.50
• Estabelecimento: Supermercado Extra
• Categoria: Alimentacao
• Data: 24/08/2025

✅ Lançamento salvo automaticamente!

---

Usuário: "relatório"

Assistente:
📊 *RELATÓRIO SEMANAL*

💰 *Resumo Financeiro:*
• Entradas: R$ 3000.00
• Saídas: R$ 850.00
• Saldo: R$ 2150.00 ✅

🏷️ *Gastos por Categoria:*
• Alimentacao: R$ 450.00 (52.9%)
• Transporte: R$ 250.00 (29.4%)
• Saude: R$ 150.00 (17.6%)

💡 *Insight:* Maior gasto em alimentacao
```

**O Assistente Financeiro está pronto para ajudar você a controlar sua saúde financeira! 🎯**
