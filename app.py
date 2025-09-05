import os
import psycopg2
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
from datetime import datetime, date, timedelta
import re
from decimal import Decimal
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from psycopg2.extras import DictCursor
from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename
from flask import Response
import mimetypes
import base64
from flask import jsonify, request, session
from psycopg2.extras import DictCursor
from datetime import datetime, timedelta

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

@app.route('/lista_conta')
def lista_conta():
    return render_template('lista_conta.html')

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
    print("USUARIO LOGADO NA SESSÃO:", session.get('usuario'))
    print("SESSION:", dict(session))  # Mostra todas as variáveis da sessão
    usuario_logado = session.get('usuario')
    print("USUARIO LOGADO:", usuario_logado)
    usuario_logado = session.get('usuario')
    if not usuario_logado:
        return "Nenhum usuário logado", 403

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=DictCursor)

    cur.execute(
        "SELECT usuario, is_admin FROM registro_usuarios WHERE usuario = %s",
        (usuario_logado,)
    )
    user_info = cur.fetchone()
    if not user_info:
        cur.close()
        conn.close()
        return "Usuário não encontrado", 404

    is_admin = user_info['is_admin']
    barbeiros = []

    if is_admin:
        cur.execute("""
            SELECT DISTINCT barbeiro 
            FROM registro_servico 
            WHERE barbeiro IS NOT NULL
            UNION
            SELECT DISTINCT barbeiro 
            FROM registro_venda 
            WHERE barbeiro IS NOT NULL
            ORDER BY barbeiro
        """)
        barbeiros = [r['barbeiro'] for r in cur.fetchall()]

    cur.close()
    conn.close()

    return render_template(
        'menu.html',
        user_nome=user_info['usuario'],
        is_admin=is_admin,
        barbeiros=barbeiros
    )
#########################################################
# Listar todas as contas
from psycopg2.extras import DictCursor
from flask import jsonify, request
from datetime import datetime
import base64  # para tratar campo bytea (arquivo)

# ------------------- ROTAS -------------------

# Listar todas as contas
@app.route("/api/contas", methods=["GET"])
def listar_contas():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=DictCursor)
    cur.execute("""
        SELECT id, data_registro, nome_conta, valor, arquivo, amortizar, meses_amortizar, valor_amortizado
        FROM registro_conta
        ORDER BY id DESC
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()

    contas = []
    for row in rows:
        contas.append({
            "id": row["id"],
            "data_registro": row["data_registro"].isoformat() if row["data_registro"] else None,
            "nome_conta": row["nome_conta"],
            "valor": float(row["valor"]) if row["valor"] is not None else None,
            "arquivo": base64.b64encode(row["arquivo"]).decode("utf-8") if row["arquivo"] else None,
            "amortizar": row["amortizar"],
            "meses_amortizar": row["meses_amortizar"],
            "valor_amortizado": float(row["valor_amortizado"]) if row["valor_amortizado"] is not None else None
        })
    return jsonify(contas)


# Deletar uma conta
@app.route("/api/conta/<int:conta_id>", methods=["PUT"])
@login_required
def atualizar_conta(conta_id):
    dados = request.get_json()
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Lógica para tratar os campos de amortização
        amortizar = dados.get('amortizar', False)
        meses_amortizar = int(dados.get('meses_amortizar')) if amortizar and dados.get('meses_amortizar') else None
        
        # Recalcula o valor amortizado se necessário
        valor_amortizado = 0
        if amortizar and meses_amortizar and float(dados.get('valor', 0)) > 0:
            valor_amortizado = float(dados.get('valor')) / meses_amortizar

        query = """
            UPDATE registro_conta 
            SET nome_conta = %s,
                valor = %s,
                data_registro = %s,
                amortizar = %s,
                meses_amortizar = %s,
                valor_amortizado = %s
            WHERE id = %s
        """
        cur.execute(query, (
            dados.get('nome_conta'),
            float(dados.get('valor', 0)),
            dados.get('data_registro'),
            amortizar,
            meses_amortizar,
            valor_amortizado,
            conta_id
        ))
        conn.commit()
        
        if cur.rowcount == 0:
            return jsonify({"message": "Conta não encontrada"}), 404
            
        return jsonify({"message": "Conta atualizada com sucesso"})

    except Exception as e:
        conn.rollback()
        print(f"Erro ao atualizar conta: {e}")
        return jsonify({"message": f"Erro no servidor: {e}"}), 500
    finally:
        cur.close()
        conn.close()

# Criar conta
@app.route("/api/conta", methods=["POST"])
def criar_conta():
    dados = request.get_json()

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO registro_conta (data_registro, nome_conta, valor, amortizar, meses_amortizar, valor_amortizado)
        VALUES (%s, %s, %s, %s, %s, %s) RETURNING id
    """, (
        datetime.strptime(dados["data_registro"], "%Y-%m-%d").date() if dados.get("data_registro") else None,
        dados.get("nome_conta"),
        float(dados.get("valor")) if dados.get("valor") else None,
        dados.get("amortizar"),
        dados.get("meses_amortizar"),
        float(dados.get("valor_amortizado")) if dados.get("valor_amortizado") else None
    ))

    novo_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()

    return jsonify({"message": "Conta criada com sucesso", "id": novo_id}), 201

