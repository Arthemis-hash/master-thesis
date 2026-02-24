#!/usr/bin/env python3
"""
Interface utilisateur pour la section Environnement
Gestion du téléchargement et affichage des images satellites et Street View
"""
import streamlit as st
import os
import logging
from typing import Dict
from pathlib import Path
from db_async_wrapper import EnvironmentDB, AddressManagerWrapper

logger = logging.getLogger(__name__)


def get_or_create_address_id(address: str, lat: float, lon: float) -> int:
    """
    Récupère ou crée un address_id à partir d'une adresse et de coordonnées

    Args:
        address: Adresse complète
        lat: Latitude
        lon: Longitude

    Returns:
        int: ID de l'adresse dans la base de données
    """
    try:
        addr_mgr = AddressManagerWrapper()
        addr_result = addr_mgr.get_or_create_address(address, lat, lon)
        return addr_result['id']
    except Exception as e:
        logger.error(f"❌ Erreur récupération address_id: {e}")
        raise


def resolve_image_path(output_dir: str, address: str, image_type: str = 'satellite') -> str:
    """
    Résout le chemin d'images de manière robuste
    
    Args:
        output_dir: Chemin depuis la DB (peut être relatif ou absolu)
        address: Adresse pour fallback
        image_type: 'satellite' ou 'streetview'
    
    Returns:
        Chemin absolu vers le dossier d'images
    """
    # Si le chemin existe déjà, le retourner
    if os.path.exists(output_dir) and os.path.isabs(output_dir):
        return output_dir
    
    # Sinon, essayer le chemin relatif depuis app/
    app_dir = Path(__file__).parent
    relative_path = app_dir / output_dir
    if relative_path.exists():
        return str(relative_path)
    
    # Fallback: construire le chemin basé sur l'adresse normalisée
    try:
        from db_async_wrapper import DatabaseManager
        normalized = DatabaseManager.sanitize_address(address)
    except ImportError:
        # Fallback simple si db_utils non disponible
        import re
        normalized = re.sub(r'[^\w\s-]', '', address.lower())
        normalized = re.sub(r'[\s_-]+', '_', normalized).strip('_')
    
    # Construire le chemin
    fallback_path = app_dir / "environment_data" / image_type / normalized
    
    logger.info(f"🔍 Résolution chemin: {output_dir} -> {fallback_path}")
    return str(fallback_path)


