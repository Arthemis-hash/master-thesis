#!/usr/bin/env python3
"""
Service d'envoi d'emails avec SMTP (Gmail)
"""

import os
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()

logger = logging.getLogger(__name__)


class EmailService:
    """Gestionnaire d'envoi d'emails via SMTP Gmail"""

    def __init__(self):
        self.smtp_host = os.getenv('SMTP_HOST', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', 587))
        self.smtp_secure = os.getenv('SMTP_SECURE', 'false').lower() == 'true'
        self.smtp_user = os.getenv('SMTP_USER')
        self.smtp_password = os.getenv('SMTP_PASSWORD')
        self.sender_email = os.getenv('SMTP_FROM_EMAIL', self.smtp_user)
        self.sender_name = os.getenv('SMTP_FROM_NAME', 'Air Quality Application')

        # Debug configuration
        logger.info("🔧 Configuration SMTP:")
        logger.info(f"   Host: {self.smtp_host}")
        logger.info(f"   Port: {self.smtp_port}")
        logger.info(f"   User: {self.smtp_user}")
        logger.info(f"   Sender Email: {self.sender_email}")
        logger.info(f"   Sender Name: {self.sender_name}")

        if not self.smtp_user or not self.smtp_password:
            logger.error("❌ Identifiants SMTP manquants dans .env - L'envoi d'emails ne fonctionnera pas")
            logger.error("   Ajoutez SMTP_USER et SMTP_PASSWORD dans le fichier .env")
        else:
            logger.info("✅ Configuration SMTP chargée avec succès")

    def send_welcome_email(self, recipient_email: str, first_name: str, last_name: str, password: str) -> bool:
        """
        Envoie email de bienvenue avec mot de passe temporaire

        Args:
            recipient_email: Email du destinataire
            first_name: Prénom
            last_name: Nom
            password: Mot de passe généré

        Returns:
            bool: True si envoi réussi
        """
        logger.info("="*60)
        logger.info("📧 ENVOI EMAIL - DÉBUT")
        logger.info(f"   Destinataire: {recipient_email}")
        logger.info(f"   Nom: {first_name} {last_name}")
        logger.info(f"   Expéditeur: {self.sender_email}")

        if not self.smtp_user or not self.smtp_password:
            logger.error("❌ Configuration SMTP manquante - impossible d'envoyer l'email")
            logger.info("="*60)
            return False

        try:
            # Créer le message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = "Bienvenue sur Air Quality Application"
            msg['From'] = f"{self.sender_name} <{self.sender_email}>"
            msg['To'] = f"{first_name} {last_name} <{recipient_email}>"

            # Contenu texte
            text_content = self._get_text_content(first_name, last_name, recipient_email, password)
            # Contenu HTML
            html_content = self._get_html_content(first_name, last_name, recipient_email, password)

            # Attacher les deux versions
            part1 = MIMEText(text_content, 'plain', 'utf-8')
            part2 = MIMEText(html_content, 'html', 'utf-8')

            msg.attach(part1)
            msg.attach(part2)

            # Connexion au serveur SMTP
            logger.info(f"📤 Connexion au serveur SMTP {self.smtp_host}:{self.smtp_port}...")

            if self.smtp_secure or self.smtp_port == 465:
                # SSL
                server = smtplib.SMTP_SSL(self.smtp_host, self.smtp_port)
                logger.info("🔒 Connexion SSL établie")
            else:
                # TLS (port 587)
                server = smtplib.SMTP(self.smtp_host, self.smtp_port)
                server.ehlo()
                server.starttls()
                server.ehlo()
                logger.info("🔒 Connexion TLS établie")

            # Authentification
            logger.info("🔑 Authentification...")
            server.login(self.smtp_user, self.smtp_password)
            logger.info("✅ Authentification réussie")

            # Envoi
            logger.info("📨 Envoi de l'email...")
            server.send_message(msg)
            server.quit()

            logger.info("✅ Email envoyé avec succès!")
            logger.info("="*60)
            return True

        except smtplib.SMTPAuthenticationError as e:
            logger.error("❌ ERREUR D'AUTHENTIFICATION SMTP")
            logger.error(f"   Code: {e.smtp_code}")
            logger.error(f"   Message: {e.smtp_error.decode() if hasattr(e.smtp_error, 'decode') else e.smtp_error}")
            logger.error("   Vérifiez SMTP_USER et SMTP_PASSWORD dans .env")
            logger.error("   Pour Gmail, utilisez un mot de passe d'application: https://myaccount.google.com/apppasswords")
            logger.info("="*60)
            return False

        except smtplib.SMTPRecipientsRefused as e:
            logger.error("❌ DESTINATAIRE REFUSÉ")
            logger.error(f"   Email: {recipient_email}")
            logger.error(f"   Raison: {e.recipients}")
            logger.info("="*60)
            return False

        except smtplib.SMTPException as e:
            logger.error("❌ ERREUR SMTP")
            logger.error(f"   Type: {type(e).__name__}")
            logger.error(f"   Message: {str(e)}")
            logger.info("="*60)
            return False

        except Exception as e:
            logger.error("❌ EXCEPTION lors de l'envoi email")
            logger.error(f"   Type: {type(e).__name__}")
            logger.error(f"   Message: {str(e)}")

            # Stack trace complète pour debug
            import traceback
            logger.error(f"   Traceback:\n{traceback.format_exc()}")

            logger.info("="*60)
            return False

    def _get_text_content(self, first_name: str, last_name: str, email: str, password: str) -> str:
        """Contenu texte de l'email"""
        return f"""
Bonjour {first_name} {last_name},

Votre compte Air Quality Application a été créé avec succès !

Voici vos identifiants de connexion :
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Email : {email}
Mot de passe : {password}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️ IMPORTANT :
- Ce mot de passe est temporaire
- Nous vous recommandons de le changer après votre première connexion
- Ne partagez jamais vos identifiants

Connectez-vous dès maintenant pour accéder à l'application.

Cordialement,
L'équipe Air Quality Application
        """.strip()

    def _get_html_content(self, first_name: str, last_name: str, email: str, password: str) -> str:
        """Contenu HTML de l'email"""
        return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f5f7fa;">
    <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #f5f7fa; padding: 40px 20px;">
        <tr>
            <td align="center">
                <table width="600" cellpadding="0" cellspacing="0" style="background-color: white; border-radius: 16px; box-shadow: 0 4px 20px rgba(0,0,0,0.08); overflow: hidden;">

                    <!-- Header -->
                    <tr>
                        <td style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 40px 30px; text-align: center;">
                            <h1 style="margin: 0; color: white; font-size: 28px; font-weight: 700;">
                                🌍 Air Quality Application
                            </h1>
                        </td>
                    </tr>

                    <!-- Body -->
                    <tr>
                        <td style="padding: 40px 30px;">
                            <h2 style="margin: 0 0 20px 0; color: #1a202c; font-size: 22px; font-weight: 600;">
                                Bonjour {first_name} {last_name},
                            </h2>

                            <p style="margin: 0 0 20px 0; color: #4a5568; font-size: 16px; line-height: 1.6;">
                                Votre compte a été créé avec succès ! Vous pouvez dès maintenant accéder à l'application avec vos identifiants.
                            </p>

                            <!-- Credentials Box -->
                            <table width="100%" cellpadding="0" cellspacing="0" style="background: linear-gradient(135deg, #f0f9ff, #e0f2fe); border-radius: 12px; border-left: 4px solid #0ea5e9; margin: 30px 0;">
                                <tr>
                                    <td style="padding: 25px;">
                                        <p style="margin: 0 0 15px 0; color: #1a202c; font-size: 14px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;">
                                            🔐 Vos identifiants
                                        </p>

                                        <table width="100%" cellpadding="8" cellspacing="0">
                                            <tr>
                                                <td style="color: #4a5568; font-size: 14px; font-weight: 600; width: 120px;">Email :</td>
                                                <td style="color: #1a202c; font-size: 14px; font-family: 'Courier New', monospace;">{email}</td>
                                            </tr>
                                            <tr>
                                                <td style="color: #4a5568; font-size: 14px; font-weight: 600;">Mot de passe :</td>
                                                <td style="color: #1a202c; font-size: 16px; font-weight: 700; font-family: 'Courier New', monospace; letter-spacing: 1px;">{password}</td>
                                            </tr>
                                        </table>
                                    </td>
                                </tr>
                            </table>

                            <!-- Warning Box -->
                            <table width="100%" cellpadding="0" cellspacing="0" style="background: #fff7ed; border-radius: 12px; border-left: 4px solid #f59e0b; margin: 20px 0;">
                                <tr>
                                    <td style="padding: 20px;">
                                        <p style="margin: 0 0 10px 0; color: #92400e; font-size: 14px; font-weight: 600;">
                                            ⚠️ Important
                                        </p>
                                        <ul style="margin: 0; padding-left: 20px; color: #78350f; font-size: 14px; line-height: 1.6;">
                                            <li>Ce mot de passe est <strong>temporaire</strong></li>
                                            <li>Changez-le après votre première connexion</li>
                                            <li>Ne partagez jamais vos identifiants</li>
                                        </ul>
                                    </td>
                                </tr>
                            </table>

                            <p style="margin: 30px 0 0 0; color: #4a5568; font-size: 16px; line-height: 1.6;">
                                Cordialement,<br>
                                <strong style="color: #1a202c;">L'équipe Air Quality Application</strong>
                            </p>
                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td style="background-color: #f7fafc; padding: 30px; text-align: center; border-top: 1px solid #e2e8f0;">
                            <p style="margin: 0; color: #718096; font-size: 13px; line-height: 1.6;">
                                Cet email a été envoyé automatiquement, merci de ne pas y répondre.<br>
                                © 2026 Air Quality Application - Tous droits réservés
                            </p>
                        </td>
                    </tr>

                </table>
            </td>
        </tr>
    </table>
</body>
</html>
        """.strip()


    def send_password_reset_email(self, recipient_email: str, first_name: str, last_name: str, password: str) -> bool:
        """
        Envoie email de réinitialisation de mot de passe
        """
        logger.info("="*60)
        logger.info("📧 ENVOI EMAIL RESET - DÉBUT")
        logger.info(f"   Destinataire: {recipient_email}")

        if not self.smtp_user or not self.smtp_password:
            logger.error("❌ Configuration SMTP manquante")
            return False

        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = "Réinitialisation de votre mot de passe"
            msg['From'] = f"{self.sender_name} <{self.sender_email}>"
            msg['To'] = f"{first_name} {last_name} <{recipient_email}>"

            text_content = self._get_reset_password_text_content(first_name, last_name, password)
            html_content = self._get_reset_password_html_content(first_name, last_name, password)

            part1 = MIMEText(text_content, 'plain', 'utf-8')
            part2 = MIMEText(html_content, 'html', 'utf-8')

            msg.attach(part1)
            msg.attach(part2)

            if self.smtp_secure or self.smtp_port == 465:
                server = smtplib.SMTP_SSL(self.smtp_host, self.smtp_port)
            else:
                server = smtplib.SMTP(self.smtp_host, self.smtp_port)
                server.ehlo()
                server.starttls()
                server.ehlo()

            server.login(self.smtp_user, self.smtp_password)
            server.send_message(msg)
            server.quit()

            logger.info("✅ Email de réinitialisation envoyé avec succès!")
            return True

        except Exception as e:
            logger.error(f"❌ Erreur envoi email reset: {str(e)}")
            return False

    def _get_reset_password_text_content(self, first_name: str, last_name: str, password: str) -> str:
        return f"""
Bonjour {first_name} {last_name},

Une demande de réinitialisation de mot de passe a été effectuée pour votre compte.

Voici votre nouveau mot de passe temporaire :
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Mot de passe : {password}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Utilisez ce mot de passe pour vous connecter, puis changez-le immédiatement dans vos paramètres.

Si vous n'êtes pas à l'origine de cette demande, contactez immédiatement le support.

Cordialement,
L'équipe Air Quality Application
        """.strip()

    def _get_reset_password_html_content(self, first_name: str, last_name: str, password: str) -> str:
        return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
</head>
<body style="margin: 0; padding: 0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f5f7fa;">
    <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #f5f7fa; padding: 40px 20px;">
        <tr>
            <td align="center">
                <table width="600" cellpadding="0" cellspacing="0" style="background-color: white; border-radius: 16px; box-shadow: 0 4px 20px rgba(0,0,0,0.08); overflow: hidden;">
                    <tr>
                        <td style="background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%); padding: 40px 30px; text-align: center;">
                            <h1 style="margin: 0; color: white; font-size: 28px; font-weight: 700;">
                                🔐 Réinitialisation Mot de Passe
                            </h1>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 40px 30px;">
                            <h2 style="margin: 0 0 20px 0; color: #1a202c; font-size: 22px; font-weight: 600;">
                                Bonjour {first_name} {last_name},
                            </h2>
                            <p style="margin: 0 0 20px 0; color: #4a5568; font-size: 16px; line-height: 1.6;">
                                Une demande de réinitialisation de mot de passe a été effectuée. Voici votre nouveau mot de passe temporaire :
                            </p>
                            <table width="100%" cellpadding="0" cellspacing="0" style="background: #fff7ed; border-radius: 12px; border-left: 4px solid #f59e0b; margin: 30px 0;">
                                <tr>
                                    <td style="padding: 25px; text-align: center;">
                                        <span style="font-family: 'Courier New', monospace; font-size: 24px; font-weight: 700; color: #1a202c; letter-spacing: 2px;">
                                            {password}
                                        </span>
                                    </td>
                                </tr>
                            </table>
                            <p style="margin: 0 0 20px 0; color: #4a5568; font-size: 16px; line-height: 1.6;">
                                ⚠️ Pour votre sécurité, veuillez changer ce mot de passe dès votre connexion.
                            </p>
                             <p style="margin: 30px 0 0 0; color: #4a5568; font-size: 16px; line-height: 1.6;">
                                Cordialement,<br>
                                <strong style="color: #1a202c;">L'équipe Air Quality Application</strong>
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
        """.strip()