#########################################################
@app.route('/registro/servico', methods=['GET', 'POST'])
@login_required
def registro_servico():
    if request.method == 'POST':
        conn = None
        cur = None
        try:
            data = request.get_json()

            valor_str = data.get('valor', 'R$ 0,00')
            valor_limpo = re.sub(r'[^\d,]', '', valor_str).replace(',', '.')
            valor_numeric = float(valor_limpo) if valor_limpo else 0.0

            data_servico_dt = (
                datetime.fromisoformat(data.get('dataHora'))
                if data.get('dataHora') else None
            )

            data_final_str = data.get('dataFinal')
            data_final_dt = (
                datetime.strptime(data_final_str, '%d/%m/%Y').date()
                if data_final_str else None
            )

            conn = get_db_connection()
            cur = conn.cursor()

            sql = """
                INSERT INTO registro_servico 
                (barbeiro, servico, cliente, valor, data_servico, data_final) 
                VALUES (%s, %s, %s, %s, %s, %s)
            """

            record = (
                data.get('barbeiro'),
                data.get('servico'),
                data.get('cliente'),
                valor_numeric,
                data_servico_dt,
                data_final_dt
            )

            cur.execute(sql, record)
            conn.commit()

            return jsonify({
                'success': True,
                'message': 'Serviço registrado com sucesso!'
            }), 201

        except (Exception, psycopg2.Error) as error:
            print(f"Erro ao inserir serviço: {error}")
            return jsonify({
                'success': False,
                'message': 'Ocorreu um erro no servidor.'
            }), 500

        finally:
            if cur is not None:
                cur.close()
            if conn is not None:
                conn.close()

    return render_template('registro_servico.html')

@app.route('/registro/produto', methods=['GET', 'POST'])
@login_required
def registro_produto():
    if request.method == 'POST':
        conn = None
        cur = None
        try:
            data = request.get_json()
            conn = get_db_connection()
            cur = conn.cursor()

            nome_produto = data.get('nome_do_produto')
            quantidade = int(data.get('quantidade', 0))
            valor_unitario = float(data.get('valor_Uni', 0))
            
            # --- AJUSTES AQUI ---
            # Definimos valor_compra como 0, pois ele não vem mais do formulário
            valor_compra = 0.0
            # O lucro agora é igual ao valor de venda, pois não há custo de compra
            lucro = valor_unitario

            sql = """
                INSERT INTO registro_produto 
                (nome_produto, quantidade, valor_unitario, valor_compra, lucro) 
                VALUES (%s, %s, %s, %s, %s)
            """
            record = (nome_produto, quantidade, valor_unitario, valor_compra, lucro)
            cur.execute(sql, record)
            conn.commit()

            return jsonify({'success': True, 'message': 'Produto registrado com sucesso!'}), 201
        except (Exception, psycopg2.Error) as error:
            print(f"Erro ao inserir produto: {error}")
            return jsonify({'success': False, 'message': 'Ocorreu um erro no servidor.'}), 500
        finally:
            if cur is not None:
                cur.close()
            if conn is not None:
                conn.close()
    
    # A parte do GET continua a mesma, apenas renderiza a página
    return render_template('registro_produto.html')

