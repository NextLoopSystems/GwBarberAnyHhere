import os
import psycopg2
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
from datetime import datetime, date, timedelta
import re
from decimal import Decimal
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from psycopg2.extras import DictCursor

app = Flask(__name__)
# Chave secreta para a segurança da sessão.
app.secret_key = 'sua-chave-secreta-muito-segura-e-aleatoria-aqui'

# --- FUNÇÕES AUXILIARES ---

def get_db_connection():
    """Cria e retorna uma nova conexão com o banco de dados."""
    conn_string = 'postgresql://postgres:n3xtl00p%402025**@56.124.104.35:5432/gwbarber_db'
    conn = psycopg2.connect(conn_string)
    return conn

def login_required(f):
    """Decorator para exigir login em certas rotas."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Por favor, faça login para acessar esta página.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """Decorator para exigir que o usuário seja admin."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('is_admin'):
            flash('Acesso negado. Esta área é apenas para administradores.', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# --- ROTAS DE AUTENTICAÇÃO ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario = request.form['usuario']
        senha = request.form['senha']
        
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, usuario, senha_hash, is_admin FROM registro_usuarios WHERE usuario = %s", (usuario,))
        user = cur.fetchone()
        cur.close()
        conn.close()

        if user and check_password_hash(user[2], senha):
            session.clear()
            session['user_id'] = user[0]
            session['usuario'] = user[1]
            session['is_admin'] = user[3]
            return redirect(url_for('index'))
        else:
            flash('Usuário ou senha inválidos.', 'danger')
    return render_template('login.html')

@app.route('/registrar', methods=['GET', 'POST'])
@login_required
@admin_required
def registrar():
    if request.method == 'POST':
        usuario = request.form['usuario']
        senha = request.form['senha']
        email = request.form.get('email')
        telefone = request.form.get('telefone')
        cpf = request.form.get('cpf')

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id FROM registro_usuarios WHERE usuario = %s", (usuario,))
        
        if cur.fetchone():
            flash('Este nome de usuário já existe. Por favor, escolha outro.', 'danger')
        else:
            senha_hash = generate_password_hash(senha)
            cur.execute("INSERT INTO registro_usuarios (usuario, senha_hash, email, telefone, cpf) VALUES (%s, %s, %s, %s, %s)",
                        (usuario, senha_hash, email, telefone, cpf))
            conn.commit()
            flash('Usuário registrado com sucesso!', 'success')
            return redirect(url_for('usuarios_lista'))
        
        cur.close()
        conn.close()
    return render_template('registrar_usuario.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Você saiu da sua conta.', 'info')
    return redirect(url_for('login'))

# --- ROTAS PRINCIPAIS ---

@app.route('/')
@login_required
def index():
    return render_template('menu.html')

# --- ROTAS DE CADASTRO ---

@app.route('/registro/servico', methods=['GET', 'POST'])
@login_required
def registro_servico():
    if request.method == 'POST':
        conn = None; cur = None
        try:
            data = request.get_json()
            valor_str = data.get('valor', 'R$ 0,00'); valor_limpo = re.sub(r'[^\d,]', '', valor_str).replace(',', '.'); valor_numeric = float(valor_limpo) if valor_limpo else 0.0
            data_servico_dt = datetime.fromisoformat(data.get('dataHora')) if data.get('dataHora') else None
            data_final_str = data.get('dataFinal'); data_final_dt = datetime.strptime(data_final_str, '%d/%m/%Y').date() if data_final_str else None
            conn = get_db_connection(); cur = conn.cursor()
            sql = "INSERT INTO registro_servico (barbeiro, servico, cliente, valor, data_servico, data_final) VALUES (%s, %s, %s, %s, %s, %s)"
            record = (data.get('barbeiro'), data.get('servico'), data.get('cliente'), valor_numeric, data_servico_dt, data_final_dt)
            cur.execute(sql, record); conn.commit()
            return jsonify({'success': True, 'message': 'Serviço registrado com sucesso!'}), 201
        except (Exception, psycopg2.Error) as error:
            print(f"Erro ao inserir serviço: {error}"); return jsonify({'success': False, 'message': 'Ocorreu um erro no servidor.'}), 500
        finally:
            if cur is not None: cur.close()
            if conn is not None: conn.close()
    return render_template('registro_servico.html')

@app.route('/registro/produto', methods=['GET', 'POST'])
@login_required
def registro_produto():
    if request.method == 'POST':
        conn = None; cur = None
        try:
            data = request.get_json(); conn = get_db_connection(); cur = conn.cursor()
            sql = "INSERT INTO registro_produto (nome_produto, quantidade, valor_unitario) VALUES (%s, %s, %s)"
            record = (data.get('nome_do_produto'), data.get('quantidade'), data.get('valor_Uni'))
            cur.execute(sql, record); conn.commit()
            return jsonify({'success': True, 'message': 'Produto registrado com sucesso!'}), 201
        except (Exception, psycopg2.Error) as error:
            print(f"Erro ao inserir produto: {error}"); return jsonify({'success': False, 'message': 'Ocorreu um erro no servidor.'}), 500
        finally:
            if cur is not None: cur.close()
            if conn is not None: conn.close()
    return render_template('registro_produto.html')

@app.route('/registro/venda', methods=['GET', 'POST'])
@login_required
def registro_venda():
    if request.method == 'POST':
        conn = None; cur = None
        try:
            data = request.get_json(); produto_vendido = data.get('produto'); quantidade_vendida = int(data.get('quantidade'))
            conn = get_db_connection(); cur = conn.cursor()
            cur.execute("SELECT quantidade FROM registro_produto WHERE nome_produto = %s FOR UPDATE", (produto_vendido,)); estoque_atual = cur.fetchone()
            if estoque_atual is None or estoque_atual[0] < quantidade_vendida: return jsonify({'success': False, 'message': 'Estoque insuficiente!'}), 400
            cur.execute("UPDATE registro_produto SET quantidade = quantidade - %s WHERE nome_produto = %s", (quantidade_vendida, produto_vendido))
            valor_str = data.get('valor', 'R$ 0,00'); valor_limpo = re.sub(r'[^\d,]', '', valor_str).replace(',', '.'); valor_total_numeric = float(valor_limpo) if valor_limpo else 0.0
            sql = "INSERT INTO registro_venda (barbeiro, produto_nome, quantidade, valor_total, data_venda) VALUES (%s, %s, %s, %s, %s)"
            record = (data.get('barbeiro'), produto_vendido, quantidade_vendida, valor_total_numeric, datetime.fromisoformat(data.get('dataHoraVenda')))
            cur.execute(sql, record); conn.commit()
            return jsonify({'success': True, 'message': 'Venda registrada com sucesso!'}), 201
        except (Exception, psycopg2.Error) as error:
            if conn: conn.rollback(); print(f"Erro ao registrar venda: {error}"); return jsonify({'success': False, 'message': 'Ocorreu um erro no servidor.'}), 500
        finally:
            if cur is not None: cur.close()
            if conn is not None: conn.close()
    return render_template('registro_venda.html')


# --- ROTAS DE VISUALIZAÇÃO ---

@app.route('/servicos')
@login_required
def servicos_lista():
    return render_template('servicos_lista.html')

@app.route('/vendas')
@login_required
def vendas_lista():
    return render_template('vendas_lista.html')

@app.route('/produtos')
@login_required
def produtos_lista():
    return render_template('produtos_lista.html')

@app.route('/usuarios')
@login_required
@admin_required
def usuarios_lista():
    return render_template('usuarios_lista.html')

# --- ROTAS DA API ---

@app.route('/api/produtos')
@login_required
def api_produtos():
    conn = None; cur = None
    try:
        conn = get_db_connection(); cur = conn.cursor()
        cur.execute("SELECT id, nome_produto, quantidade, valor_unitario FROM registro_produto ORDER BY nome_produto ASC")
        colnames = [desc[0] for desc in cur.description]; produtos = [dict(zip(colnames, row)) for row in cur.fetchall()]
        return jsonify(produtos)
    except (Exception, psycopg2.Error) as error:
        print(f"Erro ao buscar produtos: {error}"); return jsonify({"error": "Não foi possível carregar os produtos"}), 500
    finally:
        if cur is not None: cur.close()
        if conn is not None: conn.close()

@app.route('/api/servicos')
@login_required
def api_servicos():
    conn = None; cur = None
    try:
        conn = get_db_connection(); cur = conn.cursor()
        cur.execute("SELECT id, barbeiro, servico, cliente, valor, data_servico, data_final FROM registro_servico ORDER BY data_servico DESC")
        colnames = [desc[0] for desc in cur.description]; servicos = [dict(zip(colnames, row)) for row in cur.fetchall()]
        return jsonify(servicos)
    except (Exception, psycopg2.Error) as error:
        print(f"Erro ao buscar serviços: {error}"); return jsonify({"error": "Não foi possível carregar os serviços"}), 500
    finally:
        if cur is not None: cur.close()
        if conn is not None: conn.close()

@app.route('/api/vendas')
@login_required
def api_vendas():
    conn = None; cur = None
    try:
        conn = get_db_connection(); cur = conn.cursor()
        cur.execute("SELECT id, barbeiro, produto_nome, quantidade, valor_total, data_venda FROM registro_venda ORDER BY data_venda DESC")
        colnames = [desc[0] for desc in cur.description]; vendas = [dict(zip(colnames, row)) for row in cur.fetchall()]
        return jsonify(vendas)
    except (Exception, psycopg2.Error) as error:
        print(f"Erro ao buscar vendas: {error}"); return jsonify({"error": "Não foi possível carregar as vendas"}), 500
    finally:
        if cur is not None: cur.close()
        if conn is not None: conn.close()

@app.route('/api/usuarios')
@login_required
@admin_required
def api_usuarios():
    conn = get_db_connection(); cur = conn.cursor()
    cur.execute("SELECT id, usuario, email, telefone, cpf, is_admin FROM registro_usuarios ORDER BY id ASC")
    colnames = [desc[0] for desc in cur.description]
    usuarios = [dict(zip(colnames, row)) for row in cur.fetchall()]
    cur.close(); conn.close()
    return jsonify(usuarios)

# --- ROTAS DE MANIPULAÇÃO DE DADOS ---

@app.route('/api/servico/<int:servico_id>', methods=['DELETE', 'PUT'])
@login_required
def api_manipular_servico(servico_id):
    conn = None; cur = None
    try:
        conn = get_db_connection(); cur = conn.cursor()
        if request.method == 'DELETE':
            cur.execute("DELETE FROM registro_servico WHERE id = %s", (servico_id,)); conn.commit()
            if cur.rowcount == 0: return jsonify({'success': False, 'message': 'Serviço não encontrado'}), 404
            return jsonify({'success': True, 'message': 'Serviço deletado com sucesso!'})
        elif request.method == 'PUT':
            data = request.get_json(); valor_numeric = float(data.get('valor')) if data.get('valor') else 0.0
            data_servico_dt = datetime.fromisoformat(data.get('data_servico')) if data.get('data_servico') else None
            data_final_str = data.get('data_final'); data_final_dt = datetime.strptime(data_final_str, '%Y-%m-%d').date() if data_final_str else None
            sql = "UPDATE registro_servico SET barbeiro = %s, servico = %s, cliente = %s, valor = %s, data_servico = %s, data_final = %s WHERE id = %s"
            record = (data.get('barbeiro'), data.get('servico'), data.get('cliente'), valor_numeric, data_servico_dt, data_final_dt, servico_id)
            cur.execute(sql, record); conn.commit()
            if cur.rowcount == 0: return jsonify({'success': False, 'message': 'Serviço não encontrado'}), 404
            return jsonify({'success': True, 'message': 'Serviço atualizado com sucesso!'})
    except (Exception, psycopg2.Error) as error:
        if conn: conn.rollback(); print(f"Erro ao manipular serviço: {error}"); return jsonify({'success': False, 'message': 'Ocorreu um erro no servidor.'}), 500
    finally:
        if cur is not None: cur.close()
        if conn is not None: conn.close()

@app.route('/api/venda/<int:venda_id>', methods=['DELETE', 'PUT'])
@login_required
def api_manipular_venda(venda_id):
    conn = None; cur = None
    try:
        conn = get_db_connection(); cur = conn.cursor()
        if request.method == 'DELETE':
            should_restock = request.args.get('restock', 'true').lower() == 'true'
            if should_restock:
                cur.execute("SELECT produto_nome, quantidade FROM registro_venda WHERE id = %s", (venda_id,)); venda = cur.fetchone()
                if not venda: return jsonify({'success': False, 'message': 'Venda não encontrada'}), 404
                produto_nome, quantidade_vendida = venda
                cur.execute("UPDATE registro_produto SET quantidade = quantidade + %s WHERE nome_produto = %s", (quantidade_vendida, produto_nome))
            cur.execute("DELETE FROM registro_venda WHERE id = %s", (venda_id,)); conn.commit()
            message = 'Venda deletada e estoque atualizado!' if should_restock else 'Venda deletada sem devolução ao estoque.'
            return jsonify({'success': True, 'message': message})
        elif request.method == 'PUT':
            data = request.get_json(); novo_barbeiro = data.get('barbeiro'); nova_data_venda = datetime.fromisoformat(data.get('data_venda')) if data.get('data_venda') else None
            cur.execute("UPDATE registro_venda SET barbeiro = %s, data_venda = %s WHERE id = %s", (novo_barbeiro, nova_data_venda, venda_id)); conn.commit()
            if cur.rowcount == 0: return jsonify({'success': False, 'message': 'Venda não encontrada'}), 404
            return jsonify({'success': True, 'message': 'Venda atualizada com sucesso!'})
    except (Exception, psycopg2.Error) as error:
        if conn: conn.rollback(); print(f"Erro ao manipular venda: {error}"); return jsonify({'success': False, 'message': 'Ocorreu um erro no servidor.'}), 500
    finally:
        if cur is not None: cur.close()
        if conn is not None: conn.close()

@app.route('/api/produto/<int:produto_id>', methods=['DELETE', 'PUT'])
@login_required
def api_manipular_produto(produto_id):
    conn = None; cur = None
    try:
        conn = get_db_connection(); cur = conn.cursor()
        if request.method == 'DELETE':
            cur.execute("SELECT nome_produto FROM registro_produto WHERE id = %s", (produto_id,)); produto = cur.fetchone()
            if not produto: return jsonify({'success': False, 'message': 'Produto não encontrado'}), 404
            cur.execute("SELECT COUNT(*) FROM registro_venda WHERE produto_nome = %s", (produto[0],))
            if cur.fetchone()[0] > 0: return jsonify({'success': False, 'message': 'Não é possível excluir. Este produto já possui vendas registradas.'}), 400
            cur.execute("DELETE FROM registro_produto WHERE id = %s", (produto_id,)); conn.commit()
            return jsonify({'success': True, 'message': 'Produto deletado com sucesso!'})
        elif request.method == 'PUT':
            data = request.get_json(); novo_nome = data.get('nome_produto'); nova_quantidade = int(data.get('quantidade')); novo_valor = float(data.get('valor_unitario'))
            cur.execute("SELECT nome_produto FROM registro_produto WHERE id = %s", (produto_id,)); resultado = cur.fetchone()
            if not resultado: return jsonify({'success': False, 'message': 'Produto não encontrado'}), 404
            nome_antigo = resultado[0]
            cur.execute("UPDATE registro_produto SET nome_produto = %s, quantidade = %s, valor_unitario = %s WHERE id = %s", (novo_nome, nova_quantidade, novo_valor, produto_id))
            if nome_antigo != novo_nome: cur.execute("UPDATE registro_venda SET produto_nome = %s WHERE produto_nome = %s", (novo_nome, nome_antigo))
            conn.commit()
            return jsonify({'success': True, 'message': 'Produto atualizado com sucesso!'})
    except (Exception, psycopg2.Error) as error:
        if conn: conn.rollback(); print(f"Erro ao manipular produto: {error}"); return jsonify({'success': False, 'message': 'Ocorreu um erro no servidor.'}), 500
    finally:
        if cur is not None: cur.close()
        if conn is not None: conn.close()

@app.route('/api/usuario/<int:user_id>', methods=['DELETE', 'PUT'])
@login_required
@admin_required
def api_manipular_usuario(user_id):
    conn = get_db_connection(); cur = conn.cursor()
    try:
        if request.method == 'DELETE':
            if user_id == session.get('user_id'):
                return jsonify({'success': False, 'message': 'Você não pode excluir sua própria conta.'}), 403
            cur.execute("DELETE FROM registro_usuarios WHERE id = %s", (user_id,)); conn.commit()
            return jsonify({'success': True, 'message': 'Usuário deletado com sucesso!'})
        elif request.method == 'PUT':
            data = request.get_json(); nova_senha = data.get('senha')
            if nova_senha:
                senha_hash = generate_password_hash(nova_senha)
                cur.execute("UPDATE registro_usuarios SET usuario = %s, email = %s, telefone = %s, cpf = %s, is_admin = %s, senha_hash = %s WHERE id = %s",
                            (data.get('usuario'), data.get('email'), data.get('telefone'), data.get('cpf'), data.get('is_admin'), senha_hash, user_id))
            else:
                cur.execute("UPDATE registro_usuarios SET usuario = %s, email = %s, telefone = %s, cpf = %s, is_admin = %s WHERE id = %s",
                            (data.get('usuario'), data.get('email'), data.get('telefone'), data.get('cpf'), data.get('is_admin'), user_id))
            conn.commit()
            return jsonify({'success': True, 'message': 'Usuário atualizado com sucesso!'})
    except (Exception, psycopg2.Error) as error:
        if conn: conn.rollback(); print(f"Erro ao manipular usuário: {error}"); return jsonify({'success': False, 'message': 'Ocorreu um erro no servidor.'}), 500
    finally:
        cur.close(); conn.close()

# API para o dashboard
@app.route('/api/barbeiros')
@login_required
def api_barbeiros():
    """Retorna uma lista de nomes de barbeiros únicos."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT DISTINCT barbeiro FROM registro_servico WHERE barbeiro IS NOT NULL
        UNION
        SELECT DISTINCT barbeiro FROM registro_venda WHERE barbeiro IS NOT NULL
        ORDER BY barbeiro;
    """)
    barbeiros = [row[0] for row in cur.fetchall()]
    cur.close()
    conn.close()
    return jsonify(barbeiros)

