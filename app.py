import streamlit as st
import pandas as pd
import sqlite3
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timedelta
from groq import Groq

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="SISTEMA JNL", page_icon="🏢", layout="wide")
SENHA_MESTRA = "JNLDIRETORIA" # Senha exclusiva para abrir o Setor Admin

# --- LISTA MESTRA INICIAL (Semente do Banco de Dados) ---
USUARIOS_SEED = {
    "arthur": {"senha": "32167308", "nome": "ARTHUR", "setores": "ALL"},
    "felipe": {"senha": "JNL2026", "nome": "FELIPE", "setores": "ALL"},
    "pedro": {"senha": "JNL2026", "nome": "PEDRO", "setores": "ALL"},
    "jessica": {"senha": "JNL2026", "nome": "JÉSSICA", "setores": "ADMINISTRATIVO,FINANCEIRO"},
    "emanoel": {"senha": "JNL2026", "nome": "EMANOEL", "setores": "ESTOQUE"},
    "gabriel": {"senha": "JNL2026", "nome": "GABRIEL", "setores": "ESTOQUE"},
    "lays": {"senha": "JNL2026", "nome": "LAYS", "setores": "ADMINISTRATIVO,FATURAMENTO"},
    "guilherme": {"senha": "JNL2026", "nome": "GUILHERME", "setores": "COMPRAS"},
    "milene": {"senha": "JNL2026", "nome": "MILENE", "setores": "SOLUÇÕES CORPORATIVAS"},
    "thauane": {"senha": "JNL2026", "nome": "THAUANE", "setores": "SOLUÇÕES CORPORATIVAS"},
    "kamilly": {"senha": "JNL2026", "nome": "KAMILLY", "setores": "SOLUÇÕES CORPORATIVAS"},
    "kaique": {"senha": "JNL2026", "nome": "KAIQUE", "setores": "SOLUÇÕES CORPORATIVAS"},
    "karina": {"senha": "JNL2026", "nome": "KARINA", "setores": "VENDAS"},
    "gustavo": {"senha": "JNL2026", "nome": "GUSTAVO", "setores": "VENDAS"},
    "manoel": {"senha": "JNL2026", "nome": "MANOEL", "setores": "VENDAS"},
    "carol": {"senha": "JNL2026", "nome": "CAROL", "setores": "RH"}
}

