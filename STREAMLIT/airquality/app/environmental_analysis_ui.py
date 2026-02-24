#!/usr/bin/env python3
"""
Module UI pour l'analyse environnementale (YOLO + Cartes)
Intègre la détection d'objets et l'analyse de segmentation
"""

import streamlit as st
import os
import sys
import logging
from pathlib import Path
import json
from PIL import Image
import pandas as pd
from datetime import datetime
import re

# Augmenter limite PIL pour éviter l'erreur "decompression bomb"
Image.MAX_IMAGE_PIXELS = 500000000  # 500 millions de pixels

logger = logging.getLogger(__name__)

# Chemins vers les modules existants
TRAIN_YOLO_PATH = Path(__file__).parent.parent.parent.parent / "train-yolo"
IMAGE_ANALYSIS_PATH = Path(__file__).parent.parent.parent / "Image-Analysis"
MAP_ANALYSIS_PATH = IMAGE_ANALYSIS_PATH / "map-anlaysis"

# Ajouter aux paths si nécessaire
if str(TRAIN_YOLO_PATH) not in sys.path:
    sys.path.insert(0, str(TRAIN_YOLO_PATH))
if str(MAP_ANALYSIS_PATH) not in sys.path:
    sys.path.insert(0, str(MAP_ANALYSIS_PATH))


def check_gpu_availability():
    """Vérifie la disponibilité du GPU (M1 via MPS)"""
    try:
        import torch
        if torch.backends.mps.is_available():
            return 'mps', '✅ GPU M1 (MPS) disponible'
        elif torch.cuda.is_available():
            return 'cuda', '✅ GPU CUDA disponible'
        else:
            return 'cpu', '⚠️ CPU uniquement'
    except Exception as e:
        logger.warning(f"Erreur détection GPU: {e}")
        return 'cpu', '⚠️ CPU uniquement'


@st.cache_data(ttl=300)  # Cache 5 minutes
def get_available_models():
    """Liste les modèles YOLO disponibles"""
    models = {}
    
    # Modèle pré-entraîné YOLO11n (détection générale)
    yolo11n_path = Path(__file__).parent.parent.parent.parent / "ultralytics-main" / "yolo11n.pt"
    if yolo11n_path.exists():
        models['yolo11n'] = {
            'path': str(yolo11n_path),
            'name': 'YOLO11n (général)',
            'type': 'pretrained',
            'description': 'Détection générale : voitures, personnes, vélos, etc.'
        }
    
    # Modèle spécialisé arbres (tree detection)
    # Le modèle Trained_model.pt est le modèle spécialisé pour détecter les arbres
    tree_model_paths = [
        IMAGE_ANALYSIS_PATH / "trained-yolo-model" / "Trained_model.pt",
        Path(__file__).parent.parent.parent.parent / "STREAMLIT" / "Image-Analysis" / "trained-yolo-model" / "Trained_model.pt",
        TRAIN_YOLO_PATH / "results" / "train" / "weights" / "best.pt"
    ]
    
    for tree_model_path in tree_model_paths:
        if tree_model_path.exists():
            models['tree_model'] = {
                'path': str(tree_model_path),
                'name': 'Tree Model (arbres)',
                'type': 'tree_specialist',
                'description': 'Spécialisé détection arbres et végétation'
            }
            break
    
    # Option combinée (YOLO11n + Tree Model)
    if 'yolo11n' in models and 'tree_model' in models:
        models['combined'] = {
            'path': [models['yolo11n']['path'], models['tree_model']['path']],
            'name': 'Combiné (général + arbres)',
            'type': 'combined',
            'description': 'Combine détection générale YOLO11n et arbres spécialisés'
        }
    
    return models


@st.cache_data(ttl=300)  # Cache 5 minutes
def get_satellite_images(address: str):
    """Récupère les images satellites téléchargées pour une adresse"""
    # Normaliser l'adresse
    try:
        from db_async_wrapper import DatabaseManager
        normalized = DatabaseManager.sanitize_address(address)
    except ImportError:
        # Fallback si db_utils non disponible
        normalized = re.sub(r'[^\w\s-]', '', address.lower())
        normalized = re.sub(r'[\s_-]+', '_', normalized).strip('_')
    
    sat_dir = Path(__file__).parent / "environment_data" / "satellite" / normalized
    
    if not sat_dir.exists():
        logger.warning(f"Dossier satellite introuvable: {sat_dir}")
        return []
    
    images = []
    for img_file in sat_dir.glob("*.png"):
        if img_file.name != "metadata.json":
            images.append({
                'path': str(img_file),
                'name': img_file.name
            })
    
    logger.info(f"✅ {len(images)} images satellites trouvées dans {sat_dir}")
    return images