@app.route('/registro/venda', methods=['GET', 'POST'])
@login_required
def registro_venda():
    if request.method == 'POST':
        conn = None
        cur = None
        try:
            data = request.get_json()
            produto_vendido = data.get('produto')
            quantidade_vendida = int(data.get('quantidade'))
            lucro_venda = float(data.get('lucro_venda', 0))  # Pega lucro do JSON

            conn = get_db_connection()
            cur = conn.cursor()

            cur.execute("SELECT quantidade, lucro FROM registro_produto WHERE nome_produto = %s FOR UPDATE", (produto_vendido,))
            estoque_atual = cur.fetchone()
            if estoque_atual is None or estoque_atual[0] < quantidade_vendida:
                return jsonify({'success': False, 'message': 'Estoque insuficiente!'}), 400

            cur.execute("UPDATE registro_produto SET quantidade = quantidade - %s WHERE nome_produto = %s",
                        (quantidade_vendida, produto_vendido))

            valor_str = data.get('valor', 'R$ 0,00')
            valor_limpo = re.sub(r'[^\d,]', '', valor_str).replace(',', '.')
            valor_total_numeric = float(valor_limpo) if valor_limpo else 0.0

            sql = """
                INSERT INTO registro_venda (barbeiro, produto_nome, quantidade, valor_total, lucro_venda, data_venda) 
                VALUES (%s, %s, %s, %s, %s, %s)
            """
            record = (
                data.get('barbeiro'),
                produto_vendido,
                quantidade_vendida,
                valor_total_numeric,
                lucro_venda,
                datetime.fromisoformat(data.get('dataHoraVenda'))
            )
            cur.execute(sql, record)
            conn.commit()
            return jsonify({'success': True, 'message': 'Venda registrada com sucesso!'}), 201

        except (Exception, psycopg2.Error) as error:
            if conn:
                conn.rollback()
            print(f"Erro ao registrar venda: {error}")
            return jsonify({'success': False, 'message': 'Ocorreu um erro no servidor.'}), 500

        finally:
            if cur is not None:
                cur.close()
            if conn is not None:
                conn.close()

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
        cur.execute("SELECT id, nome_produto, quantidade, valor_unitario, valor_compra, lucro FROM registro_produto ORDER BY nome_produto ASC")
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
        cur.execute("SELECT id, barbeiro, produto_nome, lucro_venda, quantidade, valor_total, data_venda FROM registro_venda ORDER BY data_venda DESC")
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


