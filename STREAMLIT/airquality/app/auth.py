#!/usr/bin/env python3
"""
Module d'authentification Streamlit - Système JWT avec DB
"""

import streamlit as st
from datetime import datetime, timedelta
import logging
from typing import Optional
import time

from auth_manager import AuthManager
# extra-streamlit-components REMOVED - causing 'Invalid image width: 0' error
# Session persistence now handled purely through Redis

logger = logging.getLogger(__name__)
import base64
import os


# === CSS (NOUVEAU DESIGN PREMIUM) ===
def get_base64_image(image_path):
    """Convertit image en base64"""
    try:
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    except Exception as e:
        logger.error(f"❌ Erreur lecture image background: {e}")
        return ""


def inject_login_styles():
    """Injecte styles CSS - Isolation complète et Design Premium"""

    # Calculer chemin absolu image
    base_path = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    img_path = os.path.join(base_path, "Pictures", "login page", "test.png")

    # Fallback si image non trouvée
    bg_style = "background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);"

    if os.path.exists(img_path):
        b64_img = get_base64_image(img_path)
        if b64_img:
            bg_style = f'background-image: url("data:image/png;base64,{b64_img}");'

    # Dynamic style for background
    bg_css = f"""
    .stApp {{
        {bg_style}
        background-size: cover;
        background-position: center;
        background-repeat: no-repeat;
        background-attachment: fixed;
    }}
    """

    # Static style (no f-string needed)
    static_css = """
        <style>
        /* Masquage TOTAL de tous les éléments Streamlit */
        [data-testid="stSidebar"],
        [data-testid="stSidebarNav"],
        [data-testid="stHeader"],
        [data-testid="stDecoration"],
        [data-testid="stToolbar"],
        [data-testid="stStatusWidget"],
        #MainMenu, footer, header,
        .stDeployButton {
            display: none !important;
            visibility: hidden !important;
            width: 0 !important;
            height: 0 !important;
            opacity: 0 !important;
        }
        
        /* Reset TOTAL du container */
        .main, 
        .block-container, 
        [data-testid="stVerticalBlock"],
        [data-testid="stAppViewContainer"],
        section[data-testid="stMain"] {
            padding: 0 !important;
            margin: 0 !important;
            max-width: 100% !important;
            width: 100% !important;
        }
        
        .block-container {
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            min-height: 100vh !important;
            padding: 2rem !important;
        }
        
        /* LOGIN BOX - CLEAN & PROFESSIONAL */
        .login-container {
            background: rgba(255, 255, 255, 0.15);
            backdrop-filter: blur(10px);
            -webkit-backdrop-filter: blur(10px);
            padding: 2rem 1.8rem;
            border-radius: 16px;
            border: 1px solid rgba(255, 255, 255, 0.2);
            box-shadow: 0 20px 60px rgba(0,0,0,0.4);
            width: 100%;
            max-width: 360px !important;
            margin: 0 auto;
        }
        
        .login-logo {
            text-align: center;
            margin-bottom: 1rem;
            filter: drop-shadow(0 4px 6px rgba(0,0,0,0.1));
        }
        
        .login-logo img {
            max-width: 150px;
            height: auto;
        }
        
        .login-title {
            text-align: center;
            font-size: 1.8rem;
            font-weight: 800;
            color: #ffffff !important;
            text-shadow: 0 2px 10px rgba(0,0,0,0.3);
            margin-bottom: 0.5rem;
            font-family: 'Segoe UI', system-ui, sans-serif;
        }
        
        .login-subtitle {
            text-align: center;
            font-size: 0.9rem;
            color: rgba(255, 255, 255, 0.9) !important;
            margin-bottom: 2rem;
            font-weight: 500;
        }
        
        /* INPUTS MODERNES - COMPACTS */
        .login-container .stTextInput > label {
            font-size: 0.85rem !important;
            font-weight: 600 !important;
            color: #ffffff !important;
            margin-bottom: 0.4rem !important;
            text-shadow: 0 1px 3px rgba(0,0,0,0.2);
        }
        
        .login-container .stTextInput input {
            border: 1px solid rgba(255, 255, 255, 0.3) !important;
            border-radius: 8px !important;
            padding: 0.5rem 0.9rem !important;
            font-size: 0.9rem !important;
            height: 36px !important;
            background: rgba(255, 255, 255, 0.2) !important;
            color: #ffffff !important;
            caret-color: #ffffff !important;
            transition: all 0.2s ease !important;
        }
        
        .login-container .stTextInput input::placeholder {
            color: rgba(255, 255, 255, 0.5) !important;
        }
        
        .login-container .stTextInput input:focus {
            border-color: rgba(255, 255, 255, 0.6) !important;
            box-shadow: 0 0 0 3px rgba(255, 255, 255, 0.1) !important;
            background: rgba(255, 255, 255, 0.25) !important;
            transform: translateY(-1px);
        }
        
        /* BOUTON PREMIUM - COMPACT */
        .login-container .stButton button {
            width: 100% !important;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
            color: white !important;
            border: none !important;
            border-radius: 8px !important;
            padding: 0.6rem !important;
            font-weight: 700 !important;
            font-size: 0.95rem !important;
            height: 40px !important;
            margin-top: 0.8rem !important;
            box-shadow: 0 4px 15px rgba(118, 75, 162, 0.4) !important;
            transition: all 0.3s ease !important;
        }
        
        .login-container .stButton button:hover {
            transform: translateY(-2px) !important;
            box-shadow: 0 8px 25px rgba(118, 75, 162, 0.5) !important;
            filter: brightness(110%);
        }

        .login-container .stButton button:active {
            transform: translateY(0) !important;
        }
        
        /* EXPANDER FORGOT PASSWORD - GLASSMORPHISM */
        .login-container .streamlit-expanderHeader {
            background-color: rgba(255, 255, 255, 0.1) !important;
            color: #ffffff !important;
            font-weight: 600 !important;
            font-size: 0.85rem !important;
            border: 1px solid rgba(255, 255, 255, 0.2) !important;
            border-radius: 8px !important;
        }
        
        .login-container .streamlit-expanderContent {
            background-color: rgba(255, 255, 255, 0.1) !important;
            border-radius: 8px !important;
            padding: 1rem !important;
            border: 1px solid rgba(255, 255, 255, 0.2) !important;
        }
        
        .login-container .streamlit-expanderContent p,
        .login-container .streamlit-expanderContent .stMarkdown,
        .login-container .streamlit-expanderContent label {
            color: #ffffff !important;
        }
        
        /* Divider */
        hr {
            margin: 1.5rem 0 !important;
            border-color: rgba(226, 232, 240, 0.8) !important;
        }
        </style>
    """

    # Injection: Dynamic BG inside style block not possible directly if we static first
    # So we inject dynamic CSS separately or concat

    st.markdown(f"<style>{bg_css}</style>", unsafe_allow_html=True)
    st.markdown(static_css, unsafe_allow_html=True)