@st.cache_data(ttl=300)  # Cache 5 minutes
def get_streetview_images(address: str):
    """Récupère les images Street View téléchargées pour une adresse"""
    # Normaliser l'adresse
    try:
        from db_async_wrapper import DatabaseManager
        normalized = DatabaseManager.sanitize_address(address)
    except ImportError:
        # Fallback si db_utils non disponible
        normalized = re.sub(r'[^\w\s-]', '', address.lower())
        normalized = re.sub(r'[\s_-]+', '_', normalized).strip('_')
    
    sv_dir = Path(__file__).parent / "environment_data" / "streetview" / normalized
    
    if not sv_dir.exists():
        logger.warning(f"Dossier Street View introuvable: {sv_dir}")
        return []
    
    images = []
    for img_file in sv_dir.glob("*.jpg"):
        images.append({
            'path': str(img_file),
            'name': img_file.name
        })
    
    logger.info(f"✅ {len(images)} images Street View trouvées dans {sv_dir}")
    return images


def _get_normalized_address(address: str) -> str:
    """Normalise une adresse pour l'utiliser comme nom de dossier."""
    try:
        from db_async_wrapper import DatabaseManager
        return DatabaseManager.sanitize_address(address)
    except ImportError:
        normalized = re.sub(r'[^\w\s-]', '', address.lower())
        return re.sub(r'[\s_-]+', '_', normalized).strip('_')


def run_yolo_detection(model_path, images: list, device: str = 'mps', conf: float = 0.25, is_combined: bool = False, address: str = None):
    """
    Lance la détection YOLO sur les images

    Args:
        model_path: Chemin vers le modèle YOLO (str) ou liste de chemins (combined)
        images: Liste des chemins d'images
        device: Device à utiliser ('mps', 'cuda', 'cpu')
        conf: Seuil de confiance
        is_combined: True si mode combiné (2 modèles)
        address: Adresse pour organiser les résultats par dossier

    Returns:
        Résultats de détection
    """
    try:
        # Import YOLO
        from ultralytics import YOLO

        # Import du gestionnaire de résultats
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "detection_resultats",
            TRAIN_YOLO_PATH / "detection-resultats.py"
        )
        detection_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(detection_module)
        DetectionResultsManager = detection_module.DetectionResultsManager

        # Créer dossier de sortie par adresse
        base_output_dir = Path(__file__).parent / "environment_data" / "yolo_results"
        if address:
            normalized = _get_normalized_address(address)
            output_dir = base_output_dir / normalized
        else:
            output_dir = base_output_dir
        output_dir.mkdir(parents=True, exist_ok=True)

        if is_combined and isinstance(model_path, list):
            # MODE COMBINÉ : 2 modèles
            logger.info("🔍 Mode combiné : 2 modèles")

            all_results = []
            all_class_names = {}

            for idx, path in enumerate(model_path):
                model_name = "général" if idx == 0 else "arbres"
                logger.info(f"🔍 Chargement modèle {idx+1}/2 ({model_name}): {path}")
                model = YOLO(path)

                # Fusionner les noms de classes
                if hasattr(model, 'names'):
                    all_class_names.update(model.names)

                logger.info(f"🚀 Détection avec modèle {model_name} sur {len(images)} images (device={device})")

                # Lancer prédictions
                results = model.predict(
                    source=images,
                    save=True,
                    device=device,
                    conf=conf,
                    project=str(output_dir),
                    name=f'detection_{model_name}',
                    exist_ok=True
                )

                all_results.extend(results)

            logger.info(f"✅ Détection combinée terminée : {len(all_results)} résultats")

            # Traiter tous les résultats combinés
            results_manager = DetectionResultsManager(class_names=all_class_names)
            results_data = results_manager.process_results(all_results)

            return results_data, str(output_dir / "detection_général")

        else:
            # MODE SIMPLE : 1 modèle
            logger.info(f"🔍 Chargement du modèle: {model_path}")
            model = YOLO(model_path)

            # Récupérer les noms de classes
            class_names = model.names if hasattr(model, 'names') else {}

            logger.info(f"🚀 Lancement détection sur {len(images)} images (device={device})")

            # Lancer les prédictions
            results = model.predict(
                source=images,
                save=True,
                device=device,
                conf=conf,
                project=str(output_dir),
                name='detection',
                exist_ok=True
            )

            # Traiter les résultats
            results_manager = DetectionResultsManager(class_names=class_names)
            results_data = results_manager.process_results(results)

            logger.info(f"✅ Détection terminée: {results_data['metadata']['total_detections']} détections")

            return results_data, str(output_dir / "detection")

    except Exception as e:
        logger.error(f"❌ Erreur YOLO: {e}")
        raise


