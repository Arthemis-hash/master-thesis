#!/usr/bin/env python3
"""
============================================================
PAGE RGPD - DROITS DES UTILISATEURS
============================================================
Interface Streamlit pour les droits RGPD:
- Article 15: Export des donnees
- Article 16: Rectification des donnees
- Article 17: Droit a l'oubli (suppression/anonymisation)
- Consentement RGPD

Accessible depuis: Mon Profil > Mes Donnees RGPD
"""

import streamlit as st
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from gdpr_anonymizer_sync import GDPRAnonymizer
from auth import get_current_user


st.set_page_config(
    page_title="Mes Donnees RGPD", page_icon="gdpr_shield", layout="wide"
)


def init_session_state():
    """Initialise les states de la session"""
    if "gdpr_data_exported" not in st.session_state:
        st.session_state.gdpr_data_exported = False
    if "gdpr_export_content" not in st.session_state:
        st.session_state.gdpr_export_content = None


def get_gdpr_manager() -> Optional[GDPRAnonymizer]:
    """Recupere le gestionnaire GDPR"""
    try:
        return GDPRAnonymizer()
    except Exception as e:
        st.error(f"Erreur connexion base de donnees: {e}")
        return None


def show_article_15_export(gdpr: GDPRAnonymizer, user_id: int):
    """Affiche la section Article 15 - Droit d'acces"""
    st.markdown("### Article 15 - Droit d'acces")
    st.markdown("""
    Conformement a l'**Article 15 du RGPD**, vous avez le droit d'obtenir une copie de 
    toutes vos donnees personnelles que nous traitons.
    """)

    with st.expander("Details des donnees exportees"):
        st.markdown("""
        Les donnees exportees incluent:
        - **Profil**: Email, prenom, nom, role, dates
        - **Sessions**: Historique des sessions actives
        - **Consentements**: Statut du consentement RGPD
        - **Historique**: Actions effectuees sur votre compte
        """)

    col1, col2 = st.columns([1, 2])

    with col1:
        if st.button(
            "Telecharger mes donnees", type="primary", use_container_width=True
        ):
            with st.spinner("Generation de l'export..."):
                try:
                    export_data = gdpr.export_user_data(user_id)

                    if export_data:
                        st.session_state.gdpr_export_content = json.dumps(
                            export_data, indent=2, default=str
                        )
                        st.session_state.gdpr_data_exported = True
                        st.success("Donnees exportees avec succes!")
                    else:
                        st.error("Erreur lors de l'export")
                except Exception as e:
                    st.error(f"Erreur: {e}")

    with col2:
        if st.session_state.gdpr_data_exported and st.session_state.gdpr_export_content:
            st.download_button(
                label="Sauvegarder le fichier JSON",
                data=st.session_state.gdpr_export_content,
                file_name=f"mes_donnees_rgpd_{datetime.now().strftime('%Y%m%d')}.json",
                mime="application/json",
                use_container_width=True,
            )


def show_article_16_rectification(gdpr: GDPRAnonymizer, user_id: int):
    """Affiche la section Article 16 - Droit de rectification"""
    st.markdown("### Article 16 - Droit de rectification")
    st.markdown("""
    Conformement a l'**Article 16 du RGPD**, vous avez le droit de faire rectifier 
    vos donnees personnelles inexactes.
    """)

    with st.form("gdpr_rectification_form"):
        col1, col2 = st.columns(2)

        with col1:
            new_first_name = st.text_input("Prenom", placeholder="Votre prenom")

        with col2:
            new_last_name = st.text_input("Nom", placeholder="Votre nom")

        new_email = st.text_input("Email", placeholder="votre@email.com")

        submit = st.form_submit_button("Mettre a jour", type="primary")

    if submit:
        if not new_first_name and not new_last_name and not new_email:
            st.warning("Veuillez modifier au moins un champ")
        else:
            with st.spinner("Mise a jour en cours..."):
                success, message = gdpr.update_user_data(
                    user_id=user_id,
                    first_name=new_first_name if new_first_name else None,
                    last_name=new_last_name if new_last_name else None,
                    email=new_email if new_email else None,
                )

            if success:
                st.success(f"{message}")
            else:
                st.error(f"{message}")


