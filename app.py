import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import datetime, timedelta
from groq import Groq

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="SISTEMA JNL", page_icon="🏢", layout="wide")
SENHA_MESTRA = "JNLDIRETORIA"

# --- CONEXÃO SUPABASE ---
@st.cache_resource
def get_supabase() -> Client:
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = get_supabase()

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

# --- ESTADO DO SISTEMA ---
if "autenticado" not in st.session_state: st.session_state["autenticado"] = False
if "setor" not in st.session_state: st.session_state["setor"] = None
if "mensagens_ia" not in st.session_state: st.session_state["mensagens_ia"] = []
if "admin_liberado" not in st.session_state: st.session_state["admin_liberado"] = False

# --- 1. TELA DE LOGIN ---
if not st.session_state["autenticado"]:
    st.title("🔒 CENTRO DE COMANDO JNL")
    u = st.text_input("Usuário:").lower()
    p = st.text_input("Senha:", type="password")
    if st.button("ACESSAR"):
        res = supabase.table("usuarios").select("*").eq("login", u).execute()
        if res.data and res.data[0]["senha"] == p:
            st.session_state.update({
                "autenticado": True, "user_slug": u, "user_nome": res.data[0]["nome"], "user_setores": res.data[0]["setores"]
            })
            st.rerun()
        else: st.error("Acesso Negado.")

# --- 2. SELEÇÃO DE SETORES ---
elif st.session_state["setor"] is None:
    st.title(f"🏢 {obter_saudacao()}! Bem-vindo, {st.session_state['user_nome']}.")
    setores_base = ["ADMINISTRATIVO", "FINANCEIRO", "FATURAMENTO", "VENDAS", "COMPRAS", "ESTOQUE", "SOLUÇÕES CORPORATIVAS", "PROJETOS/IMPORTAÇÃO", "RH", "GERAL"]
    permissoes = st.session_state["user_setores"]
    setores_visiveis = setores_base if permissoes == "ALL" else permissoes.split(",")
    if permissoes == "ALL": setores_visiveis.append("🔐 CONTROLE DE SENHAS")
    
    cols = st.columns(3)
    for i, s in enumerate(setores_visiveis):
        with cols[i % 3]:
            # LÓGICA CORRIGIDA: Apenas o botão de SENHAS fica vermelho (primary)
            tipo = "primary" if "SENHAS" in s else "secondary"
            if st.button(s, use_container_width=True, type=tipo):
                st.session_state["setor"] = s; st.rerun()

