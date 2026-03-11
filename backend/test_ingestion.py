#!/usr/bin/env python3
import asyncio
import logging
from src.services.azure_api import azure_api_service

logging.basicConfig(level=logging.DEBUG, format='%(name)s - %(levelname)s - %(message)s')

async def test_ingestion():
    try:
        print("Testing get_ingestion_volume()...")
        result = await azure_api_service.get_ingestion_volume(
            resource_group="PCS-Sentinel-RG",
            workspace_name="PCS-Sentinel-Demo",
            days_lookback=30
        )
        print(f"SUCCESS: Got {len(result)} tables")
        for table_name, gb_day in list(result.items())[:5]:
            print(f"  {table_name}: {gb_day} GB/day")
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_ingestion())