def run_map_analysis(satellite_path: str, roadmap_path: str, zoom: int = 17, address: str = None):
    """
    Lance l'analyse de cartes

    Args:
        satellite_path: Chemin image satellite
        roadmap_path: Chemin image roadmap
        zoom: Niveau de zoom
        address: Adresse pour organiser les résultats par dossier

    Returns:
        Résultats d'analyse
    """
    try:
        from map_analyzer import EnhancedMapAnalyzer

        logger.info(f"🗺️ Analyse de cartes (zoom {zoom})")

        # Créer l'analyseur
        analyzer = EnhancedMapAnalyzer(zoom_level=zoom, pixel_to_meter=0.6)

        # Charger les images
        analyzer.load_images(satellite_path, roadmap_path)

        # Analyser
        results = analyzer.analyze_full()

        # Créer dossier de sortie par adresse
        base_output_dir = Path(__file__).parent / "environment_data" / "map_analysis"
        if address:
            normalized = _get_normalized_address(address)
            output_dir = base_output_dir / normalized
        else:
            output_dir = base_output_dir
        output_dir.mkdir(parents=True, exist_ok=True)

        # Sauvegarder
        analyzer.save_results(str(output_dir))

        logger.info(f"✅ Analyse terminée, résultats dans {output_dir}")

        return results, str(output_dir)

    except Exception as e:
        logger.error(f"❌ Erreur analyse cartes: {e}")
        raise


def display_yolo_results(results_data: dict, output_dir: str):
    """Affiche les résultats YOLO"""
    st.subheader("📊 Résumé des détections")
    
    # Métriques principales
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("🖼️ Images analysées", results_data['metadata']['total_images'])
    
    with col2:
        st.metric("🎯 Détections totales", results_data['metadata']['total_detections'])
    
    with col3:
        unique_classes = len(results_data['summary'])
        st.metric("🏷️ Classes détectées", unique_classes)
    
    with col4:
        avg_per_image = results_data['metadata']['total_detections'] / max(results_data['metadata']['total_images'], 1)
        st.metric("📈 Moyenne / image", f"{avg_per_image:.1f}")
    
    st.divider()
    
    # Résumé par classe avec cartes
    st.subheader("📋 Détections par classe")
    
    if results_data['summary']:
        # Afficher les statistiques principales en cartes
        summary_items = list(results_data['summary'].items())
        num_classes = len(summary_items)
        
        if num_classes > 0:
            # Afficher jusqu'à 4 classes principales en cartes
            cols = st.columns(min(4, num_classes))
            for idx, (class_name, stats) in enumerate(summary_items[:4]):
                with cols[idx]:
                    st.metric(
                        label=f"🏷️ {class_name}",
                        value=stats.get('total_count', 0),
                        delta=f"{stats.get('average_per_image', 0):.1f} / image"
                    )
        
        # Tableau détaillé
        st.divider()
        st.write("**📊 Tableau détaillé**")
        
        summary_data = []
        for class_name, stats in results_data['summary'].items():
            summary_data.append({
                'Classe': class_name,
                'Nombre total': stats.get('total_count', 0),
                'Moyenne par image': f"{stats.get('average_per_image', 0):.1f}",
                'Surface moy. (px²)': f"{stats.get('average_surface_pixels', 0):.0f}",
                'Surface totale (px²)': f"{stats.get('total_surface_pixels', 0):.0f}"
            })
        
        df_summary = pd.DataFrame(summary_data)
        st.dataframe(df_summary, hide_index=True)
    else:
        st.info("Aucune détection trouvée")
    
    # Images annotées
    st.divider()
    st.subheader("🖼️ Images annotées")
    
    # Chercher les images dans tous les sous-dossiers
    output_path = Path(output_dir)
    result_imgs = []
    for ext in ['*.jpg', '*.jpeg', '*.png']:
        result_imgs.extend(output_path.rglob(ext))
    
    if result_imgs:
        st.write(f"📸 {len(result_imgs)} images avec détections")
        cols = st.columns(3)
        for idx, img_path in enumerate(result_imgs[:12]):  # Max 12 images
            with cols[idx % 3]:
                try:
                    with Image.open(img_path) as img:
                        st.image(img, caption=img_path.name)
                except Exception as e:
                    logger.warning(f"Impossible d'afficher {img_path}: {e}")
    else:
        st.warning(f"⚠️ Aucune image annotée trouvée dans {output_dir}")
        st.info(f"📁 Vérifiez le dossier : `{output_dir}`")