# --- 3. DASHBOARD PRINCIPAL ---
else:
    setor_atual = st.session_state["setor"]
    user = st.session_state["user_slug"]

    # --- CONTROLE DE SENHAS ---
    if setor_atual == "🔐 CONTROLE DE SENHAS":
        if not st.session_state["admin_liberado"]:
            st.title("🛡️ Cofre da Diretoria")
            sm = st.text_input("Senha Mestra:", type="password")
            if st.button("DESBLOQUEAR"):
                if sm == SENHA_MESTRA: st.session_state["admin_liberado"] = True; st.rerun()
                else: st.error("Incorreta.")
            if st.button("⬅️ VOLTAR"): st.session_state["setor"] = None; st.rerun()
        else:
            st.title("🔐 Gestão de Funcionários")
            if st.button("⬅️ TRANCAR E VOLTAR"): st.session_state["admin_liberado"] = False; st.session_state["setor"] = None; st.rerun()
            res_u = supabase.table("usuarios").select("login, nome").execute()
            df_u = pd.DataFrame(res_u.data)
            with st.form("f_senha"):
                u_sel = st.selectbox("Usuário:", df_u['login'].tolist())
                n_s = st.text_input("Nova Senha:", type="password")
                if st.form_submit_button("Atualizar"):
                    supabase.table("usuarios").update({"senha": n_s}).eq("login", u_sel).execute()
                    st.success("Senha atualizada!")

    # --- SETORES OPERACIONAIS ---
    else:
        with st.sidebar:
            st.header(f"📍 {setor_atual}")
            if st.button("⬅️ TROCAR SETOR"): st.session_state["setor"] = None; st.rerun()
            st.write("---")
            st.subheader("⚙️ PERFIL IA")
            nova_o = st.text_area("Nova Ordem:", placeholder="Ex: Sempre me chame de Comandante.")
            if st.button("Gravar Ordem"):
                if nova_o:
                    supabase.table("ordens_ia").insert({"usuario": user, "ordem": nova_o}).execute()
                    st.rerun()
            ordens = supabase.table("ordens_ia").select("*").eq("usuario", user).order("id", desc=False).execute()
            for o in ordens.data:
                with st.container(border=True):
                    st.caption(o['ordem'])
                    if st.button("🗑️", key=f"del_o_{o['id']}"):
                        supabase.table("ordens_ia").delete().eq("id", o['id']).execute(); st.rerun()

        tab_ia, tab_chat, tab_age, tab_note = st.tabs(["💬 IA JNL", "👥 CHAT", "📅 AGENDA", "📝 NOTAS"])

        with tab_ia:
            st.subheader("Assistente Inteligente JNL")
            for msg in st.session_state["mensagens_ia"]:
                with st.chat_message(msg["role"]): st.markdown(msg["content"])
            if prompt := st.chat_input("Comande a IA..."):
                st.session_state["mensagens_ia"].append({"role": "user", "content": prompt})
                with st.chat_message("user"): st.markdown(prompt)
                with st.chat_message("assistant"):
                    res_o = supabase.table("ordens_ia").select("ordem").eq("usuario", user).order("id", desc=False).execute()
                    regras = "\n".join([x['ordem'] for x in res_o.data])
                    contexto = busca_web(prompt) if any(x in prompt.lower() for x in ["hoje", "dólar", "agora"]) else ""
                    ctx = f"Você é a IA da JNL. REGRAS: {regras}. WEB: {contexto}"
                    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
                    resp = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role": "system", "content": ctx}] + st.session_state["mensagens_ia"]).choices[0].message.content
                    st.markdown(resp); st.session_state["mensagens_ia"].append({"role": "assistant", "content": resp})

        with tab_chat:
            res_c = supabase.table("chat_setor").select("*").eq("setor", setor_atual).order("id", desc=False).execute()
            for m in res_c.data:
                is_me = m['usuario'] == user
                align, bg = ("right", "#dcf8c6") if is_me else ("left", "#f1f0f0")
                if m['apagada'] == 1: conteudo = "<i>🚫 Mensagem apagada</i>"; cor = "#888"
                else: conteudo = f"{m['mensagem']} {'*(Editada)*' if m['editada'] == 1 else ''}"; cor = "black"
                
                st.markdown(f"<div style='text-align: {align};'><div style='display: inline-block; background: {bg}; padding: 10px; border-radius: 10px; color: {cor}; margin: 5px; min-width: 150px; text-align: left;'><b>{m['usuario'].upper()}</b><br>{conteudo}<br><small>{m['data_hora']}</small></div></div>", unsafe_allow_html=True)
                
                if is_me and m['apagada'] == 0:
                    ts = datetime.fromisoformat(m['timestamp_real'].replace('Z', '+00:00'))
                    if (datetime.now(ts.tzinfo) - ts).total_seconds() / 60 <= 20:
                        with st.popover("⚙️"):
                            nv = st.text_input("Editar:", m['mensagem'], key=f"edit_{m['id']}")
                            if st.button("Salvar", key=f"s_{m['id']}"):
                                supabase.table("chat_setor").update({"mensagem": nv, "editada": 1}).eq("id", m['id']).execute(); st.rerun()
                            if st.button("Apagar", key=f"a_{m['id']}"):
                                supabase.table("chat_setor").update({"apagada": 1}).eq("id", m['id']).execute(); st.rerun()

            with st.form("f_chat", clear_on_submit=True):
                m_txt = st.text_input("Mensagem:", placeholder="Escreva e aperte Enter ou Enviar...")
                if st.form_submit_button("Enviar"):
                    if m_txt:
                        agora = get_now_br()
                        supabase.table("chat_setor").insert({"setor": setor_atual, "usuario": user, "data_hora": agora.strftime('%d/%m %H:%M'), "mensagem": m_txt, "timestamp_real": agora.isoformat()}).execute(); st.rerun()

        with tab_age:
            with st.form("f_age", clear_on_submit=True):
                t = st.text_input("Tarefa")
                c1, c2, c3 = st.columns([2,1,1])
                d = c1.date_input("Data", format="DD/MM/YYYY")
                h = c2.selectbox("Hora", [f"{i:02d}" for i in range(24)])
                mi = c3.selectbox("Min", ["00", "15", "30", "45"])
                dest = st.text_input("E-mail")
                if st.form_submit_button("Agendar"):
                    supabase.table("calendario").insert({"usuario": user, "titulo": t, "data_hora": f"{d} {h}:{mi}:00", "destinatarios": dest}).execute(); st.rerun()
            res_a = supabase.table("calendario").select("*").eq("usuario", user).execute()
            for r in res_a.data:
                dt = datetime.fromisoformat(r['data_hora']).strftime('%d/%m/%Y %H:%M')
                with st.container(border=True):
                    st.write(f"📌 {r['titulo']} | 📅 {dt}")
                    if st.button("🗑️ Remover", key=f"da_{r['id']}"):
                        supabase.table("calendario").delete().eq("id", r['id']).execute(); st.rerun()

        with tab_note:
            st.subheader("Anotações Pessoais")
            with st.form("f_not", clear_on_submit=True):
                tn = st.text_input("Título")
                cn = st.text_area("Conteúdo")
                if st.form_submit_button("Salvar Nota"):
                    supabase.table("anotacoes").insert({"usuario": user, "titulo": tn, "conteudo": cn}).execute(); st.rerun()
            res_n = supabase.table("anotacoes").select("*").eq("usuario", user).execute()
            for n in res_n.data:
                with st.container(border=True):
                    st.write(f"**{n['titulo']}**")
                    st.write(n['conteudo'])
                    if st.button("🗑️", key=f"dn_{n['id']}"):
                        supabase.table("anotacoes").delete().eq("id", n['id']).execute(); st.rerun()