def get_cookie_manager():
    """CookieManager disabled - causes image width error"""
    return None


def init_session():
    """Initialise session state"""
    defaults = {
        "authenticated": False,
        "user_data": None,
        "jwt_token": None,
        "last_refresh": None,
        "show_create_user": False,
        "cleanup_done": False,
        "reset_mode": False,  # Nouveau state pour reset password
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


def show_change_password_ui():
    """Affiche le formulaire de changement de mot de passe"""
    st.markdown("### 🔐 Changer le mot de passe")

    with st.form("change_password_form"):
        old_pass = st.text_input("Ancien mot de passe", type="password")
        new_pass = st.text_input("Nouveau mot de passe", type="password")
        confirm_pass = st.text_input(
            "Confirmer le nouveau mot de passe", type="password"
        )

        submit = st.form_submit_button("Mettre à jour")

    if submit:
        if not old_pass or not new_pass:
            st.error("⚠️ Tous les champs sont requis")
        elif new_pass != confirm_pass:
            st.error("❌ Les mots de passe ne correspondent pas")
        elif len(new_pass) < 8:
            st.warning("⚠️ Le mot de passe doit contenir au moins 8 caractères")
        else:
            auth = AuthManager()
            user = get_current_user()

            with st.spinner("Mise à jour du mot de passe..."):
                success, msg = auth.change_password(user["email"], old_pass, new_pass)

            if success:
                st.success(f"✅ {msg}")
                time.sleep(1)
                st.rerun()
            else:
                st.error(f"❌ {msg}")


def check_token_refresh():
    """Rafraîchit token si nécessaire (30min)"""
    if not st.session_state.authenticated or not st.session_state.jwt_token:
        return

    last_refresh = st.session_state.get("last_refresh")
    if not last_refresh:
        st.session_state.last_refresh = datetime.now()
        return

    # Rafraîchir si > 25 minutes (marge sécurité)
    if datetime.now() - last_refresh > timedelta(minutes=25):
        auth = AuthManager()
        result = auth.refresh_token(st.session_state.jwt_token)

        if result:
            new_token, expires_at = result
            st.session_state.jwt_token = new_token
            st.session_state.last_refresh = datetime.now()
            logger.info("🔄 Token auto-rafraîchi")
        else:
            # Token invalide, forcer déconnexion
            logout()
            st.warning("⏰ Session expirée, reconnectez-vous")
            st.rerun()


def logout():
    """Déconnexion avec nettoyage complet"""
    if st.session_state.jwt_token:
        auth = AuthManager()
        cm = get_cookie_manager()
        auth.logout(st.session_state.jwt_token, cookie_manager=cm)

    # Nettoyage TOTAL du session_state
    for key in list(st.session_state.keys()):
        del st.session_state[key]

    logger.info("🚪 Déconnexion + nettoyage session_state")

    # Force rerun complet
    st.rerun()


def login_page():
    """Page login modernisée avec Glassmorphism et Reset Password"""
    inject_login_styles()
    auth = AuthManager()

    # Importation d'image pour PIL
    from PIL import Image
    import os

    st.markdown('<div class="login-container">', unsafe_allow_html=True)

    # Afficher le logo ULB au lieu de l'emoji
    try:
        base_path = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        logo_path = os.path.join(base_path, "Pictures", "login page", "logo_ULB.png")

        if os.path.exists(logo_path):
            # Convertir l'image en base64 pour l'afficher dans HTML
            logo_b64 = get_base64_image(logo_path)
            st.markdown(
                f'<div class="login-logo"><img src="data:image/png;base64,{logo_b64}" alt="ULB Logo"></div>',
                unsafe_allow_html=True,
            )
        else:
            # Fallback emoji si image non trouvée
            st.markdown('<div class="login-logo">🌍</div>', unsafe_allow_html=True)
            logger.warning(f"Logo ULB non trouvé: {logo_path}")
    except Exception as e:
        logger.error(f"Erreur chargement logo ULB: {e}")
        st.markdown('<div class="login-logo">🌍</div>', unsafe_allow_html=True)

    st.markdown(
        '<div class="login-title">Air Quality App</div>', unsafe_allow_html=True
    )
    st.markdown(
        '<div class="login-subtitle">Connectez-vous à votre espace sécurisé</div>',
        unsafe_allow_html=True,
    )

    # === LOGIN FORM ===
    with st.form("login_form"):
        email = st.text_input("Adresse Email", placeholder="exemple@domaine.com")
        password = st.text_input("Mot de passe", type="password")
        submit = st.form_submit_button("Se connecter")

    if submit:
        if not email or not password:
            st.error("⚠️ Veuillez remplir tous les champs")
        else:
            with st.spinner("Connexion en cours..."):
                time.sleep(0.5)  # Petit délai pour UX
                # Pass cookie manager explicitly
                cm = get_cookie_manager()
                success, user_data = auth.login(email, password, cookie_manager=cm)

            if success:
                st.session_state.authenticated = True
                st.session_state.user_data = user_data
                st.session_state.jwt_token = user_data["token"]
                st.session_state.last_refresh = datetime.now()

                st.success(f"✅ Ravi de vous revoir !")
                st.balloons()
                time.sleep(0.5)
                st.rerun()
            else:
                st.error("❌ Email ou mot de passe incorrect")

    st.markdown(
        "</div>", unsafe_allow_html=True
    )  # Fin du container principal pour le form

    # === MOT DE PASSE OUBLIÉ ===
    # On le met hors du container principal pour style différent ou dedans,
    # ici je simule qu'il est "attaché" visuellement

    with st.expander("🔒 Mot de passe oublié ?"):
        st.info("Entrez votre email ci-dessous pour recevoir un nouveau mot de passe.")

        # Image temporairement désactivée pour compatibilité
        # try:
        #     base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        #     img_path = os.path.join(base_path, "Pictures", "login page", "test.png")
        #
        #     if os.path.exists(img_path):
        #         st.image(img_path, use_column_width=True, caption="Récupération sécurisée")
        #     else:
        #         st.warning(f"Image introuvable: {img_path}")
        # except Exception as e:
        #     logger.error(f"Erreur chargement image: {e}")

        with st.form("reset_password_form"):
            reset_email = st.text_input("Email de récupération")
            submit_reset = st.form_submit_button("🔄 Réinitialiser mon mot de passe")

        if submit_reset:
            if not reset_email:
                st.warning("⚠️ Veuillez entrer votre email")
            else:
                with st.spinner("Traitement de la demande..."):
                    success, msg = auth.reset_password(reset_email)

                if success:
                    st.success(f"✅ {msg}")
                else:
                    st.error(f"❌ {msg}")

    # Compte test discret
    st.markdown(
        """
        <div style="text-align: center; margin-top: 2rem; opacity: 0.6;">
            <small>🔐 Compte démo : <code>test@test.com</code> / <code>test</code></small>
        </div>
    """,
        unsafe_allow_html=True,
    )


def show_admin_panel():
    """Panel admin pour gérer les utilisateurs"""
    st.markdown(
        """
        <div style="text-align: center; 
                    padding: 0.8rem 0; 
                    border-bottom: 2px solid #e2e8f0;
                    margin-bottom: 1rem;">
            <h3 style="margin: 0; 
                       color: #dc2626; 
                       font-size: 0.95rem;
                       font-weight: 700;
                       letter-spacing: 0.5px;">
                🛡️ ADMIN PANEL
            </h3>
        </div>
    """,
        unsafe_allow_html=True,
    )

    # Bouton pour ouvrir le dialogue de création
    if st.button("➕ Créer un utilisateur", width="stretch", type="primary"):
        st.session_state.show_create_user = True

    # Dialogue de création d'utilisateur
    if st.session_state.get("show_create_user", False):
        st.markdown(
            """
            <div style="background: linear-gradient(135deg, #f0f9ff, #e0f2fe); 
                        padding: 1rem; 
                        border-radius: 10px; 
                        border: 2px solid #0ea5e9;
                        margin: 1rem 0;">
        """,
            unsafe_allow_html=True,
        )

        st.markdown("**➕ Nouveau compte**")

        with st.form("create_user_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                new_first_name = st.text_input(
                    "� Prénom", placeholder="Jean", key="admin_new_first_name"
                )
            with col2:
                new_last_name = st.text_input(
                    "� Nom", placeholder="Dupont", key="admin_new_last_name"
                )

            new_email = st.text_input(
                "📧 Email", placeholder="jean.dupont@exemple.com", key="admin_new_email"
            )
            new_role = st.selectbox("�️ Rôle", ["user", "admin"], key="admin_new_role")

            st.info(
                "🔐 Un mot de passe sécurisé sera généré automatiquement et envoyé par email"
            )

            col1, col2 = st.columns(2)
            with col1:
                submit = st.form_submit_button(
                    "✅ Créer & Envoyer", width="stretch", type="primary"
                )
            with col2:
                cancel = st.form_submit_button("❌ Annuler", width="stretch")

        if submit:
            if not new_email or not new_first_name or not new_last_name:
                st.error("⚠️ Tous les champs sont requis")
            else:
                auth = AuthManager()

                with st.spinner("Création du compte et envoi de l'email..."):
                    success, error, password = auth.register(
                        new_email,
                        new_first_name,
                        new_last_name,
                        role=new_role,
                        send_email=True,
                    )

                if success:
                    st.success(f"✅ Compte créé pour {new_first_name} {new_last_name}")
                    st.info(f"📧 Email envoyé à {new_email}")

                    # Afficher le mot de passe généré (au cas où l'email échoue)
                    with st.expander(
                        "🔑 Mot de passe généré (à communiquer si l'email n'arrive pas)"
                    ):
                        st.code(password, language=None)
                        st.caption(
                            "⚠️ Conservez ce mot de passe en lieu sûr jusqu'à confirmation de réception de l'email"
                        )

                    st.session_state.show_create_user = False
                    time.sleep(2)
                    st.rerun()
                else:
                    st.error(f"❌ {error}")

        if cancel:
            st.session_state.show_create_user = False
            st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)

    st.divider()