@app.route('/registro/conta', methods=['GET', 'POST'])
def registro_conta():
    if request.method == 'POST':
        try:
            # Campos básicos
            data = request.form.get('dataConta')
            nome_conta = request.form.get('nomeConta')
            valor = float(request.form.get('valorConta', 0))
            
            # Arquivo opcional
            arquivo = None
            if 'arquivoConta' in request.files:
                file = request.files['arquivoConta']
                if file.filename != '':
                    arquivo = file.read()  # ou salvar com file.save()

            # Campos de amortização
            amortizar = request.form.get('amortizar', 'false') == 'true'
            meses_amortizar = int(request.form.get('mesesAmortizar', 0)) if amortizar else None
            valor_amortizado = float(request.form.get('valorAmortizado', 0).replace(',', '.')) if amortizar else None

            # Inserir no banco
            conn = get_db_connection()
            cur = conn.cursor(cursor_factory=DictCursor)
            cur.execute("""
                INSERT INTO registro_conta (
                    data_registro, nome_conta, valor, arquivo, amortizar, meses_amortizar, valor_amortizado
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (data, nome_conta, valor, arquivo, amortizar, meses_amortizar, valor_amortizado))
            
            conn.commit()
            cur.close()
            conn.close()

            return jsonify({"message": "Conta registrada com sucesso!"})

        except Exception as e:
            return jsonify({"message": f"Erro ao registrar conta: {str(e)}"}), 500

    # GET request
    return render_template('registro_conta.html')

@app.route('/api/produto/<int:produto_id>', methods=['PUT', 'DELETE'])
@login_required
def api_manipular_produto(produto_id):
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        if request.method == 'DELETE':
            cur.execute("SELECT nome_produto FROM registro_produto WHERE id = %s", (produto_id,))
            produto = cur.fetchone()
            if not produto:
                return jsonify({'success': False, 'message': 'Produto não encontrado'}), 404

            cur.execute("SELECT COUNT(*) FROM registro_venda WHERE produto_nome = %s", (produto[0],))
            if cur.fetchone()[0] > 0:
                return jsonify({'success': False, 'message': 'Não é possível excluir. Este produto já possui vendas registradas.'}), 400

            cur.execute("DELETE FROM registro_produto WHERE id = %s", (produto_id,))
            conn.commit()
            return jsonify({'success': True, 'message': 'Produto deletado com sucesso!'})

        elif request.method == 'PUT':
            data = request.get_json()
            novo_nome = data.get('nome_produto')
            nova_quantidade = int(data.get('quantidade'))
            novo_valor_unitario = float(data.get('valor_unitario'))
            novo_valor_compra = float(data.get('valor_compra'))
            
            # --- LÓGICA CORRIGIDA AQUI ---
            # Recalcula o lucro antes de salvar
            novo_lucro = novo_valor_unitario - novo_valor_compra

            cur.execute("SELECT nome_produto FROM registro_produto WHERE id = %s", (produto_id,))
            resultado = cur.fetchone()
            if not resultado:
                return jsonify({'success': False, 'message': 'Produto não encontrado'}), 404

            nome_antigo = resultado[0]

            # Atualiza o banco de dados incluindo o novo lucro
            cur.execute("""
                UPDATE registro_produto
                SET nome_produto = %s, 
                    quantidade = %s, 
                    valor_unitario = %s, 
                    valor_compra = %s, 
                    lucro = %s 
                WHERE id = %s
            """, (novo_nome, nova_quantidade, novo_valor_unitario, novo_valor_compra, novo_lucro, produto_id))

            if nome_antigo != novo_nome:
                cur.execute("UPDATE registro_venda SET produto_nome = %s WHERE produto_nome = %s", (novo_nome, nome_antigo))

            conn.commit()
            return jsonify({'success': True, 'message': 'Produto atualizado com sucesso!'})

    except (Exception, psycopg2.Error) as error:
        if conn:
            conn.rollback()
        print(f"Erro ao manipular produto: {error}")
        return jsonify({'success': False, 'message': 'Ocorreu um erro no servidor.'}), 500

    finally:
        if cur is not None:
            cur.close()
        if conn is not None:
            conn.close()

@app.route('/clientes_assinatura', methods=['GET'])
@login_required
def listar_clientes_assinatura():
    barbeiro = request.args.get("barbeiro")  # pega o barbeiro da query string
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        if barbeiro:
            cur.execute("""
                SELECT id, cliente, data_final
                FROM registro_servico
                WHERE servico IN ('Assinatura mensal Corte', 'Assinatura mensal Corte e Barba')
                  AND barbeiro = %s
                ORDER BY cliente
            """, (barbeiro,))
        else:
            cur.execute("""
                SELECT id, cliente, data_final
                FROM registro_servico
                WHERE servico IN ('Assinatura mensal Corte', 'Assinatura mensal Corte e Barba')
                ORDER BY cliente
            """)

        clientes = cur.fetchall()
        return jsonify([
            {
                "id": c[0],
                "nome": c[1],
                "data_final": c[2].strftime("%Y-%m-%d") if c[2] else None
            }
            for c in clientes
        ])

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if cur: cur.close()
        if conn: conn.close()
#aqui acaba o teste 13/08
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
@app.route("/incrementar_corte", methods=["POST"])
def incrementar_corte():
    conn = None
    cur = None
    try:
        data = request.get_json()
        id_cliente = data.get("id")  # ID que veio do frontend

        # Garantir que veio um valor válido
        if not id_cliente:
            return jsonify({"success": False, "message": "ID não fornecido"}), 400

        conn = get_db_connection()
        cur = conn.cursor()

        # UPDATE somando +1
        cur.execute("""
            UPDATE registro_servico
            SET quantidade_corte = quantidade_corte + 1
            WHERE id = %s
        """, (id_cliente,))

        conn.commit()

        return jsonify({"success": True, "message": "Quantidade de cortes incrementada com sucesso"})
    except Exception as e:
        print(f"Erro ao incrementar corte: {e}")
        return jsonify({"success": False, "message": "Erro no servidor"}), 500
    finally:
        if cur: cur.close()
        if conn: conn.close()

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
from decimal import Decimal

@app.route('/api/dashboard_data')
@login_required
def dashboard_data():
    """Coleta e retorna todos os dados agregados para o dashboard, aplicando filtros com controle de acesso."""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=DictCursor)

    try:
        # --- Usuário logado ---
        usuario_logado = session.get('usuario')
        if not usuario_logado:
            return jsonify({"error": "Usuário não autenticado"}), 401

        cur.execute("SELECT usuario, is_admin FROM registro_usuarios WHERE usuario = %s", (usuario_logado,))
        user_info = cur.fetchone()
        if not user_info:
            return jsonify({"error": "Usuário não encontrado"}), 404

        is_admin = user_info['is_admin']
        user_nome = user_info['usuario']

        # --- Filtros do frontend ---
        barbeiro = request.args.get('barbeiro')
        inicio_str = request.args.get('inicio')
        fim_str = request.args.get('fim')

        start_date = datetime.strptime(inicio_str, '%Y-%m-%d') if inicio_str else None
        end_date = datetime.strptime(fim_str, '%Y-%m-%d') if fim_str else None
        if end_date:
            end_date += timedelta(days=1)

        # --- Controle de acesso ---
        if not is_admin:
            barbeiro = user_nome
        elif barbeiro == "":
            barbeiro = None

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
        if end_date:
            where_clauses["servico"].append("data_servico < %(end_date)s") # Alterado para '<' para incluir o dia todo
            where_clauses["venda"].append("data_venda < %(end_date)s")
            params['end_date'] = end_date

        where_servico_str = f"WHERE {' AND '.join(where_clauses['servico'])}" if where_clauses['servico'] else ""
        where_venda_str = f"WHERE {' AND '.join(where_clauses['venda'])}" if where_clauses['venda'] else ""

        # --- Cálculos dos KPIs (sem alteração) ---
        cur.execute("SELECT COUNT(*) FROM registro_servico WHERE servico IN ('Assinatura mensal Corte', 'Assinatura mensal Corte e Barba')")
        total_assinantes = cur.fetchone()[0] or 0
        
        cur.execute("SELECT COALESCE(SUM(valor_amortizado),0) FROM registro_conta")
        total_amortizado = float(cur.fetchone()[0] or 0)

        cur.execute("SELECT COALESCE(SUM(valor),0) FROM registro_conta")
        total_gastos = float(cur.fetchone()[0] or 0)
        
        cur.execute(f"SELECT COALESCE(SUM(valor),0) FROM registro_servico {where_servico_str}", params)
        total_servicos_faturado = float(cur.fetchone()[0] or 0)

        cur.execute(f"SELECT COALESCE(SUM(valor_total),0) FROM registro_venda {where_venda_str}", params)
        total_vendas_faturado = float(cur.fetchone()[0] or 0)

        faturamento_total = total_servicos_faturado + total_vendas_faturado
        liquido_servicos = total_servicos_faturado - total_gastos
        liquido_total = faturamento_total - total_gastos
        
        # --- Dados para Gráficos (EXISTENTES) ---
        cur.execute(f"SELECT barbeiro, COUNT(id) AS count FROM registro_servico {where_servico_str} GROUP BY barbeiro ORDER BY count DESC", params)
        servicos_por_barbeiro = cur.fetchall()

        cur.execute(f"SELECT barbeiro, COUNT(id) AS count FROM registro_venda {where_venda_str} GROUP BY barbeiro ORDER BY count DESC", params)
        vendas_por_barbeiro = cur.fetchall()

        cur.execute("SELECT nome_produto, quantidade FROM registro_produto ORDER BY quantidade DESC")
        produtos_em_estoque = cur.fetchall()

        # --- *NOVA CONSULTA* PARA O GRÁFICO "TOP 5 SERVIÇOS" ---
        cur.execute(f"""
            SELECT servico, COUNT(id) as total
            FROM registro_servico
            {where_servico_str}
            GROUP BY servico
            ORDER BY total DESC
            LIMIT 5
        """, params)
        top_servicos = cur.fetchall()

        # --- Montagem do JSON final ---
        dashboard_json = {
            "total_assinantes": total_assinantes,
            "total_amortizado": total_amortizado,
            "total_gastos": total_gastos,
            "total_servicos_faturado": total_servicos_faturado,
            "total_vendas_faturado": total_vendas_faturado,
            "faturamento_total": faturamento_total,
            "liquido_servicos": liquido_servicos,
            "liquido_total": liquido_total,
            "servicos_por_barbeiro": {"labels": [r['barbeiro'] for r in servicos_por_barbeiro], "data": [int(r['count']) for r in servicos_por_barbeiro]},
            "vendas_por_barbeiro": {"labels": [r['barbeiro'] for r in vendas_por_barbeiro], "data": [int(r['count']) for r in vendas_por_barbeiro]},
            "produtos_em_estoque": {"labels": [r['nome_produto'] for r in produtos_em_estoque], "data": [int(r['quantidade']) for r in produtos_em_estoque]},
            # --- *NOVO DADO* ADICIONADO AO JSON ---
            "top_servicos": {"labels": [r['servico'] for r in top_servicos], "data": [int(r['total']) for r in top_servicos]}
        }
        return jsonify(dashboard_json)

    except (Exception, psycopg2.Error) as error:
        print(f"Erro ao buscar dados do dashboard: {error}")
        return jsonify({"error": "Erro interno do servidor"}), 500

    finally:
        cur.close()
        conn.close()

#----teste 14/08-
@app.route('/funcionario')
@login_required  # opcional, se quiser proteger o acesso
def funcionario():
    return render_template('funcionario.html')

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)  # cria a pasta se não existir

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/api/pagar', methods=['POST'])
def pagar():
    barbeiro = request.form.get('barbeiro')
    inicio = request.form.get('inicio')
    fim = request.form.get('fim')
    valor = request.form.get('valor')
    arquivo = request.files.get('arquivo')

    if not all([barbeiro, inicio, fim, valor, arquivo]):
        return jsonify({'success': False, 'message': 'Todos os campos são obrigatórios!'})

    if arquivo and allowed_file(arquivo.filename):
        try:
            arquivo_bytes = arquivo.read()  # lê os bytes do arquivo

            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO pagamentos (barbeiro, inicio, fim, valor, arquivo)
                VALUES (%s, %s, %s, %s, %s)
            """, (barbeiro, inicio, fim, valor, arquivo_bytes))
            conn.commit()
            cur.close()
            conn.close()

            return jsonify({'success': True, 'message': 'Pagamento registrado com sucesso!'})
        except Exception as e:
            if conn:
                conn.rollback()
                conn.close()
            return jsonify({'success': False, 'message': f'Erro ao salvar no banco: {e}'})
    else:
        return jsonify({'success': False, 'message': 'Arquivo inválido!'})