@app.route('/api/dashboard_data')
@login_required
def dashboard_data():
    """Coleta e retorna todos os dados agregados para o dashboard, aplicando filtros."""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=DictCursor)
    
    barbeiro = request.args.get('barbeiro')
    period = request.args.get('period', 'all')

    start_date = None
    now = datetime.now()
    if period == 'hour':
        start_date = now - timedelta(hours=1)
    elif period == 'day':
        start_date = now - timedelta(days=1)
    elif period == 'week':
        start_date = now - timedelta(weeks=1)
    elif period == 'month':
        start_date = now - timedelta(days=30)
    elif period == 'year':
        start_date = now - timedelta(days=365)

    params = {}
    where_clauses = {"servico": [], "venda": []}

    if barbeiro:
        where_clauses["servico"].append("barbeiro = %(barbeiro)s")
        where_clauses["venda"].append("barbeiro = %(barbeiro)s")
        params['barbeiro'] = barbeiro
    
    if start_date:
        where_clauses["servico"].append("data_servico >= %(start_date)s")
        where_clauses["venda"].append("data_venda >= %(start_date)s")
        params['start_date'] = start_date

    where_servico_str = f"WHERE {' AND '.join(where_clauses['servico'])}" if where_clauses['servico'] else ""
    where_venda_str = f"WHERE {' AND '.join(where_clauses['venda'])}" if where_clauses['venda'] else ""

    try:
        cur.execute(f"SELECT COALESCE(SUM(valor), 0) FROM registro_servico {where_servico_str}", params)
        total_servicos = cur.fetchone()[0] or 0
        cur.execute(f"SELECT COALESCE(SUM(valor_total), 0) FROM registro_venda {where_venda_str}", params)
        total_vendas = cur.fetchone()[0] or 0
        cur.execute(f"SELECT barbeiro, COUNT(id) as count FROM registro_servico {where_servico_str} GROUP BY barbeiro ORDER BY count DESC", params)
        servicos_por_barbeiro = cur.fetchall()
        cur.execute(f"SELECT barbeiro, COUNT(id) as count FROM registro_venda {where_venda_str} GROUP BY barbeiro ORDER BY count DESC", params)
        vendas_por_barbeiro = cur.fetchall()
        cur.execute("SELECT nome_produto, quantidade FROM registro_produto ORDER BY quantidade DESC")
        produtos_em_estoque = cur.fetchall()
        
        dashboard_json = {
            "total_servicos_faturado": float(total_servicos),
            "total_vendas_faturado": float(total_vendas),
            "faturamento_total": float(total_servicos + total_vendas),
            "servicos_por_barbeiro": {"labels": [r['barbeiro'] for r in servicos_por_barbeiro], "data": [r['count'] for r in servicos_por_barbeiro]},
            "vendas_por_barbeiro": {"labels": [r['barbeiro'] for r in vendas_por_barbeiro], "data": [r['count'] for r in vendas_por_barbeiro]},
            "produtos_em_estoque": {"labels": [r['nome_produto'] for r in produtos_em_estoque], "data": [r['quantidade'] for r in produtos_em_estoque]}
        }
        return jsonify(dashboard_json)
    except (Exception, psycopg2.Error) as error:
        print(f"Erro ao buscar dados do dashboard: {error}")
        return jsonify({"error": "Erro interno do servidor"}), 500
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    app.run(debug=True)