def show_user_sidebar():
    """Sidebar utilisateur optimisée pour le dashboard"""
    with st.sidebar:
        # Titre sidebar
        st.markdown(
            """
            <div style="text-align: center; 
                        padding: 0.8rem 0; 
                        border-bottom: 2px solid #e2e8f0;
                        margin-bottom: 1rem;">
                <h3 style="margin: 0; 
                           color: #2d3748; 
                           font-size: 1rem;
                           font-weight: 700;
                           letter-spacing: 0.5px;">
                    👤 PROFIL USER
                </h3>
            </div>
        """,
            unsafe_allow_html=True,
        )

        user = st.session_state.user_data
        role = user.get("role", "user")

        role_config = {
            "admin": {
                "color": "#dc2626",
                "bg": "linear-gradient(135deg, #fee2e2, #fecaca)",
            },
            "user": {
                "color": "#059669",
                "bg": "linear-gradient(135deg, #d1fae5, #a7f3d0)",
            },
        }
        config = role_config.get(role, role_config["user"])

        # Card utilisateur compact
        full_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
        display_name = full_name if full_name else user["email"]

        st.markdown(
            f"""
            <div style="background: {config["bg"]}; 
                        padding: 1rem; 
                        border-radius: 10px; 
                        border-left: 4px solid {config["color"]};
                        margin-bottom: 1rem;">
                <div style="margin-bottom: 0.6rem;">
                    <div style="font-size: 0.9rem; 
                                font-weight: 700; 
                                color: #1a202c;
                                margin-bottom: 0.3rem;">
                        {display_name}
                    </div>
                    <div style="font-size: 0.75rem; 
                                color: #4a5568;
                                overflow: hidden;
                                text-overflow: ellipsis;
                                white-space: nowrap;">
                        {user["email"]}
                    </div>
                </div>
                <div style="text-align: center;">
                    <span style="display: inline-block;
                                background: {config["color"]}; 
                                color: white;
                                padding: 0.2rem 0.8rem; 
                                border-radius: 12px;
                                font-size: 0.7rem;
                                font-weight: 700;
                                letter-spacing: 0.5px;">
                        {role.upper()}
                    </span>
                </div>
            </div>
        """,
            unsafe_allow_html=True,
        )

        # Bouton déconnexion
        if st.button("🚪 Déconnexion", width="stretch", type="secondary"):
            logout()
            st.rerun()

        st.divider()

        # Section Changer Mot de passe
        with st.expander("🔑 Sécurité"):
            show_change_password_ui()

        st.divider()

        # Section RGPD - Mes données personnelles
        with st.expander("🛡️ Mes données RGPD"):
            st.markdown("""
            Gérez vos droits concernant la protection de vos données personnelles:
            """)
            if st.button("Ouvrir la page RGPD", use_container_width=True):
                st.markdown(
                    "<script>window.location.href='/gdpr'</script>",
                    unsafe_allow_html=True,
                )
                st.switch_page("gdpr_ui.py")

        st.divider()

        # Section Admin - Gestion des utilisateurs
        if is_admin():
            show_admin_panel()