@app.route('/api/pagamentos/<barbeiro>', methods=['GET'])
def ultimo_pagamento(barbeiro):
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT inicio, fim, valor
            FROM pagamentos
            WHERE barbeiro = %s
            ORDER BY fim DESC
            LIMIT 1
        """, (barbeiro,))
        resultado = cur.fetchone()
        cur.close()
        conn.close()

        if resultado:
            return jsonify({
                'success': True,
                'inicio': resultado[0].strftime("%Y-%m-%d") if resultado[0] else None,
                'fim': resultado[1].strftime("%Y-%m-%d") if resultado[1] else None,
                'valor': float(resultado[2]) if resultado[2] else 0
            })
        else:
            return jsonify({'success': False, 'message': 'Nenhum pagamento encontrado para esse barbeiro.'})

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
    
@app.route('/api/historico_pagamentos/<barbeiro>')
@login_required
def historico_pagamentos(barbeiro):
    """Retorna o histórico de pagamentos de um barbeiro."""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=DictCursor)
    try:
        usuario_logado = session.get('usuario')
        cur.execute("SELECT usuario, is_admin FROM registro_usuarios WHERE usuario = %s", (usuario_logado,))
        user_info = cur.fetchone()
        if not user_info:
            return jsonify({"error": "Usuário não encontrado"}), 404

        is_admin = user_info['is_admin']
        if not is_admin:
            barbeiro = usuario_logado  # Usuário comum só vê o próprio histórico

        # Consulta com ID
        cur.execute("""
            SELECT id, barbeiro, valor, inicio, fim
            FROM pagamentos
            WHERE barbeiro = %s
            ORDER BY inicio DESC
        """, (barbeiro,))
        pagamentos = cur.fetchall()

        resultado = []
        for p in pagamentos:
            resultado.append({
                "id": p['id'],  # ID único
                "barbeiro": p['barbeiro'],
                "valor": float(p['valor']),
                "inicio": p['inicio'].strftime("%Y-%m-%d"),
                "fim": p['fim'].strftime("%Y-%m-%d"),
                "arquivo_url": f"/download_pagamento/{p['id']}"  # Rota para download
            })

        return jsonify({"pagamentos": resultado})

    except Exception as e:
        print(f"Erro ao buscar histórico de pagamentos: {e}")
        return jsonify({"error": "Erro interno do servidor"}), 500
    finally:
        cur.close()
        conn.close()
@app.route('/download_pagamento/<int:id>')
@login_required
def download_pagamento(id):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT arquivo FROM pagamentos WHERE id = %s", (id,))
        row = cur.fetchone()
        if not row or row[0] is None:
            return "Arquivo não encontrado", 404

        arquivo_bytes = row[0]

        # Definir extensão padrão (pode ser .jpg, .png, .pdf conforme o caso)
        extensao = ".bin"  # fallback
        mime_type = "application/octet-stream"

        # Exemplo: se você souber que são jpg
        extensao = ".jpg"
        mime_type = "image/jpeg"

        nome_arquivo = f"pagamento_{id}{extensao}"

        return Response(
            arquivo_bytes,
            mimetype=mime_type,
            headers={"Content-Disposition": f"attachment; filename={nome_arquivo}"}
        )
    finally:
        cur.close()
        conn.close()
#----fim teste 14/08-
if __name__ == '__main__':
    app.run(debug=True)
