#!/usr/bin/env python3
"""
Service d'envoi d'emails avec Mailjet
"""

import os
import logging
from mailjet_rest import Client
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()

logger = logging.getLogger(__name__)


class EmailService:
    """Gestionnaire d'envoi d'emails via Mailjet"""
    
    def __init__(self):
        self.api_key = os.getenv('MAILJET_API_KEY')
        self.api_secret = os.getenv('MAILJET_SECRET_KEY') or os.getenv('MAILJET_API_SECRET')
        self.sender_email = os.getenv('MAILJET_SENDER_EMAIL', 'noreply@airquality.app')
        self.sender_name = os.getenv('MAILJET_SENDER_NAME', 'Air Quality Application')
        
        # Debug configuration
        logger.info("🔧 Configuration Mailjet:")
        logger.info(f"   API Key: {self.api_key[:10]}..." if self.api_key else "   API Key: ❌ NON CONFIGURÉE")
        logger.info(f"   API Secret: {self.api_secret[:10]}..." if self.api_secret else "   API Secret: ❌ NON CONFIGURÉE")
        logger.info(f"   Sender Email: {self.sender_email}")
        logger.info(f"   Sender Name: {self.sender_name}")
        
        if not self.api_key or not self.api_secret:
            logger.error("❌ Clés Mailjet manquantes dans .env - L'envoi d'emails ne fonctionnera pas")
        else:
            logger.info("✅ Clés Mailjet chargées")
        
        self.client = Client(auth=(self.api_key, self.api_secret), version='v3.1')
    
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
        
        try:
            data = {
                'Messages': [
                    {
                        "From": {
                            "Email": self.sender_email,
                            "Name": self.sender_name
                        },
                        "To": [
                            {
                                "Email": recipient_email,
                                "Name": f"{first_name} {last_name}"
                            }
                        ],
                        "Subject": "Bienvenue sur Air Quality Application",
                        "TextPart": self._get_text_content(first_name, last_name, recipient_email, password),
                        "HTMLPart": self._get_html_content(first_name, last_name, recipient_email, password)
                    }
                ]
            }
            
            logger.info("📤 Envoi de la requête à Mailjet...")
            result = self.client.send.create(data=data)
            
            logger.info(f"📥 Réponse Mailjet - Code: {result.status_code}")
            
            if result.status_code == 200:
                response_data = result.json()
                logger.info(f"✅ Email envoyé avec succès!")
                logger.info(f"   Réponse complète: {response_data}")
                
                # Extraire l'ID du message si disponible
                if 'Messages' in response_data and len(response_data['Messages']) > 0:
                    message_info = response_data['Messages'][0]
                    logger.info(f"   Message ID: {message_info.get('To', [{}])[0].get('MessageID', 'N/A')}")
                    logger.info(f"   Status: {message_info.get('Status', 'N/A')}")
                
                logger.info("="*60)
                return True
            else:
                error_data = result.json()
                logger.error(f"❌ ERREUR MAILJET - Code: {result.status_code}")
                logger.error(f"   Détails: {error_data}")
                
                # Parser les erreurs spécifiques Mailjet
                if 'ErrorMessage' in error_data:
                    logger.error(f"   Message d'erreur: {error_data['ErrorMessage']}")
                if 'ErrorCode' in error_data:
                    logger.error(f"   Code d'erreur: {error_data['ErrorCode']}")
                
                logger.info("="*60)
                return False
                
        except Exception as e:
            logger.error(f"❌ EXCEPTION lors de l'envoi email")
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
                                © 2025 Air Quality Application - Tous droits réservés
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