def require_auth():
    """Protection authentification"""
    init_session()

    # Nettoyage automatique au démarrage de l'app
    if "cleanup_done" not in st.session_state:
        auth = AuthManager()
        auth._cleanup_sessions()
        st.session_state.cleanup_done = True

    # --- Check Cookie for Persistence ---
    if not st.session_state.authenticated:
        try:
            # Récupérer cookie manager singleton
            cookie_manager = get_cookie_manager()
            if not cookie_manager:
                cookie_token = None
            else:
                cookie_token = cookie_manager.get("jwt_token")

            if cookie_token:
                logger.info("🍪 Token trouvé dans cookies, validation...")
                auth = AuthManager()
                valid, user_data = auth.verify_session(cookie_token)

                if valid and user_data:
                    st.session_state.authenticated = True
                    st.session_state.user_data = user_data
                    st.session_state.jwt_token = cookie_token
                    st.session_state.last_refresh = datetime.now()
                    logger.info(
                        f"✅ Session restaurée depuis cookie: {user_data['email']}"
                    )
                    st.rerun()
        except Exception as e:
            logger.warning(f"⚠️ Erreur lecture cookies: {e}")

    # Vérifier token
    if st.session_state.authenticated and st.session_state.jwt_token:
        auth = AuthManager()
        valid, user_data = auth.verify_session(st.session_state.jwt_token)

        if not valid:
            logout()
            st.warning("⏰ Session expirée")
            st.stop()

        # Rafraîchir si nécessaire
        check_token_refresh()

    if not st.session_state.authenticated:
        login_page()
        st.stop()

    show_user_sidebar()


def get_current_user() -> dict:
    """Retourne user connecté"""
    return st.session_state.user_data if st.session_state.authenticated else {}


def is_admin() -> bool:
    """Vérifie si admin"""
    user = get_current_user()
    return user.get("role") == "admin"
