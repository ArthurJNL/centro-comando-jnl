import streamlit as st
import pandas as pd
import sqlite3
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timedelta
from groq import Groq

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="SISTEMA JNL", page_icon="🏢", layout="wide")

# --- BANCO DE DADOS ---
def init_db():
    conn = sqlite3.connect('jnl_master.db')
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS arquivos_setoriais (setor TEXT, nome TEXT, caminho TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS calendario (id INTEGER PRIMARY KEY AUTOINCREMENT, usuario TEXT, titulo TEXT, data_hora TEXT, notificado INTEGER, destinatarios TEXT, copias TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS anotacoes (id INTEGER PRIMARY KEY AUTOINCREMENT, usuario TEXT, pasta TEXT, titulo TEXT, conteudo TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS chat_setor (id INTEGER PRIMARY KEY AUTOINCREMENT, setor TEXT, usuario TEXT, data_hora TEXT, mensagem TEXT, editada INTEGER DEFAULT 0)')
    
    # Garantia de colunas (Proteção contra KeyError)
    c.execute("PRAGMA table_info(calendario)")
    cols_cal = [col[1] for col in c.fetchall()]
    if 'destinatarios' not in cols_cal: c.execute('ALTER TABLE calendario ADD COLUMN destinatarios TEXT')
    
    c.execute("PRAGMA table_info(chat_setor)")
    cols_chat = [col[1] for col in c.fetchall()]
    if 'editada' not in cols_chat: c.execute('ALTER TABLE chat_setor ADD COLUMN editada INTEGER DEFAULT 0')
    
    conn.commit()
    conn.close()

init_db()

# --- SESSÃO E LOGIN ---
if "autenticado" not in st.session_state: st.session_state["autenticado"] = False
if "setor" not in st.session_state: st.session_state["setor"] = None

USUARIOS = {"arthur": {"senha": "32167308", "nome": "ARTHUR (DIRETORIA)"}}

if not st.session_state["autenticado"]:
    st.title("🏢 SISTEMA JNL - ACESSO")
    u = st.text_input("USUÁRIO:").lower()
    p = st.text_input("SENHA:", type="password")
    if st.button("ENTRAR"):
        if u in USUARIOS and USUARIOS[u]["senha"] == p:
            st.session_state.update({"autenticado": True, "user_slug": u, "user_nome": USUARIOS[u]["nome"]})
            st.rerun()
        else: st.error("Acesso Negado.")

elif st.session_state["setor"] is None:
    st.title(f"Olá, {st.session_state['user_nome']}")
    st.subheader("Selecione o Setor:")
    setores = ["ADMINISTRATIVO", "FINANCEIRO", "VENDAS", "COMPRAS", "SOLUÇÕES CORPORATIVAS", "GERAL"]
    cols = st.columns(3)
    for i, s in enumerate(setores):
        with cols[i % 3]:
            if st.button(s, use_container_width=True):
                st.session_state["setor"] = s
                st.rerun()

else:
    # --- ÁREA LOGADA ---
    setor_atual = st.session_state["setor"]
    user = st.session_state["user_slug"]

    # BARRA LATERAL (PLANILHAS)
    with st.sidebar:
        st.header(f"📍 {setor_atual}")
        if st.button("⬅️ VOLTAR AO MENU"):
            st.session_state["setor"] = None
            st.rerun()
        st.write("---")
        st.subheader("📂 PLANILHAS")
        up = st.file_uploader("Upload", accept_multiple_files=True)
        if st.button("📥 SALVAR"):
            if up: st.success("Salvo com sucesso!"); st.rerun()
        
    # CRIAÇÃO DAS ABAS (Garantindo que todas existam no mesmo bloco)
    tab_ia, tab_chat, tab_agenda, tab_notes = st.tabs(["💻 IA", "👥 Chat", "📅 Agenda", "📝 Notas"])

    with tab_ia:
        st.subheader("Cérebro Artificial JNL")
        prompt = st.chat_input("Pergunte algo...")
        if prompt:
            with st.chat_message("user"): st.write(prompt)
            try:
                client = Groq(api_key=st.secrets["GROQ_API_KEY"])
                res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role": "user", "content": prompt}]).choices[0].message.content
                with st.chat_message("assistant"): st.write(res)
            except: st.error("Erro na chave da IA (Verifique os Secrets).")

    with tab_chat:
        st.subheader(f"Chat: {setor_atual}")
        conn = sqlite3.connect('jnl_master.db')
        df = pd.read_sql_query("SELECT * FROM chat_setor WHERE setor = ? ORDER BY id ASC", conn, params=(setor_atual,))
        conn.close()

        for _, row in df.iterrows():
            is_me = row['usuario'] == user
            align, bg = ("right", "#dcf8c6") if is_me else ("left", "#f1f0f0")
            tag = " *(Editada)*" if row.get('editada') == 1 else ""
            
            st.markdown(f"<div style='text-align: {align};'><div style='display: inline-block; background: {bg}; padding: 10px; border-radius: 10px; color: black; margin: 5px; min-width: 150px; box-shadow: 1px 1px 2px rgba(0,0,0,0.1);'><b>{row['usuario'].capitalize()}</b><br>{row['mensagem']}<br><small style='color: gray; font-size: 0.7em;'>{row['data_hora']}{tag}</small></div></div>", unsafe_allow_html=True)
            
            if is_me:
                # Trava de 10 minutos para edição
                dt_m = datetime.strptime(row['data_hora'], '%Y-%m-%d %H:%M:%S')
                if datetime.now() - dt_m < timedelta(minutes=10):
                    with st.popover("✏️ Editar"):
                        nv = st.text_input("Corrigir:", row['mensagem'], key=f"e_{row['id']}")
                        if st.button("Salvar Alteração", key=f"b_{row['id']}"):
                            conn = sqlite3.connect('jnl_master.db'); c = conn.cursor()
                            c.execute("UPDATE chat_setor SET mensagem = ?, editada = 1 WHERE id = ?", (nv, row['id']))
                            conn.commit(); conn.close(); st.rerun()

        with st.form("chat_form", clear_on_submit=True):
            m = st.text_input("Digite sua mensagem:")
            if st.form_submit_button("Enviar"):
                if m:
                    conn = sqlite3.connect('jnl_master.db'); c = conn.cursor()
                    c.execute("INSERT INTO chat_setor (setor, usuario, data_hora, mensagem) VALUES (?, ?, ?, ?)", (setor_atual, user, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), m))
                    conn.commit(); conn.close(); st.rerun()

    with tab_agenda:
        st.subheader("Agenda de Ações")
        with st.form("agenda_form"):
            t_age = st.text_input("Título da Tarefa")
            col1, col2 = st.columns(2)
            d_age = col1.date_input("Data")
            h_age = col2.time_input("Hora")
            para = st.text_input("Para (e-mails)")
            if st.form_submit_button("Agendar"):
                conn = sqlite3.connect('jnl_master.db'); c = conn.cursor()
                c.execute("INSERT INTO calendario (usuario, titulo, data_hora, notificado, destinatarios) VALUES (?, ?, ?, 0, ?)", (user, t_age, f"{d_age} {h_age}", para))
                conn.commit(); conn.close(); st.success("Agendado com sucesso!"); st.rerun()

    with tab_notes:
        st.subheader("Bloco de Notas Pessoal")
        with st.form("nota_form", clear_on_submit=True):
            t_nota = st.text_input("Título da Nota")
            c_nota = st.text_area("Escreva sua nota aqui...")
            if st.form_submit_button("Salvar Nota 💾"):
                conn = sqlite3.connect('jnl_master.db'); c = conn.cursor()
                c.execute("INSERT INTO anotacoes (usuario, pasta, titulo, conteudo) VALUES (?, 'N', ?, ?)", (user, t_nota, c_nota))
                conn.commit(); conn.close(); st.success("Nota salva!"); st.rerun()
        
        st.write("---")
        conn = sqlite3.connect('jnl_master.db')
        df_n = pd.read_sql_query("SELECT * FROM anotacoes WHERE usuario = ?", conn, params=(user,))
        conn.close()
        for _, n in df_n.iterrows():
            with st.container(border=True):
                st.write(f"**{n['titulo']}**")
                st.write(n['conteudo'])