def show_article_17_deletion(gdpr: GDPRAnonymizer, user_id: int):
    """Affiche la section Article 17 - Droit a l'oubli"""
    st.markdown("### Article 17 - Droit a l'oubli")
    st.markdown("""
    Conformement a l'**Article 17 du RGPD**, vous avez le droit de demander la 
    suppression de vos donnees personnelles.
    """)

    st.warning("Attention: Cette action est irreversible!")

    tab1, tab2 = st.tabs(["Anonymisation (Recommande)", "Suppression complete"])

    with tab1:
        st.markdown("""
        **Option recommandee**: L'anonymisation irreversible conserve vos donnees 
        analytiques tout en rendant votre identite impossible a identifier.
        
        Vos donnees seront remplacees par un hash:
        - Nom -> `User_a3f5b9c1`
        - Email -> `anonymous_a3f5b9c1@deleted.local`
        """)

        if st.button("Anonymiser mon compte", type="primary"):
            confirm = st.checkbox("Je comprends que cette action est irreversible")

            if confirm:
                with st.spinner("Anonymisation en cours..."):
                    success, message = gdpr.anonymize_user(user_id)

                if success:
                    st.success(f"{message}")
                    st.warning("Vous allez etre deconnecte...")
                else:
                    st.error(f"{message}")
            else:
                st.info("Veuillez cocher la case de confirmation")

    with tab2:
        st.markdown("""
        **Suppression complete**: Cette option supprime DEFINITIVEMENT toutes vos donnees.
        
        Cette action est IRREVERSIBLE et aucune donnee ne pourra etre recuperee.
        """)

        st.error("Nous recommandons plutot l'anonymisation!")

        confirm_text = st.text_input(
            "Tapez 'SUPPRIMER' pour confirmer", type="password"
        )

        if st.button("Supprimer definitivement mon compte", type="primary"):
            if confirm_text == "SUPPRIMER":
                with st.spinner("Suppression en cours..."):
                    success, message = gdpr.delete_user_data(user_id, confirm=True)

                if success:
                    st.success(f"{message}")
                    st.warning("Vous allez etre deconnecte...")
                else:
                    st.error(f"{message}")
            else:
                st.error("Veuillez taper 'SUPPRIMER' pour confirmer")


def show_consent_management(gdpr: GDPRAnonymizer, user_id: int):
    """Affiche la gestion du consentement"""
    st.markdown("### Gestion du consentement")
    st.markdown("""
    Gerez vos preferences concernant le traitement de vos donnees personnelles.
    """)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Consentement au traitement des donnees**")
        consent_given = st.checkbox(
            "J'accepte que mes donnees personnelles soient traitees", value=True
        )

    with col2:
        if st.button("Enregistrer mes preferences", type="primary"):
            with st.spinner("Enregistrement..."):
                success, message = gdpr.record_consent(user_id, consent_given)

            if success:
                st.success(f"{message}")
            else:
                st.error(f"{message}")


def show_sessions_management(gdpr: GDPRAnonymizer, user_id: int):
    """Affiche la gestion des sessions"""
    st.markdown("### Gestion des sessions")
    st.markdown("Visualisez et gerez vos sessions actives.")

    try:
        export_data = gdpr.export_user_data(user_id)

        if export_data and export_data.get("sessions"):
            sessions = export_data["sessions"]

            st.write(f"**{len(sessions)} session(s) active(s)**")

            for i, session in enumerate(sessions, 1):
                with st.expander(f"Session #{i}"):
                    st.write(f"Creee: {session.get('created_at', 'N/A')}")
                    st.write(f"Expire: {session.get('expires_at', 'N/A')}")
                    st.write(
                        f"Derniere activite: {session.get('last_activity', 'N/A')}"
                    )
        else:
            st.info("Aucune session active")

    except Exception as e:
        st.error(f"Erreur: {e}")


def main():
    """Page principale RGPD"""
    init_session_state()

    st.markdown(
        """
    <style>
    .gdpr-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
        border-radius: 10px;
        color: white;
        margin-bottom: 2rem;
    }
    </style>
    """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="gdpr-header">', unsafe_allow_html=True)
    st.markdown("# Mes Donnees RGPD")
    st.markdown(
        "### Gestion de vos droits concernant la protection de vos donnees personnelles"
    )
    st.markdown("</div>", unsafe_allow_html=True)

    user = get_current_user()

    if not user:
        st.error("Vous devez etre connecte pour acceder a cette page")
        return

    gdpr = get_gdpr_manager()

    if not gdpr:
        st.error("Erreur de connexion a la base de donnees")
        return

    user_id = user.get("user_id")

    st.markdown("---")

    tabs = st.tabs(
        [
            "Export (Art. 15)",
            "Rectification (Art. 16)",
            "Suppression (Art. 17)",
            "Consentement",
            "Sessions",
        ]
    )

    with tabs[0]:
        show_article_15_export(gdpr, user_id)

    with tabs[1]:
        show_article_16_rectification(gdpr, user_id)

    with tabs[2]:
        show_article_17_deletion(gdpr, user_id)

    with tabs[3]:
        show_consent_management(gdpr, user_id)

    with tabs[4]:
        show_sessions_management(gdpr, user_id)

    st.markdown("---")
    st.caption("""
    Pour toute question concernant vos donnees personnelles, contactez notre Delegue 
    a la Protection des Donnees (DPO) a l'adresse: dpo@airquality.brussels
    
    Conformement au RGPD, vous avez le droit de porter plainte aupres de l'Autorite 
    de Protection des Donnees (APD) belge.
    """)


if __name__ == "__main__":
    main()