def display_environment_section(address: str, lat: float, lon: float):
    """
    Section Environnement - Téléchargement et affichage des images satellites et Street View
    """
    st.header("🛰️ Visualisation de l'Environnement")
    
    st.markdown("""
    Cette section vous permet de télécharger et visualiser:
    - 📡 **Images satellites** (plusieurs niveaux de zoom)
    - 📸 **Photos Street View** (vue 3D des rues)
    """)
    
    # Initialiser la base de données
    try:
        env_db = EnvironmentDB()
        address_mgr = AddressManagerWrapper()

        # Récupérer ou créer l'adresse dans la base de données
        addr_info = address_mgr.get_or_create_address(address, lat, lon)
        address_id = addr_info['id']
        normalized = addr_info['normalized_address']

        # Récupérer les téléchargements existants
        existing_satellite = env_db.get_latest_satellite_download(address_id)
        existing_streetview = env_db.get_latest_streetview_download(address_id)

    except Exception as e:
        logger.error(f"Erreur environnement: {e}", exc_info=True)
        st.warning(f"⚠️ Module environnement temporairement indisponible")
        return
    
    # Interface de contrôle
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📡 Images Satellites")
        if existing_satellite:
            st.success(f"✅ Téléchargement existant du {existing_satellite.get('download_date', 'N/A')[:10]}")
            st.info(f"📁 {existing_satellite.get('total_images', 0)} images disponibles")
        else:
            st.info("Aucun téléchargement disponible")
        
        # Configuration du téléchargement satellite
        with st.expander("⚙️ Configuration Satellite"):
            st.warning("⚠️ Rayon > 1 km et zoom > 18 peuvent générer des images très volumineuses")
            radius_km = st.slider("Rayon (km)", 0.3, 1.5, 0.5, 0.1)
            zoom_levels = st.multiselect(
                "Niveaux de zoom (max 2 recommandé)",
                [15, 16, 17, 18, 19],
                default=[17, 18]
            )
            map_types = st.multiselect(
                "Types de carte",
                ['satellite', 'roadmap', 'hybrid', 'terrain'],
                default=['satellite', 'roadmap']
            )
            
            # Estimation précise de la taille de l'image finale
            # Calcul de sécurité
            is_config_safe = True
            if zoom_levels:
                max_zoom = max(zoom_levels)
                tiles_per_side = int(2 ** max_zoom * (radius_km / 40000) * 256 * 2)
                estimated_pixels = tiles_per_side * tiles_per_side
                MAX_SAFE_PIXELS = 200_000_000
                
                # Afficher estimation
                st.caption(f"📊 Taille estimée: {estimated_pixels:,} pixels (zoom max: {max_zoom})")
                
                # Alerte si dangereux
                if estimated_pixels > MAX_SAFE_PIXELS:
                    is_config_safe = False
                    st.error(
                        f"🚫 Configuration DANGEREUSE!\n\n"
                        f"Taille estimée: **{estimated_pixels:,} pixels**\n\n"
                        f"Limite sécurité: **{MAX_SAFE_PIXELS:,} pixels**\n\n"
                        f"💡 Réduisez le rayon ou le zoom maximum."
                    )
                elif estimated_pixels > MAX_SAFE_PIXELS * 0.8:
                    st.warning(f"⚠️ Configuration proche de la limite de sécurité ({estimated_pixels / MAX_SAFE_PIXELS * 100:.0f}%)")
                else:
                    st.success(f"✅ Configuration sécurisée ({estimated_pixels / MAX_SAFE_PIXELS * 100:.0f}% de la limite)")
            else:
                is_config_safe = False
                st.info("Sélectionnez au moins un niveau de zoom")
        
        # Désactiver le bouton si configuration dangereuse
        download_satellite = st.button(
            "🛰️ Télécharger Images Satellites", 
            key="btn_satellite",
            disabled=not is_config_safe,
            help="Bouton désactivé car la configuration dépasse la limite de sécurité" if not is_config_safe else None
        )
    
    with col2:
        st.subheader("📸 Street View")
        if existing_streetview:
            st.success(f"✅ Téléchargement existant du {existing_streetview.get('download_date', 'N/A')[:10]}")
            st.info(f"📷 {existing_streetview.get('total_photos', 0)} photos disponibles")
        else:
            st.info("Aucun téléchargement disponible")
        
        # Configuration du téléchargement Street View
        with st.expander("⚙️ Configuration Street View"):
            radius_m = st.slider("Rayon (mètres)", 100, 500, 250, 50)
            max_photos = st.slider("Nombre max de photos", 5, 20, 12, 1)
            use_filter = st.checkbox("Utiliser filtre qualité intelligent", value=True)
        
        download_streetview = st.button("📸 Télécharger Street View", key="btn_streetview")
    
    # Gestion des téléchargements
    if download_satellite:
        with st.spinner("🛰️ Téléchargement des images satellites en cours..."):
            try:
                # Import dynamique pour éviter les conflits
                from environment_downloader import EnvironmentDownloader
                downloader = EnvironmentDownloader(address)
                downloader.lat = lat
                downloader.lon = lon
                downloader.formatted_address = address
                
                metadata = downloader.download_satellite_maps(
                    radius_km=radius_km,
                    zoom_levels=zoom_levels,
                    map_types=map_types
                )

                # Récupérer ou créer l'address_id
                address_id = get_or_create_address_id(address, lat, lon)
                logger.info(f"💾 Enregistrement DB pour address_id={address_id}")

                # Enregistrer dans la base de données
                download_id = env_db.insert_satellite_download(
                    address_id=address_id,
                    radius_km=radius_km,
                    zoom_levels=zoom_levels,
                    map_types=map_types,
                    output_directory=metadata['output_directory'],
                    metadata=metadata
                )
                
                if download_id:
                    st.success(f"✅ {metadata['total_images']} images téléchargées avec succès!")
                    st.info(f"📁 Dossier: {metadata['output_directory']}")
                    st.rerun()
                else:
                    st.error("❌ Erreur lors de l'enregistrement")
                
            except Exception as e:
                st.error(f"❌ Erreur téléchargement: {e}")
                logger.error(f"Erreur téléchargement satellite: {e}", exc_info=True)
    
    if download_streetview:
        with st.spinner("📸 Téléchargement des images Street View en cours..."):
            try:
                # Import dynamique pour éviter les conflits
                from environment_downloader import EnvironmentDownloader
                downloader = EnvironmentDownloader(address)
                downloader.lat = lat
                downloader.lon = lon
                downloader.formatted_address = address
                
                metadata = downloader.download_streetview_images(
                    radius_m=radius_m,
                    max_photos=max_photos,
                    use_smart_filter=use_filter
                )

                # Récupérer ou créer l'address_id
                address_id = get_or_create_address_id(address, lat, lon)
                logger.info(f"💾 Enregistrement DB pour address_id={address_id}")

                # Enregistrer dans la base de données
                download_id = env_db.insert_streetview_download(
                    address_id=address_id,
                    radius_m=radius_m,
                    total_photos=metadata['total_photos'],
                    quality_filter_used=use_filter,
                    output_directory=metadata['output_directory'],
                    metadata=metadata
                )
                
                if download_id:
                    st.success(f"✅ {metadata['total_photos']} photos téléchargées avec succès!")
                    st.info(f"📁 Dossier: {metadata['output_directory']}")
                    st.rerun()
                else:
                    st.error("❌ Erreur lors de l'enregistrement")
                
            except Exception as e:
                st.error(f"❌ Erreur téléchargement: {e}")
                logger.error(f"Erreur téléchargement Street View: {e}", exc_info=True)
    
    st.divider()
    
    # Affichage des images existantes
    st.subheader("🖼️ Galerie d'Images")
    
    if existing_satellite or existing_streetview:
        view_tab1, view_tab2 = st.tabs(["📡 Satellites", "📸 Street View"])
        
        with view_tab1:
            if existing_satellite:
                display_satellite_gallery(existing_satellite)
            else:
                st.info("Aucune image satellite disponible")
        
        with view_tab2:
            if existing_streetview:
                display_streetview_gallery(existing_streetview)
            else:
                st.info("Aucune image Street View disponible")
    else:
        st.info("📥 Téléchargez des images pour les visualiser ici")


