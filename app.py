import streamlit as st
import pandas as pd
import sqlite3
import os
import smtplib # Motor de e-mail compatível com a Nuvem
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timedelta
from groq import Groq

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="SISTEMA JNL", page_icon="🏢", layout="wide")

# --- BANCO DE DADOS (PROTEÇÃO CONTRA ERROS) ---
def init_db():
    conn = sqlite3.connect('jnl_master.db')
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS arquivos_setoriais (setor TEXT, nome TEXT, caminho TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS calendario (id INTEGER PRIMARY KEY AUTOINCREMENT, usuario TEXT, titulo TEXT, data_hora TEXT, notificado INTEGER, destinatarios TEXT, copias TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS anotacoes (id INTEGER PRIMARY KEY AUTOINCREMENT, usuario TEXT, pasta TEXT, titulo TEXT, conteudo TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS chat_setor (id INTEGER PRIMARY KEY AUTOINCREMENT, setor TEXT, usuario TEXT, data_hora TEXT, mensagem TEXT, editada INTEGER DEFAULT 0)')
    
    c.execute("PRAGMA table_info(calendario)")
    cols = [col[1] for col in c.fetchall()]
    if 'destinatarios' not in cols: c.execute('ALTER TABLE calendario ADD COLUMN destinatarios TEXT')
    
    conn.commit()
    conn.close()

init_db()

# --- FUNÇÃO DE E-MAIL PARA A NUVEM (SMTP) ---
def enviar_email_nuvem(para, assunto, corpo):
    try:
        # Puxa as credenciais que o senhor salvou nos SECRETS do Streamlit
        msg = MIMEMultipart()
        msg['From'] = st.secrets["OUTLOOK_USER_ARTHUR"]
        msg['To'] = para
        msg['Subject'] = assunto
        msg.attach(MIMEText(corpo, 'plain'))
        
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(st.secrets["OUTLOOK_USER_ARTHUR"], st.secrets["OUTLOOK_PASS_ARTHUR"])
        server.send_message(msg)
        server.quit()
        return True
    except: return False

# --- SESSÃO E LOGIN ---
if "autenticado" not in st.session_state: st.session_state["autenticado"] = False
if "setor" not in st.session_state: st.session_state["setor"] = None

USUARIOS = {"arthur": {"senha": "32167308", "nome": "ARTHUR (DIRETORIA)", "setores": ["TODOS"]}}

if not st.session_state["autenticado"]:
    st.title("🏢 SISTEMA JNL - ACESSO")
    u = st.text_input("USUÁRIO:").lower()
    p = st.text_input("SENHA:", type="password")
    if st.button("ENTRAR"):
        if u in USUARIOS and USUARIOS[u]["senha"] == p:
            st.session_state.update({"autenticado": True, "user_slug": u, "user_nome": USUARIOS[u]["nome"]})
            st.rerun()
        else: st.error("Erro!")

elif st.session_state["setor"] is None:
    st.title(f"Olá, {st.session_state['user_nome']}")
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

    # --- BARRA LATERAL (PLANILHAS) ---
    with st.sidebar:
        st.header(f"📍 {setor_atual}")
        if st.button("⬅️ VOLTAR"):
            st.session_state["setor"] = None
            st.rerun()
        st.write("---")
        st.subheader("📂 PLANILHAS")
        up = st.file_uploader("Upload", accept_multiple_files=True)
        if st.button("📥 SALVAR"):
            if up: st.success("Arquivos prontos!"); st.rerun()
        
    # --- ABAS ---
    tab_ia, tab_chat, tab_agenda, tab_notas = st.tabs(["💻 IA", "👥 Chat", "📅 Agenda", "📝 Notas"])

    with tab_chat:
        st.subheader("Chat do Setor")
        conn = sqlite3.connect('jnl_master.db')
        df = pd.read_sql_query("SELECT * FROM chat_setor WHERE setor = ? ORDER BY id ASC", conn, params=(setor_atual,))
        conn.close()

        for _, row in df.iterrows():
            is_me = row['usuario'] == user
            align, bg = ("right", "#dcf8c6") if is_me else ("left", "#f1f0f0")
            tag = " *(Editada)*" if row.get('editada') == 1 else ""
            
            st.markdown(f"<div style='text-align: {align};'><div style='display: inline-block; background: {bg}; padding: 10px; border-radius: 10px; color: black; margin: 5px;'><b>{row['usuario'].capitalize()}</b><br>{row['mensagem']}<br><small>{row['data_hora']}{tag}</small></div></div>", unsafe_allow_html=True)
            
            if is_me:
                try:
                    dt = datetime.strptime(row['data_hora'], '%Y-%m-%d %H:%M:%S')
                    if datetime.now() - dt < timedelta(minutes=10):
                        with st.popover("Editar"):
                            nv = st.text_input("Novo texto:", row['mensagem'], key=f"e_{row['id']}")
                            if st.button("OK", key=f"b_{row['id']}"):
                                conn = sqlite3.connect('jnl_master.db'); c = conn.cursor()
                                c.execute("UPDATE chat_setor SET mensagem = ?, editada = 1 WHERE id = ?", (nv, row['id']))
                                conn.commit(); conn.close(); st.rerun()
                except: pass

    with tab_notas:
        st.subheader("Bloco de Notas")
        with st.form("f_notas", clear_on_submit=True):
            t_nota = st.text_input("Título")
            c_nota = st.text_area("Conteúdo")
            if st.form_submit_button("Salvar Nota"):
                conn = sqlite3.connect('jnl_master.db'); c = conn.cursor()
                c.execute("INSERT INTO anotacoes (usuario, pasta, titulo, conteudo) VALUES (?, 'N', ?, ?)", (user, t_nota, c_nota))
                conn.commit(); conn.close(); st.rerun()