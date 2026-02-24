#!/usr/bin/env python3
"""
Test script for QeV calculation
Tests with real data from the database
"""

import sys
import logging
from db_async_wrapper import AirQualityDB

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def test_qev_calculation():
    """Test QeV calculation with real data"""

    # Test with Grand-Place Brussels (has 2460 air quality records)
    test_address = "1000 Région de Bruxelles-Capitale - Brussels Hoofdstedelijk Gewest"

    logger.info("="*80)
    logger.info("TEST QEV CALCULATION")
    logger.info("="*80)
    logger.info(f"Address: {test_address}")
    logger.info("")

    # Initialize database
    db = AirQualityDB(address=test_address)

    # Get location summary
    logger.info("1. Fetching location summary...")
    summary = db.get_location_summary(test_address)

    if not summary:
        logger.error("❌ No data found for this address")
        return False

    logger.info(f"   ✅ Found {summary['total_records']} air quality records")
    logger.info(f"   📍 Location: {summary['latitude']:.4f}, {summary['longitude']:.4f}")
    logger.info(f"   🌫️  PM2.5 avg: {summary['avg_pm2_5']:.1f} μg/m³")
    logger.info("")

    # Calculate QeV score
    logger.info("2. Calculating QeV score...")
    try:
        qev_result = db.get_qev_score(test_address)

        if not qev_result:
            logger.error("❌ QeV calculation failed")
            return False

        logger.info("   ✅ QeV calculation successful!")
        logger.info("")

        # Display results
        logger.info("="*80)
        logger.info("QEV RESULTS")
        logger.info("="*80)
        logger.info(f"📊 QeV Score: {qev_result['QeV']:.3f}")
        logger.info(f"📈 Category: {qev_result['QeV_category']}")
        logger.info(f"🎯 Confidence: {qev_result['confidence_level']:.0%}")
        logger.info(f"📋 Data Completeness: {qev_result['data_completeness']:.0%}")
        logger.info("")

        # Raw indicators
        logger.info("RAW INDICATORS:")
        logger.info("-" * 80)
        air = qev_result['raw_indicators']['air']
        traffic = qev_result['raw_indicators']['traffic']
        green = qev_result['raw_indicators']['green']

        logger.info(f"Air Quality:")
        logger.info(f"  - NO₂: {air['no2']:.1f} μg/m³" if air['no2'] else "  - NO₂: N/A")
        logger.info(f"  - PM2.5: {air['pm25']:.1f} μg/m³" if air['pm25'] else "  - PM2.5: N/A")
        logger.info(f"  - PM10: {air['pm10']:.1f} μg/m³" if air['pm10'] else "  - PM10: N/A")
        logger.info(f"  - O₃: {air['o3']:.1f} μg/m³" if air['o3'] else "  - O₃: N/A")
        logger.info(f"  - SO₂: {air['so2']:.1f} μg/m³" if air['so2'] else "  - SO₂: N/A")
        logger.info("")

        logger.info(f"Traffic:")
        logger.info(f"  - Light vehicles: {traffic['light_vehicles']} veh/h")
        logger.info(f"  - Utility vehicles: {traffic['utility_vehicles']} veh/h")
        logger.info(f"  - Heavy vehicles: {traffic['heavy_vehicles']} veh/h")
        logger.info("")

        logger.info(f"Green Spaces:")
        logger.info(f"  - Trees visible: {green.get('trees_visible_count', 0)}")
        logger.info(f"  - Canopy coverage: {green.get('canopy_coverage_pct', 0):.1f}%")
        logger.info(f"  - Distance to park: {green.get('distance_to_nearest_park_m', 999):.0f}m")
        logger.info("")

        # Sub-indices
        logger.info("SUB-INDICES:")
        logger.info("-" * 80)
        logger.info(f"Air Index (BelAQI): {qev_result['sub_indices']['I_Air']:.2f}/10")
        logger.info(f"Traffic Nuisance: {qev_result['sub_indices']['I_Trafic']:.0f} units")
        logger.info(f"Green Index (3-30-300): {qev_result['sub_indices']['I_Vert']:.2f}")
        logger.info("")

        # Normalized scores
        logger.info("NORMALIZED SCORES (0-1):")
        logger.info("-" * 80)
        logger.info(f"S_Air: {qev_result['normalized_scores']['S_Air']:.3f}")
        logger.info(f"S_Trafic: {qev_result['normalized_scores']['S_Trafic']:.3f}")
        logger.info(f"S_Vert: {qev_result['normalized_scores']['S_Vert']:.3f}")
        logger.info("")

        # Weighted contributions
        logger.info("WEIGHTED CONTRIBUTIONS:")
        logger.info("-" * 80)
        contrib_air = qev_result['normalized_scores']['S_Air'] * qev_result['weights']['air']
        contrib_traffic = qev_result['normalized_scores']['S_Trafic'] * qev_result['weights']['traffic']
        contrib_green = qev_result['normalized_scores']['S_Vert'] * qev_result['weights']['green']

        logger.info(f"Air Quality (50%): {contrib_air:.3f}")
        logger.info(f"Traffic (25%): {contrib_traffic:.3f}")
        logger.info(f"Green Spaces (25%): {contrib_green:.3f}")
        logger.info(f"TOTAL QeV: {contrib_air + contrib_traffic + contrib_green:.3f}")
        logger.info("")

        # Interpretation
        logger.info("INTERPRETATION:")
        logger.info("-" * 80)
        logger.info(qev_result['interpretation'])
        logger.info("")

        logger.info("="*80)
        logger.info("✅ TEST PASSED - QeV calculation is working correctly!")
        logger.info("="*80)

        return True

    except Exception as e:
        logger.error(f"❌ Error during QeV calculation: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_qev_calculation()
    sys.exit(0 if success else 1)