# --- BANCO DE DADOS ---
def init_db():
    conn = sqlite3.connect('jnl_master.db')
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS usuarios (login TEXT PRIMARY KEY, senha TEXT, nome TEXT, setores TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS arquivos_setoriais (setor TEXT, nome TEXT, caminho TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS calendario (id INTEGER PRIMARY KEY AUTOINCREMENT, usuario TEXT, titulo TEXT, data_hora TEXT, notificado INTEGER, destinatarios TEXT, copias TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS anotacoes (id INTEGER PRIMARY KEY AUTOINCREMENT, usuario TEXT, titulo TEXT, conteudo TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS chat_setor (id INTEGER PRIMARY KEY AUTOINCREMENT, setor TEXT, usuario TEXT, data_hora TEXT, mensagem TEXT, editada INTEGER DEFAULT 0, apagada INTEGER DEFAULT 0, timestamp_real TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS perfil_usuario (usuario TEXT PRIMARY KEY, nome_tratamento TEXT, instrucoes_ia TEXT)')
    
    # Popular usuários se estiver vazio
    c.execute('SELECT COUNT(*) FROM usuarios')
    if c.fetchone()[0] == 0:
        for k, v in USUARIOS_SEED.items():
            c.execute("INSERT INTO usuarios VALUES (?, ?, ?, ?)", (k, v["senha"], v["nome"], v["setores"]))
    
    # Atualização de tabelas (segurança)
    try: c.execute("ALTER TABLE chat_setor ADD COLUMN apagada INTEGER DEFAULT 0")
    except: pass
    try: c.execute("ALTER TABLE chat_setor ADD COLUMN timestamp_real TEXT")
    except: pass
    try: c.execute("ALTER TABLE calendario ADD COLUMN copias TEXT")
    except: pass
    
    conn.commit()
    conn.close()

init_db()

# --- TEMPO BRASÍLIA ---
def get_now_br():
    return datetime.utcnow() - timedelta(hours=3)

def obter_saudacao():
    hora = get_now_br().hour
    if 5 <= hora < 12: return "Bom dia"
    elif 12 <= hora < 18: return "Boa tarde"
    else: return "Boa noite"

# --- IA BUSCA WEB SILENCIOSA ---
def busca_web(prompt):
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            resultados = [r['body'] for r in ddgs.text(prompt, max_results=2)]
            return " ".join(resultados) if resultados else ""
    except:
        return ""

# --- ESTADO DO SISTEMA ---
if "autenticado" not in st.session_state: st.session_state["autenticado"] = False
if "setor" not in st.session_state: st.session_state["setor"] = None
if "mensagens_ia" not in st.session_state: st.session_state["mensagens_ia"] = []
if "admin_liberado" not in st.session_state: st.session_state["admin_liberado"] = False

# --- 1. TELA DE LOGIN ---
if not st.session_state["autenticado"]:
    st.title("🔒 CENTRO DE COMANDO JNL")
    u = st.text_input("Usuário:", placeholder="Ex: arthur").lower()
    p = st.text_input("Senha:", type="password", placeholder="Digite sua senha")
    if st.button("ACESSAR"):
        conn = sqlite3.connect('jnl_master.db')
        c = conn.cursor()
        c.execute("SELECT senha, nome, setores FROM usuarios WHERE login = ?", (u,))
        user_data = c.fetchone()
        conn.close()
        
        if user_data and user_data[0] == p:
            st.session_state.update({"autenticado": True, "user_slug": u, "user_nome": user_data[1], "user_setores": user_data[2]})
            st.rerun()
        else: st.error("Acesso Negado. Verifique usuário e senha.")

# --- 2. SELEÇÃO DE SETORES ---
elif st.session_state["setor"] is None:
    st.title(f"🏢 {obter_saudacao()}! Bem-vindo(a), {st.session_state['user_nome']}.")
    
    setores_base = ["ADMINISTRATIVO", "FINANCEIRO", "FATURAMENTO", "VENDAS", "COMPRAS", "ESTOQUE", "SOLUÇÕES CORPORATIVAS", "PROJETOS/IMPORTAÇÃO", "RH", "GERAL"]
    permissoes = st.session_state["user_setores"]
    setores_visiveis = setores_base if permissoes == "ALL" else permissoes.split(",")
    
    # Adiciona o Setor Secreto apenas para a Diretoria (ALL)
    if permissoes == "ALL":
        setores_visiveis.append("🔐 PAINEL ADMIN")

    cols = st.columns(3)
    for i, s in enumerate(setores_visiveis):
        with cols[i % 3]:
            # Destacar visualmente o painel admin se for o botão
            if s == "🔐 PAINEL ADMIN":
                if st.button(s, use_container_width=True, type="primary"):
                    st.session_state["setor"] = s
                    st.rerun()
            else:
                if st.button(s, use_container_width=True):
                    st.session_state["setor"] = s
                    st.rerun()

# --- 3. DASHBOARD PRINCIPAL ---
else:
    setor_atual = st.session_state["setor"]
    user = st.session_state["user_slug"]
    user_nome = st.session_state["user_nome"]
    is_admin = st.session_state["user_setores"] == "ALL"

    # ====================================================
    # FLUXO 1: O COFRE DA DIRETORIA (SETOR ADMIN ISOLADO)
    # ====================================================
    if setor_atual == "🔐 PAINEL ADMIN":
        if not st.session_state["admin_liberado"]:
            st.title("🛡️ Cofre da Diretoria (Acesso Restrito)")
            st.write("Digite a Senha Mestra da JNL para desbloquear o painel de senhas.")
            
            senha_digitada = st.text_input("Senha Mestra:", type="password", placeholder="Digite a Senha Mestra...")
            col1, col2 = st.columns([1, 5])
            with col1:
                if st.button("⬅️ VOLTAR"):
                    st.session_state["setor"] = None
                    st.rerun()
            with col2:
                if st.button("DESBLOQUEAR COFRE"):
                    if senha_digitada == SENHA_MESTRA:
                        st.session_state["admin_liberado"] = True
                        st.rerun()
                    else:
                        st.error("Senha Mestra Incorreta! Acesso Bloqueado.")
        
        else:
            st.title("🔐 Painel de Controle de Senhas (Diretoria)")
            if st.button("⬅️ TRANCAR COFRE E VOLTAR"):
                st.session_state["admin_liberado"] = False
                st.session_state["setor"] = None
                st.rerun()
            
            st.warning("Área de segurança máxima. O funcionário será desconectado se errar a nova senha na próxima vez.")
            conn = sqlite3.connect('jnl_master.db')
            df_usu = pd.read_sql_query("SELECT login, nome, setores FROM usuarios", conn)
            
            with st.form("form_senha"):
                usr_sel = st.selectbox("Selecione o Funcionário:", df_usu['login'].tolist())
                nova_senha = st.text_input("Definir Nova Senha:", type="password", placeholder="Nova senha...")
                if st.form_submit_button("Atualizar Senha no Sistema"):
                    c = conn.cursor()
                    c.execute("UPDATE usuarios SET senha = ? WHERE login = ?", (nova_senha, usr_sel))
                    conn.commit()
                    st.success(f"Senha de {usr_sel.upper()} atualizada com sucesso no banco de dados!")
            conn.close()

    # ====================================================
    # FLUXO 2: SETORES NORMAIS (VENDAS, ESTOQUE, ADM, ETC.)
    # ====================================================
    else:
        # Carregar Perfil da IA
        conn = sqlite3.connect('jnl_master.db'); c = conn.cursor()
        c.execute("SELECT nome_tratamento, instrucoes_ia FROM perfil_usuario WHERE usuario = ?", (user,))
        perfil = c.fetchone()
        nome_ia = perfil[0] if perfil else user_nome
        inst_ia = perfil[1] if perfil else ""
        conn.close()

        # --- BARRA LATERAL (COM PLANILHAS NO LUGAR CERTO) ---
        with st.sidebar:
            st.header(f"📍 {setor_atual}")
            if st.button("⬅️ TROCAR DE SETOR"): 
                st.session_state["setor"] = None
                st.session_state["admin_liberado"] = False # Trava o admin por segurança
                st.rerun()
            st.write("---")
            
            st.subheader("📂 ARQUIVOS (MACROS/DOCS)")
            up = st.file_uploader("Subir Arquivo", type=["xlsx", "xlsm", "docx", "pptx", "pdf", "csv"], accept_multiple_files=True)
            if st.button("📥 SALVAR"):
                if up:
                    for f in up:
                        with open(f.name, "wb") as file: file.write(f.getbuffer())
                        conn = sqlite3.connect('jnl_master.db'); c = conn.cursor()
                        c.execute("INSERT INTO arquivos_setoriais (setor, nome, caminho) VALUES (?, ?, ?)", (setor_atual, f.name, f.name))
                        conn.commit(); conn.close()
                    st.success("Salvo!")
                    st.rerun()
                    
            st.write("**Arquivos do Setor:**")
            conn = sqlite3.connect('jnl_master.db')
            df_arq = pd.read_sql_query("SELECT * FROM arquivos_setoriais WHERE setor = ?", conn, params=(setor_atual,))
            for _, arq in df_arq.iterrows():
                st.caption(f"📄 {arq['nome']}")
            conn.close()
            
            st.write("---")
            with st.expander("⚙️ MEU PERFIL IA"):
                n_nome = st.text_input("Como a IA te chama?", value=nome_ia, placeholder="Ex: Meu senhor")
                n_inst = st.text_area("Instruções Fixas:", value=inst_ia, placeholder="Ex: Formatar em maiúsculo...")
                if st.button("💾 Salvar Perfil"):
                    conn = sqlite3.connect('jnl_master.db'); c = conn.cursor()
                    c.execute("INSERT OR REPLACE INTO perfil_usuario (usuario, nome_tratamento, instrucoes_ia) VALUES (?, ?, ?)", (user, n_nome, n_inst))
                    conn.commit(); conn.close(); st.rerun()

        # --- ABAS PRINCIPAIS ---
        abas_nomes = ["💬 IA JNL", "👥 CHAT SETOR", "📅 AGENDA", "📝 NOTAS"]
        abas = st.tabs(abas_nomes)

        # ABA 1: IA JNL
        with abas[0]:
            st.subheader(f"Assistente JNL - {obter_saudacao()}, {nome_ia}")
            for msg in st.session_state["mensagens_ia"]:
                with st.chat_message(msg["role"]): st.markdown(msg["content"])
                
            if prompt := st.chat_input("Como posso ajudar a JNL hoje?"):
                st.session_state["mensagens_ia"].append({"role": "user", "content": prompt})
                with st.chat_message("user"): st.markdown(prompt)
                with st.chat_message("assistant"):
                    try:
                        contexto = busca_web(prompt) if any(palavra in prompt.lower() for palavra in ["hoje", "agora", "atual", "notícia", "cotação", "dólar", "pesquise", "busque"]) else ""
                        ctx = f"Você é a IA da JNL Importadora. Usuário: {nome_ia}. Regras fixas: {inst_ia}. Info de tempo real encontrada: {contexto}"
                        client = Groq(api_key=st.secrets["GROQ_API_KEY"])
                        resp = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role": "system", "content": ctx}] + st.session_state["mensagens_ia"]).choices[0].message.content
                        st.markdown(resp)
                        st.session_state["mensagens_ia"].append({"role": "assistant", "content": resp})
                    except Exception as e:
                        st.error("Erro na comunicação com a IA.")

        # ABA 2: CHAT DO SETOR
        with abas[1]:
            st.subheader(f"Mural de Comunicação: {setor_atual}")
            conn = sqlite3.connect('jnl_master.db')
            df_c = pd.read_sql_query("SELECT * FROM chat_setor WHERE setor = ? ORDER BY id ASC", conn, params=(setor_atual,))
            
            for _, row in df_c.iterrows():
                is_me = row['usuario'] == user
                align, bg = ("right", "#dcf8c6") if is_me else ("left", "#f1f0f0")
                
                if row['apagada'] == 1:
                    conteudo = "<i>🚫 Mensagem apagada</i>"
                    cor_texto = "#888888"
                else:
                    tag_edit = " *(Editada)*" if row['editada'] == 1 else ""
                    conteudo = f"{row['mensagem']}{tag_edit}"
                    cor_texto = "black"

                st.markdown(f"<div style='text-align: {align};'><div style='display: inline-block; background: {bg}; padding: 10px; border-radius: 10px; color: {cor_texto}; margin: 5px; min-width: 150px; text-align: left;'><b>{row['usuario'].upper()}</b><br>{conteudo}<br><small style='color: #666;'>{row['data_hora']}</small></div></div>", unsafe_allow_html=True)
                
                if is_me and row['apagada'] == 0:
                    try:
                        msg_time = datetime.strptime(row['timestamp_real'], '%Y-%m-%d %H:%M:%S')
                        minutos_passados = (get_now_br() - msg_time).total_seconds() / 60
                    except:
                        minutos_passados = 999 
                    
                    if minutos_passados <= 20:
                        with st.popover("⚙️ Opções (20 min)"):
                            nv = st.text_input("Editar Mensagem:", row['mensagem'], key=f"cedit_{row['id']}")
                            if st.button("Salvar Edição", key=f"bsave_{row['id']}"):
                                c = conn.cursor(); c.execute("UPDATE chat_setor SET mensagem = ?, editada = 1 WHERE id = ?", (nv, row['id'])); conn.commit(); st.rerun()
                            if st.button("🗑️ Apagar para todos", key=f"bdel_{row['id']}"):
                                c = conn.cursor(); c.execute("UPDATE chat_setor SET apagada = 1 WHERE id = ?", (row['id'],)); conn.commit(); st.rerun()

            with st.form("chat_f", clear_on_submit=True):
                m = st.text_input("Escreva sua mensagem...", placeholder="Digite aqui...")
                if st.form_submit_button("Enviar Mensagem"):
                    if m:
                        agora_br = get_now_br()
                        data_hora_display = agora_br.strftime('%d/%m %H:%M')
                        timestamp_real = agora_br.strftime('%Y-%m-%d %H:%M:%S')
                        c = conn.cursor()
                        c.execute("INSERT INTO chat_setor (setor, usuario, data_hora, mensagem, timestamp_real) VALUES (?, ?, ?, ?, ?)", (setor_atual, user, data_hora_display, m, timestamp_real))
                        conn.commit(); st.rerun()
            conn.close()

        # ABA 3: AGENDA
        with abas[2]:
            st.subheader("Agenda e Disparo de E-mails")
            with st.form("age_f", clear_on_submit=True):
                t_age = st.text_input("Título da Tarefa", placeholder="Ex: Enviar orçamento Komatsu")
                
                c1, c2, c3 = st.columns([2, 1, 1])
                d_age = c1.date_input("Data do Vencimento", format="DD/MM/YYYY")
                h_age = c2.selectbox("Hora", [f"{i:02d}" for i in range(24)])
                m_age = c3.selectbox("Minutos", ["00", "15", "30", "45"])
                
                p_age = st.text_input("Para (E-mail Principal)", placeholder="Ex: jessica@jnl.com.br")
                cc_age = st.text_input("CC (Com Cópia)", placeholder="Ex: felipe@jnl.com.br, compras@jnl.com.br")
                
                if st.form_submit_button("AGENDAR"):
                    data_completa = f"{d_age} {h_age}:{m_age}:00"
                    conn = sqlite3.connect('jnl_master.db'); c = conn.cursor()
                    c.execute("INSERT INTO calendario (usuario, titulo, data_hora, notificado, destinatarios, copias) VALUES (?, ?, ?, 0, ?, ?)", (user, t_age, data_completa, p_age, cc_age))
                    conn.commit(); conn.close(); st.rerun()
            
            conn = sqlite3.connect('jnl_master.db')
            df_res = pd.read_sql_query("SELECT * FROM calendario WHERE usuario = ?", conn, params=(user,))
            for _, r in df_res.iterrows():
                dt_obj = datetime.strptime(r['data_hora'], '%Y-%m-%d %H:%M:%S')
                data_br = dt_obj.strftime('%d/%m/%Y às %H:%M')
                
                with st.container(border=True):
                    st.write(f"📌 **{r['titulo']}** | 📅 {data_br}")
                    st.caption(f"Para: {r['destinatarios']} | CC: {r.get('copias', '')}")
                    
                    with st.expander("✏️ Gerenciar Agendamento"):
                        with st.form(f"edit_f_{r['id']}"):
                            n_tit = st.text_input("Título", value=r['titulo'])
                            n_dest = st.text_input("E-mail", value=r['destinatarios'])
                            if st.form_submit_button("Atualizar E-mail/Título"):
                                c = conn.cursor(); c.execute("UPDATE calendario SET titulo = ?, destinatarios = ? WHERE id = ?", (n_tit, n_dest, r['id'])); conn.commit(); st.rerun()
                        if st.button("🗑️ Deletar Tarefa", key=f"del_age_{r['id']}"):
                            c = conn.cursor(); c.execute("DELETE FROM calendario WHERE id = ?", (r['id'],)); conn.commit(); st.rerun()
            conn.close()

        # ABA 4: NOTAS
        with abas[3]:
            st.subheader("Bloco de Notas Pessoal")
            with st.form("nota_form", clear_on_submit=True):
                tn = st.text_input("Título", placeholder="Ex: Telefones Úteis")
                cn = st.text_area("Conteúdo", placeholder="Ex: Manoel Vendas: 1930346567...")
                if st.form_submit_button("Salvar Nota"):
                    conn = sqlite3.connect('jnl_master.db'); c = conn.cursor()
                    c.execute("INSERT INTO anotacoes (usuario, titulo, conteudo) VALUES (?, ?, ?)", (user, tn, cn))
                    conn.commit(); conn.close(); st.rerun()
            conn = sqlite3.connect('jnl_master.db')
            df_n = pd.read_sql_query("SELECT * FROM anotacoes WHERE usuario = ?", conn, params=(user,))
            for _, n in df_n.iterrows():
                with st.container(border=True):
                    st.write(f"**{n['titulo']}**")
                    st.write(n['conteudo'])
                    if st.button("🗑️ Remover", key=f"del_n_{n['id']}"):
                        c = conn.cursor(); c.execute("DELETE FROM anotacoes WHERE id = ?", (n['id'],)); conn.commit(); st.rerun()
            conn.close()