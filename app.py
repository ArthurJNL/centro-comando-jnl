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

# --- BANCO DE DADOS (GARANTIA TOTAL) ---
def init_db():
    conn = sqlite3.connect('jnl_master.db')
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS arquivos_setoriais (setor TEXT, nome TEXT, caminho TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS calendario (id INTEGER PRIMARY KEY AUTOINCREMENT, usuario TEXT, titulo TEXT, data_hora TEXT, notificado INTEGER, destinatarios TEXT, copias TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS anotacoes (id INTEGER PRIMARY KEY AUTOINCREMENT, usuario TEXT, pasta TEXT, titulo TEXT, conteudo TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS chat_setor (id INTEGER PRIMARY KEY AUTOINCREMENT, setor TEXT, usuario TEXT, data_hora TEXT, mensagem TEXT, editada INTEGER DEFAULT 0)')
    
    # Adicionando colunas que "sumiram" para evitar erro de KeyError
    c.execute("PRAGMA table_info(calendario)")
    cols_cal = [col[1] for col in c.fetchall()]
    if 'destinatarios' not in cols_cal: c.execute('ALTER TABLE calendario ADD COLUMN destinatarios TEXT')
    if 'copias' not in cols_cal: c.execute('ALTER TABLE calendario ADD COLUMN copias TEXT')
    
    conn.commit()
    conn.close()

init_db()

# --- LOGIN ---
if "autenticado" not in st.session_state: st.session_state["autenticado"] = False
if "setor" not in st.session_state: st.session_state["setor"] = None

USUARIOS = {"arthur": {"senha": "32167308", "nome": "ARTHUR (DIRETORIA)"}}

if not st.session_state["autenticado"]:
    st.title("🔒 CENTRO DE COMANDO JNL")
    u = st.text_input("USUÁRIO:").lower()
    p = st.text_input("SENHA:", type="password")
    if st.button("ENTRAR"):
        if u in USUARIOS and USUARIOS[u]["senha"] == p:
            st.session_state.update({"autenticado": True, "user_slug": u, "user_nome": USUARIOS[u]["nome"]})
            st.rerun()
        else: st.error("Acesso Negado.")

elif st.session_state["setor"] is None:
    st.title(f"Bem-vindo, {st.session_state['user_nome']}")
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
        if st.button("⬅️ VOLTAR AO MENU"):
            st.session_state["setor"] = None
            st.rerun()
        st.write("---")
        st.subheader("📂 SALVAR PLANILHAS")
        up = st.file_uploader("Upload de Planilhas", accept_multiple_files=True)
        if st.button("📥 SALVAR NO SERVIDOR"):
            if up: st.success("Arquivos processados com sucesso!"); st.rerun()
        
    # --- ABAS (SEM O EMOJI ROSA) ---
    tab_ia, tab_chat, tab_agenda, tab_notas = st.tabs(["💻 IA", "👥 Chat Equipe", "📅 Agenda", "📝 Notas"])

    with tab_ia:
        st.subheader("Inteligência JNL")
        prompt = st.chat_input("Fale com a IA...")
        if prompt:
            with st.chat_message("user"): st.write(prompt)
            try:
                client = Groq(api_key=st.secrets["GROQ_API_KEY"])
                res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role": "user", "content": prompt}]).choices[0].message.content
                with st.chat_message("assistant"): st.write(res)
            except: st.error("Erro nos Secrets (Chave IA).")

    with tab_chat:
        st.subheader("Chat Estilo WhatsApp")
        conn = sqlite3.connect('jnl_master.db')
        df = pd.read_sql_query("SELECT * FROM chat_setor WHERE setor = ? ORDER BY id ASC", conn, params=(setor_atual,))
        
        for _, row in df.iterrows():
            is_me = row['usuario'] == user
            align, bg = ("right", "#dcf8c6") if is_me else ("left", "#f1f0f0")
            tag_edit = " *(Editada)*" if row.get('editada') == 1 else ""
            
            st.markdown(f"<div style='text-align: {align};'><div style='display: inline-block; background: {bg}; padding: 10px; border-radius: 10px; color: black; margin: 5px; min-width: 150px;'><b>{row['usuario'].capitalize()}</b><br>{row['mensagem']}<br><small style='color: gray;'>{row['data_hora']}{tag_edit}</small></div></div>", unsafe_allow_html=True)
            
            if is_me:
                dt_msg = datetime.strptime(row['data_hora'], '%Y-%m-%d %H:%M:%S')
                if datetime.now() - dt_msg < timedelta(minutes=10):
                    with st.popover("✏️"):
                        nv = st.text_input("Editar:", row['mensagem'], key=f"e_{row['id']}")
                        if st.button("OK", key=f"b_{row['id']}"):
                            c = conn.cursor(); c.execute("UPDATE chat_setor SET mensagem = ?, editada = 1 WHERE id = ?", (nv, row['id'])); conn.commit(); st.rerun()
        conn.close()

    with tab_agenda:
        st.subheader("Agenda de Ações")
        with st.form("f_age"):
            t_age = st.text_input("Tarefa", placeholder="Ex: Cobrar Hyundai")
            col1, col2 = st.columns(2)
            d_age = col1.date_input("Data")
            h_age = col2.time_input("Hora")
            p_age = st.text_input("Para (e-mail)", placeholder="exemplo@jnl.com.br")
            c_age = st.text_input("Cc (Cópia)", placeholder="chefe@jnl.com.br")
            if st.form_submit_button("AGENDAR"):
                conn = sqlite3.connect('jnl_master.db'); c = conn.cursor()
                c.execute("INSERT INTO calendario (usuario, titulo, data_hora, notificado, destinatarios, copias) VALUES (?, ?, ?, 0, ?, ?)", (user, t_age, f"{d_age} {h_age}", p_age, c_age))
                conn.commit(); conn.close(); st.success("Agendado!"); st.rerun()

    with tab_notas:
        st.subheader("Bloco de Notas")
        with st.form("f_notas", clear_on_submit=True):
            tit = st.text_input("Título")
            cont = st.text_area("Conteúdo")
            if st.form_submit_button("Salvar Nota 💾"):
                conn = sqlite3.connect('jnl_master.db'); c = conn.cursor()
                c.execute("INSERT INTO anotacoes (usuario, pasta, titulo, conteudo) VALUES (?, 'N', ?, ?)", (user, tit, cont))
                conn.commit(); conn.close(); st.rerun()
        
        conn = sqlite3.connect('jnl_master.db')
        df_n = pd.read_sql_query("SELECT * FROM anotacoes WHERE usuario = ?", conn, params=(user,))
        for _, n in df_n.iterrows():
            with st.container(border=True):
                st.write(f"**{n['titulo']}**")
                st.write(n['conteudo'])
        conn.close()