def display_map_analysis_results(results: dict, output_dir: str):
    """Affiche les résultats d'analyse de cartes"""
    st.subheader("🗺️ Segmentation de la carte")
    
    # Métriques de couverture
    st.write("**📊 Couverture du sol**")
    
    col1, col2, col3, col4 = st.columns(4)
    
    # Support du format statistics_z*.json (nested sous 'elements')
    data_source = results.get('elements', results)
    
    with col1:
        # Compatible avec 'vegetation' (ancien) et 'green_spaces' (nouveau)
        veg_data = data_source.get('green_spaces', data_source.get('vegetation', {}))
        # Support pour format metrics direct ou nested
        if 'metrics' in veg_data:
             coverage = veg_data['metrics'].get('coverage_percent', 0)
        else:
             coverage = veg_data.get('coverage_percent', 0)
        st.metric("🌳 Végétation", f"{coverage:.1f}%")
    
    with col2:
        roads_data = data_source.get('roads', {})
        if 'metrics' in roads_data:
             coverage = roads_data['metrics'].get('coverage_percent', 0)
        else:
             coverage = roads_data.get('coverage_percent', 0)
        st.metric("🛣️ Routes", f"{coverage:.1f}%")
    
    with col3:
        build_data = data_source.get('buildings', {})
        if 'metrics' in build_data:
             coverage = build_data['metrics'].get('coverage_percent', 0)
        else:
             coverage = build_data.get('coverage_percent', 0)
        st.metric("🏢 Bâtiments", f"{coverage:.1f}%")
    
    with col4:
        water_data = data_source.get('water', {})
        if 'metrics' in water_data:
             coverage = water_data['metrics'].get('coverage_percent', 0)
        else:
             coverage = water_data.get('coverage_percent', 0)
        st.metric("💧 Eau", f"{coverage:.1f}%")
    
    st.divider()
    
    # Images de segmentation
    st.subheader("🎨 Visualisation")
    
    output_path = Path(output_dir)
    
    # Chercher les images générées
    segmentation_img = list(output_path.glob("segmentation_*.png"))
    overlay_img = list(output_path.glob("overlay_*.png"))
    
    col_left, col_right = st.columns(2)
    
    with col_left:
        if segmentation_img:
            st.write("**Segmentation colorée**")
            with Image.open(segmentation_img[0]) as img:
                st.image(img)
    
    with col_right:
        if overlay_img:
            st.write("**Superposition**")
            with Image.open(overlay_img[0]) as img:
                st.image(img)
    
    # Légende
    st.info("""
    🌳 **Vert** : Végétation | 🛣️ **Gris** : Routes | 🏢 **Rouge** : Bâtiments | 💧 **Bleu** : Eau
    """)


