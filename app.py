import streamlit as st
import pandas as pd
import sqlite3
import os
from datetime import datetime, timedelta
from groq import Groq

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="SISTEMA JNL", page_icon="🏢", layout="wide")

# --- BANCO DE DADOS (ESTRUTURA COMPLETA) ---
def init_db():
    conn = sqlite3.connect('jnl_master.db')
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS calendario (id INTEGER PRIMARY KEY AUTOINCREMENT, usuario TEXT, titulo TEXT, data_hora TEXT, notificado INTEGER, destinatarios TEXT, copias TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS anotacoes (id INTEGER PRIMARY KEY AUTOINCREMENT, usuario TEXT, titulo TEXT, conteudo TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS chat_setor (id INTEGER PRIMARY KEY AUTOINCREMENT, setor TEXT, usuario TEXT, data_hora TEXT, mensagem TEXT, editada INTEGER DEFAULT 0)')
    c.execute('CREATE TABLE IF NOT EXISTS perfil_usuario (usuario TEXT PRIMARY KEY, nome_tratamento TEXT, instrucoes_ia TEXT)')
    
    # Verificação de colunas da Agenda
    c.execute("PRAGMA table_info(calendario)")
    cols = [col[1] for col in c.fetchall()]
    if 'destinatarios' not in cols: c.execute('ALTER TABLE calendario ADD COLUMN destinatarios TEXT')
    if 'copias' not in cols: c.execute('ALTER TABLE calendario ADD COLUMN copias TEXT')
    conn.commit()
    conn.close()

init_db()

# --- LÓGICA DE SAUDAÇÃO INTELIGENTE ---
def obter_saudacao():
    hora_atual = datetime.now().hour
    if 5 <= hora_atual < 12: return "Bom dia"
    elif 12 <= hora_atual < 18: return "Boa tarde"
    else: return "Boa noite"

# --- LOGIN E MEMÓRIA DE SESSÃO ---
if "autenticado" not in st.session_state: st.session_state["autenticado"] = False
if "setor" not in st.session_state: st.session_state["setor"] = None
if "historico_ia" not in st.session_state: st.session_state["historico_ia"] = []

USUARIOS = {"arthur": {"senha": "32167308", "nome": "ARTHUR"}}

if not st.session_state["autenticado"]:
    st.title("🔒 ACESSO JNL")
    u = st.text_input("Usuário:").lower()
    p = st.text_input("Senha:", type="password")
    if st.button("ENTRAR"):
        if u in USUARIOS and USUARIOS[u]["senha"] == p:
            st.session_state.update({"autenticado": True, "user_slug": u})
            st.rerun()
        else: st.error("Dados incorretos.")

elif st.session_state["setor"] is None:
    st.title(f"🏢 {obter_saudacao()}! Bem-vindo ao Centro de Comando JNL.")
    setores = ["ADMINISTRATIVO", "FINANCEIRO", "VENDAS", "COMPRAS", "SOLUÇÕES CORPORATIVAS", "GERAL"]
    cols = st.columns(3)
    for i, s in enumerate(setores):
        with cols[i % 3]:
            if st.button(s, use_container_width=True):
                st.session_state["setor"] = s
                st.rerun()
else:
    setor_atual = st.session_state["setor"]
    user = st.session_state["user_slug"]

    # --- RECUPERAR PREFERÊNCIAS DO BANCO ---
    conn = sqlite3.connect('jnl_master.db'); c = conn.cursor()
    c.execute("SELECT nome_tratamento, instrucoes_ia FROM perfil_usuario WHERE usuario = ?", (user,))
    perfil = c.fetchone()
    nome_ia = perfil[0] if perfil else "Comandante"
    regras_ia = perfil[1] if perfil else "Seja um assistente eficiente."
    conn.close()

    with st.sidebar:
        st.header(f"📍 {setor_atual}")
        if st.button("⬅️ VOLTAR AO MENU"): st.session_state["setor"] = None; st.rerun()
        st.write("---")
        with st.expander("⚙️ CONFIGURAR MINHA IA"):
            n_nome = st.text_input("Como a IA te chama?", value=nome_ia)
            n_inst = st.text_area("Instruções (Ex: Orçamentos):", value=regras_ia)
            if st.button("💾 Salvar Perfil"):
                conn = sqlite3.connect('jnl_master.db'); c = conn.cursor()
                c.execute("INSERT OR REPLACE INTO perfil_usuario (usuario, nome_tratamento, instrucoes_ia) VALUES (?, ?, ?)", (user, n_nome, n_inst))
                conn.commit(); conn.close(); st.success("Perfil Atualizado!"); st.rerun()

    tab_ia, tab_chat, tab_agenda, tab_notes = st.tabs(["💬 IA JNL", "👥 CHAT EQUIPE", "📅 AGENDA", "📝 NOTAS"])

    # --- IA COM HISTÓRICO E PERSONALIDADE ---
    with tab_ia:
        st.subheader(f"{obter_saudacao()}, {nome_ia}!")
        for msg in st.session_state["historico_ia"]:
            with st.chat_message(msg["role"]): st.markdown(msg["content"])
        
        if prompt := st.chat_input("Em que posso ajudar a JNL agora?"):
            st.session_state["historico_ia"].append({"role": "user", "content": prompt})
            with st.chat_message("user"): st.markdown(prompt)
            with st.chat_message("assistant"):
                try:
                    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
                    contexto_sistema = f"Você é o assistente da JNL. O usuário é {nome_ia}. Siga estritamente: {regras_ia}"
                    resp = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role": "system", "content": contexto_sistema}] + st.session_state["historico_ia"]).choices[0].message.content
                    st.markdown(resp)
                    st.session_state["historico_ia"].append({"role": "assistant", "content": resp})
                except: st.error("Erro na chave da IA.")

    # --- AGENDA COM STATUS REAL ---
    with tab_agenda:
        st.subheader("Gerenciamento de Ações")
        with st.form("f_age"):
            t_age = st.text_input("Tarefa", placeholder="Ex: Cobrar Hyundai")
            col1, col2 = st.columns(2)
            d_age = col1.date_input("Data")
            h_age = col2.time_input("Hora")
            p_age = st.text_input("Para", placeholder="email@jnl.com.br")
            c_age = st.text_input("Cc (Cópia)", placeholder="diretoria@jnl.com.br")
            if st.form_submit_button("AGENDAR"):
                conn = sqlite3.connect('jnl_master.db'); c = conn.cursor()
                c.execute("INSERT INTO calendario (usuario, titulo, data_hora, notificado, destinatarios, copias) VALUES (?, ?, ?, 0, ?, ?)", (user, t_age, f"{d_age} {h_age}", p_age, c_age))
                conn.commit(); conn.close(); st.success("Agendado!"); st.rerun()

        st.write("---")
        conn = sqlite3.connect('jnl_master.db')
        df_cal = pd.read_sql_query("SELECT * FROM calendario WHERE usuario = ? ORDER BY data_hora ASC", conn, params=(user,))
        for _, r in df_cal.iterrows():
            # ACOMPANHAMENTO DE STATUS
            data_limite = datetime.strptime(r['data_hora'], '%Y-%m-%d %H:%M:%S')
            status = "🔴 VENCIDO" if data_limite < datetime.now() else "🟢 NO PRAZO"
            with st.container(border=True):
                c_a, c_b = st.columns([4, 1])
                c_a.write(f"**{r['titulo']}** | {status}")
                c_a.write(f"📅 {r['data_hora']} | ✉️ {r['destinatarios']}")
                if c_b.button("🗑️", key=f"del_a_{r['id']}"):
                    c = conn.cursor(); c.execute("DELETE FROM calendario WHERE id = ?", (r['id'],)); conn.commit(); st.rerun()
        conn.close()

    # --- NOTAS COM EDIÇÃO EFICAZ ---
    with tab_notes:
        st.subheader("Bloco de Notas da Diretoria")
        with st.form("f_n", clear_on_submit=True):
            tn = st.text_input("Título")
            cn = st.text_area("Conteúdo")
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
                c1, c2 = st.columns(2)
                with c1.popover("✏️ Editar"):
                    new_t = st.text_input("Título", n['titulo'], key=f"nt_{n['id']}")
                    new_c = st.text_area("Conteúdo", n['conteudo'], key=f"nc_{n['id']}")
                    if st.button("Salvar Edição", key=f"sb_{n['id']}"):
                        c = conn.cursor(); c.execute("UPDATE anotacoes SET titulo = ?, conteudo = ? WHERE id = ?", (new_t, new_c, n['id'])); conn.commit(); st.rerun()
                if c2.button("🗑️ Apagar", key=f"db_{n['id']}"):
                    c = conn.cursor(); c.execute("DELETE FROM anotacoes WHERE id = ?", (n['id'],)); conn.commit(); st.rerun()
        conn.close()