def display_satellite_gallery(download_info: Dict):
    """Affiche la galerie d'images satellites"""
    output_dir_db = download_info.get('output_directory', '')
    address = download_info.get('address', '')
    
    # Résoudre le chemin de manière robuste
    output_dir = resolve_image_path(output_dir_db, address, 'satellite')
    
    if not os.path.exists(output_dir):
        st.warning(f"⚠️ Dossier introuvable: {output_dir}")
        logger.warning(f"Chemin DB: {output_dir_db}, Résolu: {output_dir}")
        return
    
    # Lister les images
    image_files = [f for f in os.listdir(output_dir) if f.endswith('.png')]
    
    if not image_files:
        st.info("Aucune image trouvée dans le dossier")
        return
    
    st.write(f"**{len(image_files)} images disponibles**")
    
    # Organiser par type
    satellites = [f for f in image_files if 'satellite' in f]
    roadmaps = [f for f in image_files if 'roadmap' in f]
    
    if satellites:
        st.markdown("### 🛰️ Vue Satellite")
        cols = st.columns(min(3, len(satellites)))
        for idx, img_file in enumerate(satellites):
            with cols[idx % 3]:
                img_path = os.path.join(output_dir, img_file)
                st.image(img_path, caption=img_file, use_column_width=True)
    
    if roadmaps:
        st.markdown("### 🗺️ Vue Routière")
        cols = st.columns(min(3, len(roadmaps)))
        for idx, img_file in enumerate(roadmaps):
            with cols[idx % 3]:
                img_path = os.path.join(output_dir, img_file)
                st.image(img_path, caption=img_file, use_column_width=True)


def display_streetview_gallery(download_info: Dict):
    """Affiche la galerie d'images Street View"""
    output_dir_db = download_info.get('output_directory', '')
    address = download_info.get('address', '')
    
    # Résoudre le chemin de manière robuste
    output_dir = resolve_image_path(output_dir_db, address, 'streetview')
    
    if not os.path.exists(output_dir):
        st.warning(f"⚠️ Dossier introuvable: {output_dir}")
        logger.warning(f"Chemin DB: {output_dir_db}, Résolu: {output_dir}")
        return
    
    # Lister les images
    image_files = [f for f in os.listdir(output_dir) if f.endswith('.jpg') or f.endswith('.png')]
    
    if not image_files:
        st.info("Aucune image trouvée dans le dossier")
        return
    
    st.write(f"**{len(image_files)} photos disponibles**")
    
    # Afficher en grille
    cols = st.columns(3)
    for idx, img_file in enumerate(sorted(image_files)):
        with cols[idx % 3]:
            img_path = os.path.join(output_dir, img_file)
            st.image(img_path, caption=img_file, use_column_width=True)
    
    # Lien vers le fichier HTML de prévisualisation si disponible
    preview_html = os.path.join(output_dir, 'preview.html')
    if os.path.exists(preview_html):
        st.markdown("---")
        st.markdown("🌐 **Prévisualisation interactive disponible**")
        st.markdown(f"[Ouvrir la carte interactive]({preview_html})")