def display_environmental_analysis(address: str):
    """
    Section principale d'analyse environnementale
    
    Args:
        address: Adresse analysée
    """
    st.header("🔬 Analyse Environnementale")
    
    st.info("""
    Cette section combine la détection d'objets (YOLO) et l'analyse de segmentation des cartes 
    pour fournir une analyse complète de l'environnement.
    """)
    
    # Vérifier disponibilité GPU
    device, gpu_status = check_gpu_availability()
    st.caption(gpu_status)
    
    st.divider()
    
    # === SECTION 1: DÉTECTION D'OBJETS (YOLO) ===
    st.subheader("🎯 Détection d'objets (YOLO)")
    
    # Récupérer les images disponibles
    streetview_images = get_streetview_images(address)
    
    if not streetview_images:
        st.warning("⚠️ Aucune image Street View disponible. Téléchargez d'abord les images dans l'onglet '🗺️ Cartes & Images'.")
    else:
        st.success(f"✅ {len(streetview_images)} images Street View disponibles")
        
        # Sélection du modèle
        available_models = get_available_models()
        
        if not available_models:
            st.error("❌ Aucun modèle YOLO trouvé. Vérifiez les chemins des modèles.")
        else:
            col1, col2 = st.columns([2, 1])
            
            with col1:
                model_options = {k: v['name'] for k, v in available_models.items()}
                selected_model = st.selectbox(
                    "Choisir un modèle",
                    options=list(model_options.keys()),
                    format_func=lambda x: model_options[x],
                    help="Sélectionnez le modèle YOLO à utiliser pour la détection"
                )
            
            with col2:
                conf_threshold = st.slider("Seuil de confiance", 0.1, 0.9, 0.25, 0.05)
            
            # Afficher la description du modèle sélectionné
            model_info = available_models[selected_model]
            st.info(f"ℹ️ **{model_info['name']}** : {model_info['description']}")
            
            # Bouton de lancement
            if st.button("🚀 Lancer la détection YOLO", type="primary"):
                model_path = available_models[selected_model]['path']
                image_paths = [img['path'] for img in streetview_images]
                
                # Détecter si c'est le mode combiné
                is_combined = selected_model == 'combined'
                
                with st.spinner(f"🔍 Analyse en cours avec {model_options[selected_model]}..."):
                    try:
                        results_data, output_dir = run_yolo_detection(
                            model_path=model_path,
                            images=image_paths,
                            device=device,
                            conf=conf_threshold,
                            is_combined=is_combined,
                            address=address
                        )
                        
                        # Sauvegarder sur disque au lieu de session_state (économie mémoire)
                        results_file = Path(output_dir) / "yolo_results.json"
                        with open(results_file, 'w', encoding='utf-8') as f:
                            json.dump(results_data, f, ensure_ascii=False, indent=2)
                        
                        # ✅ Sauvegarder aussi en PostgreSQL
                        try:
                            import asyncio
                            from db_async_wrapper import ImageAnalysisManager

                            async def save_to_db():
                                analysis_manager = ImageAnalysisManager()

                                # Enregistrer l'analyse (image_id=0 pour analyse batch)
                                await analysis_manager.save_analysis(
                                    image_type="streetview",
                                    image_id=0,
                                    analysis_type="yolo",
                                    model_name="yolov8n",
                                    results=results_data
                                )

                            asyncio.run(save_to_db())
                            logger.info("✅ Analyse YOLO enregistrée en PostgreSQL")
                        except Exception as e:
                            logger.warning(f"⚠️ Impossible d'enregistrer en DB: {e}")
                        
                        st.session_state.yolo_results_path = str(results_file)
                        st.session_state.yolo_output_dir = output_dir
                        
                        st.success("✅ Analyse YOLO terminée!")
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"❌ Erreur lors de l'analyse: {e}")
                        logger.error(f"Erreur YOLO: {e}", exc_info=True)
    
    # Afficher les résultats si disponibles (charger depuis disque)
    if 'yolo_results_path' in st.session_state:
        try:
            with open(st.session_state.yolo_results_path, 'r', encoding='utf-8') as f:
                yolo_results = json.load(f)
            
            st.divider()
            display_yolo_results(yolo_results, st.session_state.yolo_output_dir)
            
            # Export JSON
            col1, col2 = st.columns([3, 1])
            with col2:
                json_str = json.dumps(yolo_results, indent=2, ensure_ascii=False)
                st.download_button(
                    label="📥 Télécharger JSON",
                    data=json_str,
                    file_name=f"yolo_results_{address.replace(' ', '_')}.json",
                    mime="application/json"
                )
        except Exception as e:
            logger.error(f"Erreur chargement résultats YOLO: {e}")
            st.error("⚠️ Impossible de charger les résultats")
    
    st.divider()
    
    # === SECTION 2: ANALYSE DE CARTES ===
    st.subheader("🗺️ Analyse de segmentation des cartes")
    
    # Récupérer les images satellites
    satellite_images = get_satellite_images(address)
    
    if not satellite_images:
        st.warning("⚠️ Aucune carte satellite disponible. Téléchargez d'abord les cartes dans l'onglet '🗺️ Cartes & Images'.")
    else:
        # Trouver les paires satellite/roadmap
        satellite_imgs = [img for img in satellite_images if 'satellite' in img['name']]
        roadmap_imgs = [img for img in satellite_images if 'roadmap' in img['name']]
        
        if satellite_imgs and roadmap_imgs:
            st.success(f"✅ {len(satellite_imgs)} paires de cartes disponibles")
            
            # Sélection du zoom
            zoom_options = []
            for sat_img in satellite_imgs:
                # Extraire le zoom du nom (ex: map_z17_satellite.png)
                match = re.search(r'_z(\d+)_', sat_img['name'])
                if match:
                    zoom = int(match.group(1))
                    if zoom not in zoom_options:
                        zoom_options.append(zoom)
            
            if zoom_options:
                selected_zoom = st.selectbox("Niveau de zoom", sorted(zoom_options), index=0)
                
                # Trouver les images correspondantes
                sat_img = next((img for img in satellite_imgs if f'_z{selected_zoom}_' in img['name']), None)
                road_img = next((img for img in roadmap_imgs if f'_z{selected_zoom}_' in img['name']), None)
                
                if sat_img and road_img:
                    # Bouton de lancement
                    if st.button("🗺️ Lancer l'analyse de cartes", type="primary"):
                        with st.spinner(f"🔍 Analyse de segmentation en cours (zoom {selected_zoom})..."):
                            try:
                                results, output_dir = run_map_analysis(
                                    satellite_path=sat_img['path'],
                                    roadmap_path=road_img['path'],
                                    zoom=selected_zoom,
                                    address=address
                                )
                                # analyzer.save_results(str(output_dir)) est déjà appelé dans run_map_analysis
                                results_file = Path(output_dir) / f"statistics_z{selected_zoom}.json"
                                # Note: map_analyzer sauvegarde les stats dans statistics_z{zoom}.json
                                
                                # ✅ Sauvegarder aussi en PostgreSQL
                                try:
                                    import asyncio
                                    from db_async_wrapper import ImageAnalysisManager

                                    async def save_to_db():
                                        analysis_manager = ImageAnalysisManager()

                                        # Enregistrer l'analyse (image_id=0 pour analyse batch)
                                        await analysis_manager.save_analysis(
                                            image_type="satellite",
                                            image_id=0,
                                            analysis_type="segmentation",
                                            model_name="deeplabv3",
                                            results=results
                                        )

                                    asyncio.run(save_to_db())
                                    logger.info("✅ Analyse Map enregistrée en PostgreSQL")
                                except Exception as e:
                                    logger.warning(f"⚠️ Impossible d'enregistrer en DB: {e}")
                                
                                st.session_state.map_results_path = str(results_file)
                                st.session_state.map_output_dir = output_dir
                                
                                st.success("✅ Analyse de cartes terminée!")
                                st.rerun()
                                
                            except Exception as e:
                                st.error(f"❌ Erreur lors de l'analyse: {e}")
                                logger.error(f"Erreur analyse cartes: {e}", exc_info=True)
        else:
            st.warning("⚠️ Paires satellite/roadmap incomplètes. Assurez-vous d'avoir téléchargé les deux types de cartes.")
    
    # Afficher les résultats si disponibles (charger depuis disque)
    if 'map_results_path' in st.session_state:
        try:
            with open(st.session_state.map_results_path, 'r', encoding='utf-8') as f:
                map_results = json.load(f)
            
            st.divider()
            display_map_analysis_results(map_results, st.session_state.map_output_dir)
            
            # Export JSON
            col1, col2 = st.columns([3, 1])
            with col2:
                json_str = json.dumps(map_results, indent=2, default=str, ensure_ascii=False)
                st.download_button(
                    label="📥 Télécharger JSON",
                    data=json_str,
                    file_name=f"map_analysis_{address.replace(' ', '_')}.json",
                    mime="application/json"
                )
        except Exception as e:
            logger.error(f"Erreur chargement résultats Map: {e}")
            st.error("⚠️ Impossible de charger les résultats")
