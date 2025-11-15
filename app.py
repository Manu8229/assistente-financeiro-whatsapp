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
        
        <div style="text-align: center; margin-top: 30px;">
            <a href="/inspecao" style="background: #28a745; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; display: inline-block;">
                🔍 Sistema de Inspeção Visual
            </a>
        </div>
    </div>
</body>
</html>
    """

@app.route('/inspecao')
def inspecao_visual():
    """Sistema de Inspeção Visual - Dashboard completo"""
    
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Obter parâmetros de filtro
        usuario_filtro = request.args.get('usuario', '')
        data_inicio = request.args.get('data_inicio', '')
        data_fim = request.args.get('data_fim', '')
        categoria_filtro = request.args.get('categoria', '')
        tipo_filtro = request.args.get('tipo', '')
        
        # Construir query base
        where_clauses = []
        params = []
        
        if usuario_filtro:
            where_clauses.append("usuario LIKE ?")
            params.append(f"%{usuario_filtro}%")
        
        if data_inicio:
            where_clauses.append("date(data_efetiva) >= ?")
            params.append(data_inicio)
        
        if data_fim:
            where_clauses.append("date(data_efetiva) <= ?")
            params.append(data_fim)
        
        if categoria_filtro:
            where_clauses.append("categoria = ?")
            params.append(categoria_filtro)
        
        if tipo_filtro:
            where_clauses.append("tipo = ?")
            params.append(tipo_filtro)
        
        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
        
        # Estatísticas gerais
        cursor.execute(f"""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN tipo = 'receita' THEN valor ELSE 0 END) as total_receitas,
                SUM(CASE WHEN tipo = 'gasto' THEN valor ELSE 0 END) as total_gastos,
                COUNT(DISTINCT usuario) as total_usuarios,
                COUNT(DISTINCT categoria) as total_categorias
            FROM lancamentos
            WHERE {where_sql}
        """, params)
        stats = cursor.fetchone()
        
        total_lancamentos = stats[0] or 0
        total_receitas = stats[1] or 0
        total_gastos = stats[2] or 0
        total_usuarios = stats[3] or 0
        total_categorias = stats[4] or 0
        saldo = total_receitas - total_gastos
        
        # Gastos por categoria
        cursor.execute(f"""
            SELECT categoria, SUM(valor) as total, COUNT(*) as quantidade
            FROM lancamentos
            WHERE tipo = 'gasto' AND {where_sql}
            GROUP BY categoria
            ORDER BY total DESC
        """, params)
        gastos_categoria = cursor.fetchall()
        
        # Receitas por categoria
        cursor.execute(f"""
            SELECT categoria, SUM(valor) as total, COUNT(*) as quantidade
            FROM lancamentos
            WHERE tipo = 'receita' AND {where_sql}
            GROUP BY categoria
            ORDER BY total DESC
        """, params)
        receitas_categoria = cursor.fetchall()
        
        # Lista de todas as categorias para o filtro
        cursor.execute("SELECT DISTINCT categoria FROM lancamentos ORDER BY categoria")
        todas_categorias = [row[0] for row in cursor.fetchall()]
        
        # Últimos lançamentos
        cursor.execute(f"""
            SELECT id, usuario, tipo, valor, descricao, categoria, 
                   date(data_efetiva), datetime(data_lancamento), origem
            FROM lancamentos
            WHERE {where_sql}
            ORDER BY data_lancamento DESC
            LIMIT 50
        """, params)
        lancamentos = cursor.fetchall()
        
        # Evolução diária
        cursor.execute(f"""
            SELECT date(data_efetiva) as data, 
                   SUM(CASE WHEN tipo = 'receita' THEN valor ELSE 0 END) as receitas,
                   SUM(CASE WHEN tipo = 'gasto' THEN valor ELSE 0 END) as gastos
            FROM lancamentos
            WHERE {where_sql}
            GROUP BY date(data_efetiva)
            ORDER BY date(data_efetiva) DESC
            LIMIT 30
        """, params)
        evolucao_diaria = cursor.fetchall()
        
        conn.close()
        
        # Gerar HTML do dashboard
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🔍 Sistema de Inspeção Visual - Assistente Financeiro</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}
        .container {{ max-width: 1400px; margin: 0 auto; }}
        .header {{ 
            background: white; 
            padding: 30px; 
            border-radius: 15px; 
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }}
        .header h1 {{ 
            color: #333; 
            margin-bottom: 10px;
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        .header p {{ color: #666; }}
        
        .stats-grid {{ 
            display: grid; 
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); 
            gap: 20px; 
            margin-bottom: 20px;
        }}
        .stat-card {{ 
            background: white; 
            padding: 25px; 
            border-radius: 15px; 
            box-shadow: 0 4px 20px rgba(0,0,0,0.08);
            transition: transform 0.3s, box-shadow 0.3s;
        }}
        .stat-card:hover {{ 
            transform: translateY(-5px);
            box-shadow: 0 8px 30px rgba(0,0,0,0.15);
        }}
        .stat-card .label {{ 
            color: #666; 
            font-size: 14px; 
            margin-bottom: 10px;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .stat-card .value {{ 
            font-size: 32px; 
            font-weight: bold; 
            color: #333;
        }}
        .stat-card .subtext {{ 
            color: #999; 
            font-size: 12px; 
            margin-top: 5px;
        }}
        .stat-card.receita .value {{ color: #28a745; }}
        .stat-card.gasto .value {{ color: #dc3545; }}
        .stat-card.saldo .value {{ color: {('#28a745' if saldo >= 0 else '#dc3545')}; }}
        
        .filters {{ 
            background: white; 
            padding: 25px; 
            border-radius: 15px; 
            box-shadow: 0 4px 20px rgba(0,0,0,0.08);
            margin-bottom: 20px;
        }}
        .filters h3 {{ 
            margin-bottom: 15px; 
            color: #333;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .filter-grid {{ 
            display: grid; 
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); 
            gap: 15px;
            margin-bottom: 15px;
        }}
        .filter-group {{ display: flex; flex-direction: column; }}
        .filter-group label {{ 
            font-size: 13px; 
            color: #666; 
            margin-bottom: 5px;
            font-weight: 500;
        }}
        .filter-group input, .filter-group select {{ 
            padding: 10px; 
            border: 2px solid #e0e0e0; 
            border-radius: 8px;
            font-size: 14px;
            transition: border-color 0.3s;
        }}
        .filter-group input:focus, .filter-group select:focus {{ 
            outline: none;
            border-color: #667eea;
        }}
        .btn {{ 
            padding: 12px 24px; 
            border: none; 
            border-radius: 8px; 
            cursor: pointer;
            font-size: 14px;
            font-weight: 600;
            transition: all 0.3s;
            display: inline-flex;
            align-items: center;
            gap: 8px;
        }}
        .btn-primary {{ 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
            color: white;
        }}
        .btn-primary:hover {{ 
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
        }}
        .btn-secondary {{ 
            background: #6c757d; 
            color: white;
        }}
        .btn-secondary:hover {{ 
            background: #5a6268;
        }}
        
        .content-grid {{ 
            display: grid; 
            grid-template-columns: 2fr 1fr; 
            gap: 20px;
            margin-bottom: 20px;
        }}
        
        @media (max-width: 1024px) {{
            .content-grid {{ grid-template-columns: 1fr; }}
        }}
        
        .panel {{ 
            background: white; 
            padding: 25px; 
            border-radius: 15px; 
            box-shadow: 0 4px 20px rgba(0,0,0,0.08);
        }}
        .panel h3 {{ 
            margin-bottom: 20px; 
            color: #333;
            display: flex;
            align-items: center;
            gap: 8px;
            padding-bottom: 15px;
            border-bottom: 2px solid #f0f0f0;
        }}
        
        .transactions-table {{ 
            width: 100%; 
            border-collapse: collapse;
            margin-top: 15px;
        }}
        .transactions-table th {{ 
            background: #f8f9fa; 
            padding: 12px; 
            text-align: left; 
            font-size: 13px;
            font-weight: 600;
            color: #666;
            border-bottom: 2px solid #e0e0e0;
        }}
        .transactions-table td {{ 
            padding: 12px; 
            border-bottom: 1px solid #f0f0f0;
            font-size: 14px;
        }}
        .transactions-table tr:hover {{ 
            background: #f8f9fa;
        }}
        
        .badge {{ 
            display: inline-block; 
            padding: 4px 12px; 
            border-radius: 20px; 
            font-size: 12px;
            font-weight: 600;
        }}
        .badge-receita {{ background: #d4edda; color: #155724; }}
        .badge-gasto {{ background: #f8d7da; color: #721c24; }}
        
        .category-item {{ 
            display: flex; 
            justify-content: space-between; 
            align-items: center;
            padding: 12px;
            border-bottom: 1px solid #f0f0f0;
            transition: background 0.3s;
        }}
        .category-item:hover {{ 
            background: #f8f9fa;
        }}
        .category-item:last-child {{ 
            border-bottom: none;
        }}
        .category-name {{ 
            font-weight: 500; 
            color: #333;
        }}
        .category-value {{ 
            font-weight: 600; 
            color: #dc3545;
        }}
        .category-count {{ 
            font-size: 12px; 
            color: #999;
            margin-left: 10px;
        }}
        
        .timeline {{ margin-top: 15px; }}
        .timeline-item {{ 
            padding: 12px;
            border-left: 3px solid #e0e0e0;
            margin-bottom: 10px;
            padding-left: 15px;
        }}
        .timeline-item.receita {{ border-left-color: #28a745; }}
        .timeline-item.gasto {{ border-left-color: #dc3545; }}
        .timeline-date {{ 
            font-size: 12px; 
            color: #999;
            margin-bottom: 5px;
        }}
        .timeline-values {{ 
            display: flex; 
            gap: 15px;
            font-size: 14px;
        }}
        .timeline-values span {{ 
            font-weight: 600;
        }}
        .timeline-values .receita {{ color: #28a745; }}
        .timeline-values .gasto {{ color: #dc3545; }}
        
        .empty-state {{ 
            text-align: center; 
            padding: 40px;
            color: #999;
        }}
        .empty-state svg {{ 
            width: 64px; 
            height: 64px; 
            margin-bottom: 15px;
            opacity: 0.3;
        }}
        
        .back-link {{ 
            display: inline-flex;
            align-items: center;
            gap: 8px;
            color: #667eea;
            text-decoration: none;
            font-weight: 600;
            margin-top: 20px;
            transition: all 0.3s;
        }}
        .back-link:hover {{ 
            gap: 12px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>
                🔍 Sistema de Inspeção Visual
            </h1>
            <p>Dashboard completo para análise de dados financeiros em tempo real</p>
        </div>
        
        <div class="stats-grid">
            <div class="stat-card">
                <div class="label">📊 Total de Lançamentos</div>
                <div class="value">{total_lancamentos}</div>
                <div class="subtext">{total_usuarios} usuário(s) · {total_categorias} categoria(s)</div>
            </div>
            <div class="stat-card receita">
                <div class="label">💰 Receitas Totais</div>
                <div class="value">R$ {total_receitas:,.2f}</div>
                <div class="subtext">{sum(1 for l in lancamentos if l[2] == 'receita')} lançamento(s)</div>
            </div>
            <div class="stat-card gasto">
                <div class="label">💸 Gastos Totais</div>
                <div class="value">R$ {total_gastos:,.2f}</div>
                <div class="subtext">{sum(1 for l in lancamentos if l[2] == 'gasto')} lançamento(s)</div>
            </div>
            <div class="stat-card saldo">
                <div class="label">💵 Saldo Líquido</div>
                <div class="value">R$ {saldo:,.2f}</div>
                <div class="subtext">{'Positivo ✅' if saldo >= 0 else 'Negativo ⚠️'}</div>
            </div>
        </div>
        
        <div class="filters">
            <h3>🎯 Filtros de Busca</h3>
            <form method="GET" action="/inspecao">
                <div class="filter-grid">
                    <div class="filter-group">
                        <label>Usuário (telefone)</label>
                        <input type="text" name="usuario" value="{usuario_filtro}" placeholder="Ex: +5511999999999">
                    </div>
                    <div class="filter-group">
                        <label>Data Início</label>
                        <input type="date" name="data_inicio" value="{data_inicio}">
                    </div>
                    <div class="filter-group">
                        <label>Data Fim</label>
                        <input type="date" name="data_fim" value="{data_fim}">
                    </div>
                    <div class="filter-group">
                        <label>Categoria</label>
                        <select name="categoria">
                            <option value="">Todas as categorias</option>
                            {''.join([f'<option value="{cat}" {"selected" if cat == categoria_filtro else ""}>{cat}</option>' for cat in todas_categorias])}
                        </select>
                    </div>
                    <div class="filter-group">
                        <label>Tipo</label>
                        <select name="tipo">
                            <option value="">Todos os tipos</option>
                            <option value="receita" {"selected" if tipo_filtro == "receita" else ""}>Receita</option>
                            <option value="gasto" {"selected" if tipo_filtro == "gasto" else ""}>Gasto</option>
                        </select>
                    </div>
                </div>
                <div style="margin-top: 15px; display: flex; gap: 10px;">
                    <button type="submit" class="btn btn-primary">🔍 Aplicar Filtros</button>
                    <a href="/inspecao" class="btn btn-secondary">🔄 Limpar Filtros</a>
                </div>
            </form>
        </div>
        
        <div class="content-grid">
            <div class="panel">
                <h3>📋 Lançamentos Recentes (últimos 50)</h3>
                {f'''
                <table class="transactions-table">
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Data</th>
                            <th>Tipo</th>
                            <th>Valor</th>
                            <th>Descrição</th>
                            <th>Categoria</th>
                            <th>Usuário</th>
                        </tr>
                    </thead>
                    <tbody>
                        {''.join([f"""
                        <tr>
                            <td>#{l[0]}</td>
                            <td>{datetime.strptime(l[6], '%Y-%m-%d').strftime('%d/%m/%Y')}</td>
                            <td><span class="badge badge-{l[2]}">{l[2].title()}</span></td>
                            <td style="font-weight: 600; color: {'#28a745' if l[2] == 'receita' else '#dc3545'}">R$ {l[3]:,.2f}</td>
                            <td>{l[4]}</td>
                            <td>{l[5]}</td>
                            <td style="font-size: 11px; color: #999;">{l[1][-15:]}</td>
                        </tr>
                        """ for l in lancamentos])}
                    </tbody>
                </table>
                ''' if lancamentos else '<div class="empty-state">📭<br>Nenhum lançamento encontrado com os filtros aplicados</div>'}
            </div>
            
            <div>
                <div class="panel" style="margin-bottom: 20px;">
                    <h3>🏷️ Gastos por Categoria</h3>
                    {f'''
                    {''.join([f"""
                    <div class="category-item">
                        <span class="category-name">{cat[0]}</span>
                        <div>
                            <span class="category-value">R$ {cat[1]:,.2f}</span>
                            <span class="category-count">({cat[2]} lançamentos)</span>
                        </div>
                    </div>
                    """ for cat in gastos_categoria])}
                    ''' if gastos_categoria else '<div class="empty-state">Nenhum gasto registrado</div>'}
                </div>
                
                <div class="panel">
                    <h3>📈 Evolução Diária</h3>
                    <div class="timeline">
                        {f'''
                        {''.join([f"""
                        <div class="timeline-item {('receita' if ev[1] > ev[2] else 'gasto')}">
                            <div class="timeline-date">{datetime.strptime(ev[0], '%Y-%m-%d').strftime('%d/%m/%Y')}</div>
                            <div class="timeline-values">
                                <div class="receita">▲ R$ {ev[1]:,.2f}</div>
                                <div class="gasto">▼ R$ {ev[2]:,.2f}</div>
                            </div>
                        </div>
                        """ for ev in evolucao_diaria[:10]])}
                        ''' if evolucao_diaria else '<div class="empty-state">Sem dados de evolução</div>'}
                    </div>
                </div>
            </div>
        </div>
        
        <div style="text-align: center;">
            <a href="/" class="back-link">← Voltar para Home</a>
        </div>
    </div>
</body>
</html>
        """
        
        return html
        
    except Exception as e:
        logger.error(f"❌ Erro no sistema de inspeção: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return f"""
        <h1>Erro no Sistema de Inspeção</h1>
        <p>Ocorreu um erro: {str(e)}</p>
        <p><a href="/">Voltar</a></p>
        """, 500

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
