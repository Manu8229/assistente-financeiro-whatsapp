#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🤖 ASSISTENTE FINANCEIRO WHATSAPP - RENDER DEPLOY
================================================

Servidor Flask otimizado para deploy no Render.com
- IA aprimorada para comandos naturais
- SQLite com persistence
- Webhook otimizado para WhatsApp/Twilio
- Logs estruturados para monitoramento
"""

import os
import sys
import sqlite3
import requests
from datetime import datetime, date, timedelta
from flask import Flask, request, jsonify
import re
import json
import logging

# ==================== CONFIGURAÇÕES ====================
app = Flask(__name__)

# Configuração para Render
PORT = int(os.environ.get('PORT', 5000))
DEBUG = os.environ.get('FLASK_ENV') != 'production'
DB_FILE = 'assistente_financeiro.db'

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ==================== BANCO DE DADOS ====================
def inicializar_banco():
    """Inicializar banco de dados SQLite"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Tabela de lançamentos financeiros
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS lancamentos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario TEXT NOT NULL,
                tipo TEXT NOT NULL,  -- 'gasto', 'receita'
                valor REAL NOT NULL,
                descricao TEXT,
                categoria TEXT,
                subcategoria TEXT,
                data_lancamento DATETIME DEFAULT CURRENT_TIMESTAMP,
                data_efetiva DATE DEFAULT (date('now')),
                observacoes TEXT,
                origem TEXT DEFAULT 'whatsapp'
            )
        ''')
        
        # Tabela de categorias personalizadas por usuário
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS categorias_usuario (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario TEXT NOT NULL,
                palavra_chave TEXT NOT NULL,
                categoria TEXT NOT NULL,
                subcategoria TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Tabela de configurações por usuário
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS configuracoes_usuario (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario TEXT NOT NULL UNIQUE,
                nome TEXT,
                limite_mensal REAL,
                moeda TEXT DEFAULT 'BRL',
                fuso_horario TEXT DEFAULT 'America/Sao_Paulo',
                notificacoes BOOLEAN DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info("✅ Banco de dados inicializado com sucesso")
        return True
        
    except Exception as e:
        logger.error(f"❌ Erro ao inicializar banco: {e}")
        return False

# ==================== PROCESSAMENTO IA ====================
def processar_comando_ia(mensagem, usuario):
    """
    IA aprimorada para processar comandos naturais em português
    
    Args:
        mensagem (str): Mensagem do usuário
        usuario (str): ID do usuário (telefone)
    
    Returns:
        str: Resposta formatada para o usuário
    """
    
    mensagem_original = mensagem
    mensagem_lower = mensagem.lower().strip()
    
    logger.info(f"🧠 Processando comando: '{mensagem}' do usuário {usuario}")
    
    # Palavras-chave para relatórios (EXPANDIDO)
    palavras_relatorio = [
        'relatório', 'relatorio', 'gastos', 'extrato', 'resumo',
        'mostre', 'mostra', 'mostrar', 'ver', 'veja', 'lista', 'listar',
        'meus gastos', 'minhas despesas', 'minha conta', 'movimentação', 
        'movimentacao', 'transações', 'transacoes', 'historico', 'histórico',
        'saldo', 'quanto gastei', 'quanto tenho', 'balanço', 'balanco',
        'conta', 'contas', 'dinheiro', 'financeiro', 'financeira'
    ]
    
    # Palavras de ajuda
    palavras_ajuda = ['ajuda', 'help', 'comandos', 'opcoes', 'opções', 'como usar']
    
    # Verificar se é pedido de ajuda
    if any(palavra in mensagem_lower for palavra in palavras_ajuda):
        return gerar_mensagem_ajuda()
    
    # Verificar se é comando de relatório
    if any(palavra in mensagem_lower for palavra in palavras_relatorio):
        return gerar_relatorio_inteligente(mensagem_lower, usuario)
    
    # Verificar se é comando de exclusão
    palavras_exclusao = ['deletar', 'delete', 'excluir', 'apagar', 'remover', 'cancelar']
    if any(palavra in mensagem_lower for palavra in palavras_exclusao):
        return processar_exclusao(mensagem_lower, usuario)
    
    # Analisar lançamento financeiro
    analise = analisar_lancamento_financeiro(mensagem_original)
    
    if analise['sucesso']:
        resultado = salvar_lancamento(
            usuario=usuario,
            tipo=analise['tipo'],
            valor=analise['valor'],
            descricao=analise['descricao'],
            categoria=analise['categoria']
        )
        
        if resultado:
            emoji = "💰" if analise['tipo'] == 'receita' else "💸"
            resposta = f"""{emoji} **{analise['tipo'].title()} registrada com sucesso!**

💵 **Valor:** R$ {analise['valor']:.2f}
📝 **Descrição:** {analise['descricao']}
🏷️ **Categoria:** {analise['categoria']}
📅 **Data:** {datetime.now().strftime('%d/%m/%Y às %H:%M')}

✅ Lançamento salvo no banco de dados!"""
        else:
            resposta = f"⚠️ {analise['tipo'].title()} identificada (R$ {analise['valor']:.2f}), mas houve erro ao salvar."
    else:
        resposta = f"""❓ **Não consegui identificar um valor válido.**

💡 **EXEMPLOS DE COMANDOS:**
• "Gastei R$ 25,00 no almoço"
• "Recebi 1000 salário"  
• "50 reais uber"
• "Paguei 200 de conta de luz"

📊 **RELATÓRIOS:**
• "Mostre meus gastos de hoje"
• "Qual meu saldo?"
• "Relatório da semana"
• "Gastos do mês"

❓ Digite **"ajuda"** para ver todos os comandos"""
    
    return resposta

def analisar_lancamento_financeiro(mensagem):
    """
    Analisar mensagem para extrair informações financeiras
    
    Returns:
        dict: {sucesso, tipo, valor, descricao, categoria}
    """
    
    mensagem_lower = mensagem.lower()
    
    # Padrões para detectar valores monetários
    padroes_valor = [
        r'r\$\s*(\d+(?:[,\.]\d{1,2})?)',  # R$ 100 ou R$ 100,50
        r'(\d+(?:[,\.]\d{1,2})?)\s*reais?',  # 100 reais
        r'(\d+(?:[,\.]\d{1,2})?)\s*r\$',  # 100 R$
        r'(\d+(?:[,\.]\d{1,2})?)(?=\s|$)',  # Número solto
    ]
    
    valor_encontrado = None
    for padrao in padroes_valor:
        matches = re.findall(padrao, mensagem_lower)
        if matches:
            try:
                valor_str = matches[0].replace(',', '.')
                valor_encontrado = float(valor_str)
                if valor_encontrado > 0:  # Validar valor positivo
                    break
            except (ValueError, IndexError):
                continue
    
    if not valor_encontrado:
        return {'sucesso': False}
    
    # Determinar tipo (receita vs gasto)
    palavras_receita = [
        'recebi', 'recebimento', 'salário', 'salario', 'renda', 'entrada',
        'ganho', 'ganhei', 'lucro', 'comissao', 'comissão', 'bonus',
        'freelance', 'trabalho', 'venda', 'vendeu', 'pagaram', 'depositou'
    ]
    
    tipo = 'receita' if any(palavra in mensagem_lower for palavra in palavras_receita) else 'gasto'
    
    # Determinar categoria automaticamente
    categoria = detectar_categoria(mensagem_lower)
    
    # Gerar descrição limpa
    descricao = gerar_descricao(mensagem, valor_encontrado)
    
    return {
        'sucesso': True,
        'tipo': tipo,
        'valor': valor_encontrado,
        'descricao': descricao,
        'categoria': categoria
    }

def detectar_categoria(texto):
    """Detectar categoria baseada em palavras-chave"""
    
    categorias = {
        'Alimentação': [
            'mercado', 'supermercado', 'padaria', 'açougue', 'acougue',
            'restaurante', 'lanchonete', 'pizzaria', 'hamburguer', 
            'almoço', 'almoco', 'jantar', 'lanche', 'comida', 'food',
            'ifood', 'uber eats', 'delivery'
        ],
        'Transporte': [
            'uber', 'taxi', 'gasolina', 'combustivel', 'combustível',
            'onibus', 'ônibus', 'metro', 'metrô', 'trem', 'passagem',
            'posto', 'estacionamento', 'pedágio', 'pedagio'
        ],
        'Moradia': [
            'aluguel', 'condominio', 'condomínio', 'luz', 'energia',
            'água', 'agua', 'gas', 'gás', 'internet', 'telefone',
            'iptu', 'reforma', 'reparo', 'manutenção', 'manutencao'
        ],
        'Saúde': [
            'farmacia', 'farmácia', 'remedios', 'remédios', 'medico',
            'médico', 'dentista', 'hospital', 'clinica', 'clínica',
            'exame', 'consulta', 'tratamento', 'plano de saude', 'plano de saúde'
        ],
        'Lazer': [
            'cinema', 'teatro', 'show', 'festa', 'bar', 'balada',
            'viagem', 'hotel', 'pousada', 'passeio', 'diversao', 'diversão',
            'jogo', 'netflix', 'spotify', 'streaming'
        ],
        'Educação': [
            'curso', 'faculdade', 'escola', 'colegio', 'colégio',
            'livro', 'material', 'mensalidade', 'matricula', 'matrícula'
        ],
        'Vestuário': [
            'roupa', 'sapato', 'tenis', 'tênis', 'camisa', 'calca', 'calça',
            'vestido', 'casaco', 'acessorio', 'acessório', 'relogio', 'relógio'
        ],
        'Trabalho': [
            'salario', 'salário', 'freelance', 'projeto', 'comissao',
            'comissão', 'bonus', 'bônus', 'hora extra', 'overtime'
        ]
    }
    
    for categoria, palavras in categorias.items():
        if any(palavra in texto for palavra in palavras):
            return categoria
    
    return 'Outros'

def gerar_descricao(mensagem_original, valor):
    """Gerar descrição limpa removendo o valor"""
    
    # Remover valores monetários da descrição
    descricao = re.sub(r'r\$\s*\d+(?:[,\.]\d{1,2})?', '', mensagem_original, flags=re.IGNORECASE)
    descricao = re.sub(r'\d+(?:[,\.]\d{1,2})?\s*reais?', '', descricao, flags=re.IGNORECASE)
    descricao = re.sub(r'\d+(?:[,\.]\d{1,2})?\s*r\$', '', descricao, flags=re.IGNORECASE)
    
    # Remover palavras de ação comuns
    palavras_remover = ['gastei', 'paguei', 'comprei', 'recebi', 'ganhei', 'no', 'na', 'do', 'da', 'de', 'com']
    palavras = descricao.split()
    palavras_filtradas = [palavra for palavra in palavras if palavra.lower().strip() not in palavras_remover]
    
    descricao_final = ' '.join(palavras_filtradas).strip()
    
    # Se ficou muito vazio, usar descrição genérica
    if len(descricao_final) < 3:
        descricao_final = f"Lançamento de R$ {valor:.2f}"
    
    return descricao_final

def gerar_relatorio_inteligente(comando, usuario):
    """Gerar relatórios baseados no comando natural"""
    
    hoje = date.today()
    
    # Detectar período solicitado
    if 'hoje' in comando:
        filtro_data = "date(data_efetiva) = ?"
        params_data = [str(hoje)]
        periodo_nome = "hoje"
        data_inicio = hoje
    elif 'ontem' in comando:
        ontem = hoje - timedelta(days=1)
        filtro_data = "date(data_efetiva) = ?"
        params_data = [str(ontem)]
        periodo_nome = "ontem"
        data_inicio = ontem
    elif 'semana' in comando:
        inicio_semana = hoje - timedelta(days=7)
        filtro_data = "date(data_efetiva) >= ?"
        params_data = [str(inicio_semana)]
        periodo_nome = "últimos 7 dias"
        data_inicio = inicio_semana
    elif 'mês' in comando or 'mes' in comando:
        filtro_data = "strftime('%Y-%m', data_efetiva) = ?"
        params_data = [hoje.strftime('%Y-%m')]
        periodo_nome = "este mês"
        data_inicio = hoje.replace(day=1)
    else:
        # Padrão: últimos 30 dias
        inicio_periodo = hoje - timedelta(days=30)
        filtro_data = "date(data_efetiva) >= ?"
        params_data = [str(inicio_periodo)]
        periodo_nome = "últimos 30 dias"
        data_inicio = inicio_periodo
    
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Query para gastos
        cursor.execute(f"""
            SELECT SUM(valor), COUNT(*) 
            FROM lancamentos 
            WHERE usuario = ? AND tipo = 'gasto' AND {filtro_data}
        """, [usuario] + params_data)
        resultado_gastos = cursor.fetchone()
        total_gastos = resultado_gastos[0] or 0
        qtd_gastos = resultado_gastos[1] or 0
        
        # Query para receitas
        cursor.execute(f"""
            SELECT SUM(valor), COUNT(*) 
            FROM lancamentos 
            WHERE usuario = ? AND tipo = 'receita' AND {filtro_data}
        """, [usuario] + params_data)
        resultado_receitas = cursor.fetchone()
        total_receitas = resultado_receitas[0] or 0
        qtd_receitas = resultado_receitas[1] or 0
        
        # Gastos por categoria
        cursor.execute(f"""
            SELECT categoria, SUM(valor), COUNT(*)
            FROM lancamentos 
            WHERE usuario = ? AND tipo = 'gasto' AND {filtro_data}
            GROUP BY categoria
            ORDER BY SUM(valor) DESC
            LIMIT 5
        """, [usuario] + params_data)
        gastos_por_categoria = cursor.fetchall()
        
        # Últimos lançamentos
        cursor.execute(f"""
            SELECT tipo, valor, descricao, categoria, date(data_efetiva)
            FROM lancamentos 
            WHERE usuario = ? AND {filtro_data}
            ORDER BY data_lancamento DESC 
            LIMIT 8
        """, [usuario] + params_data)
        ultimos_lancamentos = cursor.fetchall()
        
        conn.close()
        
        # Calcular saldo
        saldo = total_receitas - total_gastos
        saldo_emoji = "✅" if saldo >= 0 else "❌"
        
        # Montar relatório
        relatorio = f"""📊 **RELATÓRIO FINANCEIRO - {periodo_nome.upper()}**
{'═' * 50}

💰 **RESUMO GERAL:**
• 📈 Receitas: R$ {total_receitas:.2f} ({qtd_receitas} lançamentos)
• 📉 Gastos: R$ {total_gastos:.2f} ({qtd_gastos} lançamentos)
• 💵 **Saldo: R$ {saldo:.2f}** {saldo_emoji}

"""
        
        # Seção de categorias (se houver gastos)
        if gastos_por_categoria:
            relatorio += "🏷️ **GASTOS POR CATEGORIA:**\n"
            for categoria, valor, quantidade in gastos_por_categoria:
                percentual = (valor / total_gastos * 100) if total_gastos > 0 else 0
                relatorio += f"• {categoria}: R$ {valor:.2f} ({percentual:.1f}%)\n"
            relatorio += "\n"
        
        # Últimos lançamentos
        if ultimos_lancamentos:
            relatorio += "📋 **ÚLTIMOS LANÇAMENTOS:**\n"
            for tipo, valor, desc, categoria, data_efetiva in ultimos_lancamentos:
                emoji = "💰" if tipo == "receita" else "💸"
                data_formatada = datetime.strptime(data_efetiva, '%Y-%m-%d').strftime('%d/%m')
                relatorio += f"{emoji} {data_formatada} - R$ {valor:.2f} - {desc}\n"
        else:
            relatorio += "📭 **Nenhum lançamento encontrado no período.**\n"
        
        relatorio += f"\n🕒 Gerado em {datetime.now().strftime('%H:%M - %d/%m/%Y')}"
        
        logger.info(f"📊 Relatório gerado para {usuario}: {periodo_nome}")
        return relatorio
        
    except Exception as e:
        logger.error(f"❌ Erro ao gerar relatório: {e}")
        return f"❌ **Erro ao consultar dados:** {str(e)}\n\nTente novamente em alguns segundos."

def processar_exclusao(comando, usuario):
    """Processar comandos de exclusão de lançamentos"""
    
    # Por enquanto, retorna instrução de exclusão manual
    return """🗑️ **EXCLUSÃO DE LANÇAMENTOS**

Para excluir lançamentos, você pode:

📱 **Via WhatsApp:**
• "deletar último gasto"
• "remover último lançamento"
• "cancelar receita de 1000"

🔍 **Para ver seus últimos lançamentos:**
• "relatório de hoje"
• "meus gastos recentes"

⚠️ **Atenção:** Exclusões são permanentes!"""

def gerar_mensagem_ajuda():
    """Gerar mensagem de ajuda completa"""
    
    return """🤖 **ASSISTENTE FINANCEIRO - AJUDA**
{'═' * 40}

💰 **REGISTRAR GASTOS/RECEITAS:**
• "Gastei 50 reais no mercado"
• "Paguei 200 de conta de luz"
• "Recebi 1000 de salário"
• "25,50 almoço"

📊 **RELATÓRIOS:**
• "Mostre meus gastos de hoje"
• "Relatório da semana"
• "Qual meu saldo do mês?"
• "Gastos por categoria"

🏷️ **CATEGORIAS AUTOMÁTICAS:**
Alimentação, Transporte, Moradia, Saúde, Lazer, Educação, Vestuário, Trabalho, Outros

🎤 **COMANDOS DE VOZ:**
• Grave um áudio falando seus gastos
• "Paguei quarenta reais de gasolina"

📱 **COMANDOS ESPECIAIS:**
• "ajuda" - Esta mensagem
• "relatório" - Resumo geral
• "saldo" - Saldo atual

✨ **DICAS:**
• Use linguagem natural
• Valores em reais (R$ ou reais)
• Seja específico na descrição

❓ **Dúvidas?** Fale comigo em linguagem natural!"""

def salvar_lancamento(usuario, tipo, valor, descricao, categoria='Outros'):
    """Salvar lançamento no banco de dados"""
    
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO lancamentos 
            (usuario, tipo, valor, descricao, categoria, data_efetiva)
            VALUES (?, ?, ?, ?, ?, date('now'))
        """, (usuario, tipo, valor, descricao, categoria))
        
        lancamento_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        logger.info(f"💾 Lançamento salvo: {tipo} R$ {valor:.2f} para {usuario}")
        return lancamento_id
        
    except Exception as e:
        logger.error(f"❌ Erro ao salvar lançamento: {e}")
        return False

# ==================== ROUTES FLASK ====================

@app.route('/')
def home():
    """Página inicial com status do sistema"""
    
    # Estatísticas básicas
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM lancamentos")
        total_lancamentos = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(DISTINCT usuario) FROM lancamentos")
        total_usuarios = cursor.fetchone()[0]
        
        conn.close()
    except:
        total_lancamentos = 0
        total_usuarios = 0
    
    return f"""
<!DOCTYPE html>
<html>
<head>
    <title>🤖 Assistente Financeiro WhatsApp</title>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }}
        .container {{ max-width: 600px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        .status {{ background: #e8f5e8; padding: 15px; border-radius: 5px; margin: 20px 0; }}
        .stats {{ background: #f0f8ff; padding: 15px; border-radius: 5px; margin: 20px 0; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🤖 Assistente Financeiro WhatsApp</h1>
        
        <div class="status">
            <h3>✅ Sistema Online</h3>
            <p><strong>Status:</strong> Funcionando</p>
            <p><strong>Hora:</strong> {datetime.now().strftime('%H:%M:%S - %d/%m/%Y')}</p>
            <p><strong>Ambiente:</strong> {'Produção' if not DEBUG else 'Desenvolvimento'}</p>
        </div>
        
        <div class="stats">
            <h3>📊 Estatísticas</h3>
            <p><strong>Total de Lançamentos:</strong> {total_lancamentos}</p>
            <p><strong>Usuários Ativos:</strong> {total_usuarios}</p>
        </div>
        
        <h3>📱 Configuração WhatsApp</h3>
        <p><strong>Webhook URL:</strong></p>
        <code>{request.url_root}webhook</code>
        
        <h3>🎯 Comandos Suportados</h3>
        <ul>
            <li>"Gastei 50 reais no mercado"</li>
            <li>"Recebi 1000 de salário"</li>
            <li>"Mostre meus gastos de hoje"</li>
            <li>"Qual meu saldo?"</li>
            <li>"Relatório da semana"</li>
        </ul>
        
        <p><em>Deploy otimizado para Render.com</em></p>
    </div>
</body>
</html>
    """

@app.route('/webhook', methods=['POST'])
def webhook():
    """Endpoint principal do webhook para WhatsApp via Twilio"""
    
    try:
        # Log inicial
        logger.info("🔄 Webhook chamado - iniciando processamento")
        
        # Capturar dados do Twilio
        from_number = request.form.get('From', '')
        message_body = request.form.get('Body', '').strip()
        profile_name = request.form.get('ProfileName', 'Usuário')
        message_type = request.form.get('MessageType', 'text')
        
        # Log detalhado da requisição
        logger.info(f"📨 Webhook recebido:")
        logger.info(f"   From: {from_number}")
        logger.info(f"   Body: '{message_body}'")
        logger.info(f"   Profile: {profile_name}")
        logger.info(f"   Type: {message_type}")
        
        if not message_body:
            logger.warning("⚠️ Mensagem vazia recebida")
            return "❌ Mensagem vazia", 400
        
        # Processar comando com IA
        logger.info("🧠 Iniciando processamento IA...")
        resposta = processar_comando_ia(message_body, from_number)
        logger.info(f"✅ IA processou: {len(resposta)} caracteres gerados")
        
        logger.info(f"📤 Enviando resposta para {from_number}")
        
        # Retornar resposta em formato TwiML
        try:
            from twilio.twiml.messaging_response import MessagingResponse
            twiml_response = MessagingResponse()
            twiml_response.message(resposta)
            logger.info("📱 Resposta TwiML criada")
            return str(twiml_response), 200, {'Content-Type': 'text/xml'}
        except ImportError:
            # Fallback se Twilio não estiver disponível
            logger.warning("⚠️ Twilio TwiML não disponível, usando resposta simples")
            return resposta, 200, {'Content-Type': 'text/plain; charset=utf-8'}
    
    except Exception as e:
        logger.error(f"❌ Erro no webhook: {e}")
        import traceback
        logger.error(f"❌ Traceback: {traceback.format_exc()}")
        return f"Erro interno: {str(e)}", 500

@app.route('/teste')
def teste():
    """Página de teste do webhook"""
    try:
        with open('teste_webhook.html', 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return """
        <h1>Página de teste não encontrada</h1>
        <p>Arquivo teste_webhook.html não foi encontrado.</p>
        <p><a href="/">Voltar ao início</a></p>
        """

@app.route('/status')
def status():
    """Endpoint de status para monitoramento"""
    
    return jsonify({
        'status': 'online',
        'timestamp': datetime.now().isoformat(),
        'version': '2.0',
        'environment': 'production' if not DEBUG else 'development'
    })

@app.route('/health')
def health():
    """Health check para Render"""
    
    try:
        # Teste básico do banco
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        conn.close()
        
        return jsonify({'status': 'healthy'}), 200
    except Exception as e:
        return jsonify({'status': 'unhealthy', 'error': str(e)}), 500

# ==================== INICIALIZAÇÃO ====================
def main():
    """Função principal"""
    
    logger.info("🚀 Iniciando Assistente Financeiro para Render.com")
    
    # Inicializar banco de dados
    if not inicializar_banco():
        logger.error("❌ Falha ao inicializar banco de dados")
        sys.exit(1)
    
    logger.info(f"🌐 Configuração:")
    logger.info(f"   - Porta: {PORT}")
    logger.info(f"   - Debug: {DEBUG}")
    logger.info(f"   - Banco: {DB_FILE}")
    
    # Iniciar servidor Flask
    app.run(
        host='0.0.0.0',
        port=PORT,
        debug=DEBUG,
        threaded=True
    )

if __name__ == '__main__':
    main()
