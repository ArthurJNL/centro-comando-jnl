import streamlit as st
import pandas as pd
import sqlite3
import os
from datetime import datetime, timedelta
from groq import Groq

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="SISTEMA JNL", page_icon="🏢", layout="wide")
SENHA_MESTRA = "JNLDIRETORIA"

# --- BANCO DE DADOS ---
def init_db():
    conn = sqlite3.connect('jnl_master.db')
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS usuarios (login TEXT PRIMARY KEY, senha TEXT, nome TEXT, setores TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS arquivos_setoriais (setor TEXT, nome TEXT, caminho TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS calendario (id INTEGER PRIMARY KEY AUTOINCREMENT, usuario TEXT, titulo TEXT, data_hora TEXT, notificado INTEGER, destinatarios TEXT, copias TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS anotacoes (id INTEGER PRIMARY KEY AUTOINCREMENT, usuario TEXT, titulo TEXT, conteudo TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS chat_setor (id INTEGER PRIMARY KEY AUTOINCREMENT, setor TEXT, usuario TEXT, data_hora TEXT, mensagem TEXT, editada INTEGER DEFAULT 0, apagada INTEGER DEFAULT 0, timestamp_real TEXT)')
    # Nova tabela para o Livro de Ordens da IA
    c.execute('CREATE TABLE IF NOT EXISTS ordens_ia (id INTEGER PRIMARY KEY AUTOINCREMENT, usuario TEXT, ordem TEXT, data_criacao TEXT)')
    
    # Semente de usuários (se vazio)
    c.execute('SELECT COUNT(*) FROM usuarios')
    if c.fetchone()[0] == 0:
        seed = [("arthur", "32167308", "ARTHUR", "ALL"), ("felipe", "JNL2026", "FELIPE", "ALL"), ("pedro", "JNL2026", "PEDRO", "ALL")]
        c.executemany("INSERT INTO usuarios VALUES (?, ?, ?, ?)", seed)
    
    conn.commit()
    conn.close()

init_db()

def get_now_br():
    return datetime.utcnow() - timedelta(hours=3)

def obter_saudacao():
    hora = get_now_br().hour
    if 5 <= hora < 12: return "Bom dia"
    elif 12 <= hora < 18: return "Boa tarde"
    else: return "Boa noite"

def busca_web(prompt):
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            resultados = [r['body'] for r in ddgs.text(prompt, max_results=2)]
            return " ".join(resultados) if resultados else ""
    except: return ""

# --- ESTADO ---
if "autenticado" not in st.session_state: st.session_state["autenticado"] = False
if "setor" not in st.session_state: st.session_state["setor"] = None
if "mensagens_ia" not in st.session_state: st.session_state["mensagens_ia"] = []
if "admin_liberado" not in st.session_state: st.session_state["admin_liberado"] = False

# --- LOGIN ---
if not st.session_state["autenticado"]:
    st.title("🔒 CENTRO DE COMANDO JNL")
    u = st.text_input("Usuário:").lower()
    p = st.text_input("Senha:", type="password")
    if st.button("ACESSAR"):
        conn = sqlite3.connect('jnl_master.db'); c = conn.cursor()
        c.execute("SELECT senha, nome, setores FROM usuarios WHERE login = ?", (u,))
        user_data = c.fetchone(); conn.close()
        if user_data and user_data[0] == p:
            st.session_state.update({"autenticado": True, "user_slug": u, "user_nome": user_data[1], "user_setores": user_data[2]})
            st.rerun()
        else: st.error("Acesso Negado.")

# --- SELEÇÃO DE SETOR ---
elif st.session_state["setor"] is None:
    st.title(f"🏢 {obter_saudacao()}! Bem-vindo, {st.session_state['user_nome']}.")
    setores_base = ["ADMINISTRATIVO", "FINANCEIRO", "FATURAMENTO", "VENDAS", "COMPRAS", "ESTOQUE", "SOLUÇÕES CORPORATIVAS", "PROJETOS/IMPORTAÇÃO", "RH", "GERAL"]
    permissoes = st.session_state["user_setores"]
    setores_visiveis = setores_base if permissoes == "ALL" else permissoes.split(",")
    if permissoes == "ALL": setores_visiveis.append("🔐 PAINEL ADMIN")
    cols = st.columns(3)
    for i, s in enumerate(setores_visiveis):
        with cols[i % 3]:
            if st.button(s, use_container_width=True, type="primary" if "ADMIN" in s else "secondary"):
                st.session_state["setor"] = s; st.rerun()

# --- DASHBOARD ---
else:
    setor_atual = st.session_state["setor"]
    user = st.session_state["user_slug"]
    
    # 1. COFRE ADMIN
    if setor_atual == "🔐 PAINEL ADMIN":
        if not st.session_state["admin_liberado"]:
            st.title("🛡️ Cofre da Diretoria")
            sm = st.text_input("Senha Mestra:", type="password")
            if st.button("DESBLOQUEAR"):
                if sm == SENHA_MESTRA: st.session_state["admin_liberado"] = True; st.rerun()
                else: st.error("Incorreta.")
            if st.button("⬅️ VOLTAR"): st.session_state["setor"] = None; st.rerun()
        else:
            st.title("🔐 Gestão de Senhas")
            if st.button("⬅️ TRANCAR E VOLTAR"): st.session_state["admin_liberado"] = False; st.session_state["setor"] = None; st.rerun()
            conn = sqlite3.connect('jnl_master.db')
            df_u = pd.read_sql_query("SELECT login, nome FROM usuarios", conn)
            with st.form("f_senha"):
                u_sel = st.selectbox("Funcionário:", df_u['login'].tolist())
                n_s = st.text_input("Nova Senha:", type="password")
                if st.form_submit_button("Atualizar"):
                    c = conn.cursor(); c.execute("UPDATE usuarios SET senha = ? WHERE login = ?", (n_s, u_sel)); conn.commit(); st.success("Sucesso!"); conn.close()

    # 2. SETORES COMUNS
    else:
        with st.sidebar:
            st.header(f"📍 {setor_atual}")
            if st.button("⬅️ TROCAR SETOR"): st.session_state["setor"] = None; st.rerun()
            st.write("---")
            
            # --- LIVRO DE ORDENS IA (REFORMULADO) ---
            st.subheader("⚙️ MEU PERFIL IA")
            with st.expander("📝 Adicionar Nova Ordem"):
                nova_ordem = st.text_area("Escreva o que a IA deve saber:", placeholder="Ex: Sempre me chame de Comandante.")
                if st.button("Salvar Ordem"):
                    if nova_ordem:
                        conn = sqlite3.connect('jnl_master.db'); c = conn.cursor()
                        c.execute("INSERT INTO ordens_ia (usuario, ordem, data_criacao) VALUES (?, ?, ?)", (user, nova_ordem, get_now_br().strftime('%Y-%m-%d %H:%M:%S')))
                        conn.commit(); conn.close(); st.rerun()
            
            st.write("**Ordens Ativas:**")
            conn = sqlite3.connect('jnl_master.db')
            ordens_df = pd.read_sql_query("SELECT * FROM ordens_ia WHERE usuario = ? ORDER BY data_criacao ASC", conn, params=(user,))
            for _, o in ordens_df.iterrows():
                with st.container(border=True):
                    st.caption(o['ordem'])
                    col_e, col_d = st.columns(2)
                    if col_e.button("🗑️", key=f"del_o_{o['id']}"):
                        c = conn.cursor(); c.execute("DELETE FROM ordens_ia WHERE id = ?", (o['id'],)); conn.commit(); st.rerun()
                    if col_d.button("✏️", key=f"edit_o_{o['id']}"):
                        st.session_state[f"editando_{o['id']}"] = True
                    
                    if st.session_state.get(f"editando_{o['id']}"):
                        n_val = st.text_area("Editar:", value=o['ordem'], key=f"txt_o_{o['id']}")
                        if st.button("Confirmar", key=f"conf_o_{o['id']}"):
                            c = conn.cursor(); c.execute("UPDATE ordens_ia SET ordem = ? WHERE id = ?", (n_val, o['id'])); conn.commit(); st.session_state[f"editando_{o['id']}"] = False; st.rerun()
            conn.close()

            st.write("---")
            st.subheader("📂 ARQUIVOS")
            up = st.file_uploader("Upload", accept_multiple_files=True)
            if st.button("📥 SALVAR"):
                if up:
                    for f in up:
                        with open(f.name, "wb") as file: file.write(f.getbuffer())
                        conn = sqlite3.connect('jnl_master.db'); c = conn.cursor(); c.execute("INSERT INTO arquivos_setoriais (setor, nome, caminho) VALUES (?, ?, ?)", (setor_atual, f.name, f.name)); conn.commit(); conn.close()
                    st.success("Salvo!"); st.rerun()

        # --- ABAS ---
        tab_ia, tab_chat, tab_age, tab_note = st.tabs(["💬 IA JNL", "👥 CHAT", "📅 AGENDA", "📝 NOTAS"])
        
        with tab_ia:
            st.subheader(f"Assistente JNL - {obter_saudacao()}")
            for msg in st.session_state["mensagens_ia"]:
                with st.chat_message(msg["role"]): st.markdown(msg["content"])
            
            if prompt := st.chat_input("Fale com o sistema..."):
                st.session_state["mensagens_ia"].append({"role": "user", "content": prompt})
                with st.chat_message("user"): st.markdown(prompt)
                with st.chat_message("assistant"):
                    # Coleta todas as ordens e cria o bloco de regras (mais recentes por último)
                    conn = sqlite3.connect('jnl_master.db')
                    res_ordens = pd.read_sql_query("SELECT ordem FROM ordens_ia WHERE usuario = ? ORDER BY data_criacao ASC", conn, params=(user,))
                    bloco_regras = "\n".join(res_ordens['ordem'].tolist())
                    conn.close()
                    
                    contexto = busca_web(prompt) if any(x in prompt.lower() for x in ["hoje", "dólar", "agora", "pesquise"]) else ""
                    ctx = f"Você é a IA da JNL. REGRAS DO USUÁRIO (Priorize as últimas): {bloco_regras}. INFO WEB: {contexto}"
                    
                    try:
                        client = Groq(api_key=st.secrets["GROQ_API_KEY"])
                        resp = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role": "system", "content": ctx}] + st.session_state["mensagens_ia"]).choices[0].message.content
                        st.markdown(resp); st.session_state["mensagens_ia"].append({"role": "assistant", "content": resp})
                    except: st.error("Erro na Groq.")

        # --- CHAT SETORIAL (20 MIN) ---
        with tab_chat:
            conn = sqlite3.connect('jnl_master.db')
            df_c = pd.read_sql_query("SELECT * FROM chat_setor WHERE setor = ? ORDER BY id ASC", conn, params=(setor_atual,))
            for _, row in df_c.iterrows():
                is_me = row['usuario'] == user
                align, bg = ("right", "#dcf8c6") if is_me else ("left", "#f1f0f0")
                conteudo = "<i>🚫 Mensagem apagada</i>" if row['apagada'] == 1 else f"{row['mensagem']} {'*(Editada)*' if row['editada'] == 1 else ''}"
                st.markdown(f"<div style='text-align: {align};'><div style='display: inline-block; background: {bg}; padding: 10px; border-radius: 10px; color: black; margin: 5px; min-width: 150px;'><b>{row['usuario'].upper()}</b><br>{conteudo}<br><small>{row['data_hora']}</small></div></div>", unsafe_allow_html=True)
                if is_me and row['apagada'] == 0:
                    try:
                        min_pass = (get_now_br() - datetime.strptime(row['timestamp_real'], '%Y-%m-%d %H:%M:%S')).total_seconds() / 60
                        if min_pass <= 20:
                            with st.popover("⚙️"):
                                nv_m = st.text_input("Editar:", row['mensagem'], key=f"e_{row['id']}")
                                if st.button("Salvar", key=f"s_{row['id']}"):
                                    c = conn.cursor(); c.execute("UPDATE chat_setor SET mensagem = ?, editada = 1 WHERE id = ?", (nv_m, row['id'])); conn.commit(); st.rerun()
                                if st.button("Apagar", key=f"a_{row['id']}"):
                                    c = conn.cursor(); c.execute("UPDATE chat_setor SET apagada = 1 WHERE id = ?", (row['id'],)); conn.commit(); st.rerun()
                    except: pass
            with st.form("f_chat", clear_on_submit=True):
                m = st.text_input("Mensagem:")
                if st.form_submit_button("Enviar"):
                    if m:
                        agora = get_now_br()
                        c = conn.cursor(); c.execute("INSERT INTO chat_setor (setor, usuario, data_hora, mensagem, timestamp_real) VALUES (?, ?, ?, ?, ?)", (setor_atual, user, agora.strftime('%d/%m %H:%M'), m, agora.strftime('%Y-%m-%d %H:%M:%S'))); conn.commit(); st.rerun()
            conn.close()

        # --- AGENDA (PT-BR) ---
        with tab_age:
            with st.form("f_age", clear_on_submit=True):
                t = st.text_input("Tarefa", placeholder="Ex: Ligar para Volvo")
                c1, c2, c3 = st.columns([2,1,1])
                d = c1.date_input("Data", format="DD/MM/YYYY")
                h = c2.selectbox("H", [f"{i:02d}" for i in range(24)])
                mi = c3.selectbox("M", ["00", "15", "30", "45"])
                p = st.text_input("Para", placeholder="email@jnl.com.br")
                cc = st.text_input("CC", placeholder="copia@jnl.com.br")
                if st.form_submit_button("Agendar"):
                    conn = sqlite3.connect('jnl_master.db'); c = conn.cursor(); c.execute("INSERT INTO calendario (usuario, titulo, data_hora, notificado, destinatarios, copias) VALUES (?, ?, ?, 0, ?, ?)", (user, t, f"{d} {h}:{mi}:00", p, cc)); conn.commit(); conn.close(); st.rerun()
            conn = sqlite3.connect('jnl_master.db')
            df_a = pd.read_sql_query("SELECT * FROM calendario WHERE usuario = ?", conn, params=(user,))
            for _, r in df_a.iterrows():
                dt = datetime.strptime(r['data_hora'], '%Y-%m-%d %H:%M:%S').strftime('%d/%m/%Y %H:%M')
                with st.container(border=True):
                    st.write(f"📌 {r['titulo']} | 📅 {dt}")
                    if st.button("🗑️", key=f"da_{r['id']}"):
                        c = conn.cursor(); c.execute("DELETE FROM calendario WHERE id = ?", (r['id'],)); conn.commit(); st.rerun()
            conn.close()

        # --- NOTAS ---
        with tab_note:
            with st.form("f_not", clear_on_submit=True):
                tn = st.text_input("Título"); cn = st.text_area("Conteúdo")
                if st.form_submit_button("Salvar"):
                    conn = sqlite3.connect('jnl_master.db'); c = conn.cursor(); c.execute("INSERT INTO anotacoes (usuario, titulo, conteudo) VALUES (?, ?, ?)", (user, tn, cn)); conn.commit(); conn.close(); st.rerun()
            conn = sqlite3.connect('jnl_master.db')
            df_n = pd.read_sql_query("SELECT * FROM anotacoes WHERE usuario = ?", conn, params=(user,))
            for _, n in df_n.iterrows():
                with st.container(border=True):
                    st.write(f"**{n['titulo']}**"); st.write(n['conteudo'])
                    if st.button("🗑️", key=f"dn_{n['id']}"):
                        c = conn.cursor(); c.execute("DELETE FROM anotacoes WHERE id = ?", (n['id'],)); conn.commit(); st.rerun()
            conn.close()